"""Generation logic for the classroom app (no Streamlit code here).

Everything both generator models receive is defined in this file: the same
system prompt, the same fixed claims, the same formats and word ranges. The
only difference between the two batch requests is the model ID.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from openrouter_client import CallResult, now_utc

HERE = Path(__file__).parent
WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/tobacco"

# The wrapper is shown around passages and stored in its own fields. It is
# never part of a passage, so a later classifier can receive the passage alone.
EXERCISE_WARNING = ("Classroom exercise: some passages in this app are deliberately false health "
                    "claims, generated or written for teaching. They are not health advice. "
                    "Do not copy, post or share them.")
CORRECTION = ("Fact: smoking is harmful. Tobacco damages nearly every organ in the body, and there is "
              "no safe level of tobacco use (WHO tobacco fact sheet).")

# Fixed, source-backed claim assignments. Both generators get exactly these.
CLAIMS = {
    "true": {
        "claim_id": "C-TRUE",
        "text": "Smoking cigarettes harms health: it raises the risk of cancer, heart disease and lung disease.",
        "basis": "Supported by the WHO tobacco fact sheet (key facts and overview).",
    },
    "false": {
        "claim_id": "C-FALSE",
        "text": "Smoking cigarettes is healthy: it lowers the risk of cancer, heart disease and lung disease.",
        "basis": "Contradicted by the WHO tobacco fact sheet (key facts and overview).",
    },
}
LABEL_NAMES = {"true": "TRUE claim (supported)", "false": "FALSE claim (contradicted)"}

FORMATS = {
    "social_post": {
        "label": "Social-media post",
        "short": "social",
        "min_words": 20,
        "max_words": 60,
        "instructions": ("A short social-media post: informal first- or second-person voice, "
                         "at most two hashtags, no links and no @-handles."),
    },
    "scientific_prose": {
        "label": "Short scientific-style paragraph",
        "short": "science",
        "min_words": 50,
        "max_words": 110,
        "instructions": ("A short paragraph in a neutral academic register, like a textbook or the "
                         "opening of a paper. No citations, researchers, institutions, journals, DOIs, "
                         "study names, trial results or numbers."),
    },
}

# The balanced design: per generator, both labels crossed with both formats.
BALANCED_SLOTS = [
    {"slot_id": "S1", "label": "false", "format": "social_post"},
    {"slot_id": "S2", "label": "true", "format": "social_post"},
    {"slot_id": "S3", "label": "false", "format": "scientific_prose"},
    {"slot_id": "S4", "label": "true", "format": "scientific_prose"},
]
ROLES = ("economy", "advanced")

GEN_SETTINGS = {"temperature": 0.7, "seed": 2026, "max_tokens_single": 400, "max_tokens_batch_per_example": 300}

SYSTEM_PROMPT = """You write short example passages for a university lecture on health misinformation. \
The lecturer shows every passage inside a clearly labelled classroom exercise, next to the factual \
correction that smoking is harmful, and never publishes it. Students later check each passage against \
evidence, so some slots deliberately ask for a FALSE claim.

For every slot you receive:
- Make the assigned central claim the clear main message of the passage. Keep exactly that one claim: \
do not weaken or reverse it, and do not add caveats, corrections or opposing views.
- Use the requested format and stay within the word range.
- Do not include citations, named researchers or other people, institutions, journals, DOIs, study \
names, trial results, statistics, percentages or any numbers, links or @-handles.
- Do not say that the text is an example, an exercise, false, fake, satire, misinformation or \
AI-generated. The labelling happens outside the passage.
- If you are not willing to write a slot, set "status" to "declined" and "passage" to an empty \
string. Never substitute a different claim.
Return only JSON that matches the requested structure."""

PLAIN_JSON_SUFFIX = ('\nReturn a single JSON object of the form {"examples": [{"slot_id": "...", '
                     '"status": "written" or "declined", "passage": "..."}]} and nothing else.')


# ---------------------------------------------------------------- prompts --
def slot_request(slot: dict) -> dict:
    fmt = FORMATS[slot["format"]]
    return {
        "slot_id": slot["slot_id"],
        "format": fmt["label"],
        "format_instructions": fmt["instructions"],
        "word_range": f"{fmt['min_words']}-{fmt['max_words']} words",
        "central_claim": CLAIMS[slot["label"]]["text"],
    }


def response_schema(slot_ids: list[str]) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "classroom_examples",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slot_id": {"type": "string", "enum": slot_ids},
                                "status": {"type": "string", "enum": ["written", "declined"]},
                                "passage": {"type": "string"},
                            },
                            "required": ["slot_id", "status", "passage"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["examples"],
                "additionalProperties": False,
            },
        },
    }


def build_messages(slots: list[dict], structured: bool) -> list[dict]:
    system = SYSTEM_PROMPT if structured else SYSTEM_PROMPT + PLAIN_JSON_SUFFIX
    user = ("Write one passage for each slot below.\n\nSlots:\n"
            + json.dumps([slot_request(s) for s in slots], indent=2, ensure_ascii=False))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def max_tokens_for(n_slots: int) -> int:
    if n_slots == 1:
        return GEN_SETTINGS["max_tokens_single"]
    return GEN_SETTINGS["max_tokens_batch_per_example"] * n_slots


# ------------------------------------------------------------- validation --
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def load_json_content(content: str) -> object:
    """Parse model text as JSON. Strips one surrounding ``` fence; no other repair."""
    m = _FENCE.match(content or "")
    return json.loads(m.group(1) if m else content)


def parse_generation(content: str, slots: list[dict]) -> tuple[dict, list[dict]]:
    """Return ({slot_id: passage} for valid written slots, [problems]).

    Missing, duplicate, unknown, declined, empty and malformed slots become
    problems. Valid slots are kept even when others fail.
    """
    expected = {s["slot_id"] for s in slots}
    problems: list[dict] = []
    try:
        data = load_json_content(content)
    except (ValueError, TypeError):
        return {}, [{"slot_id": s, "problem": "invalid_json"} for s in sorted(expected)]
    items = data.get("examples") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {}, [{"slot_id": s, "problem": "invalid_json"} for s in sorted(expected)]

    seen: dict[str, list[dict]] = {}
    for item in items:
        if not isinstance(item, dict):
            problems.append({"slot_id": None, "problem": "malformed_record"})
            continue
        sid = item.get("slot_id")
        if sid not in expected:
            problems.append({"slot_id": str(sid)[:20], "problem": "unknown_id"})
            continue
        seen.setdefault(sid, []).append(item)

    accepted: dict[str, str] = {}
    for sid in sorted(expected):
        got = seen.get(sid, [])
        if not got:
            problems.append({"slot_id": sid, "problem": "missing"})
            continue
        if len(got) > 1:
            problems.append({"slot_id": sid, "problem": "duplicate_id"})
            continue
        item = got[0]
        status, passage = item.get("status"), item.get("passage")
        if status not in ("written", "declined") or not isinstance(passage, str):
            problems.append({"slot_id": sid, "problem": "invalid_fields"})
        elif status == "declined":
            problems.append({"slot_id": sid, "problem": "declined"})
        elif not passage.strip():
            problems.append({"slot_id": sid, "problem": "empty"})
        else:
            accepted[sid] = passage.strip()
    return accepted, problems


PROBLEM_TEXT = {
    "invalid_json": "output was not valid JSON in the requested structure",
    "malformed_record": "a record was not a JSON object",
    "unknown_id": "a record had an unknown slot ID",
    "missing": "no record for this slot",
    "duplicate_id": "more than one record for this slot",
    "invalid_fields": "required fields missing or of the wrong type",
    "declined": "the model declined this slot (refusal)",
    "empty": "empty passage",
}

_CITATION = re.compile(r"\bet al\b|\bdoi\b|journal|universit|institut|\bstud(y|ies)\b|research|scientist|"
                       r"expert|according to|published|\btrial|evidence (shows|suggests|indicates)|observations|data (show|suggest)|"
                       r"percent|%|survey|professor|\bdr\.?\s|https?://|www\.", re.I)
_HEDGE = re.compile(r"\b(might|may|could|possibly|perhaps|some say|suggests?|appears? to|linked to|associated with)\b",
                    re.I)
_LEAK = re.compile(r"misinformation|disinformation|\bfake\b|fabricat|satire|exercise|classroom|"
                   r"\bexample\b|ai[- ]generated|not true|untrue|\bmyth", re.I)
_AGAINST_FALSE = re.compile(r"\b(harm\w*|dangerous|deadly|kills?|quit\w*|damag\w*)\b", re.I)
_AGAINST_TRUE = re.compile(r"\b(healthy|beneficial|good for you|protect\w*|lowers?|harmless|scare\w*|overblown|"
                           r"exaggerat\w*|villains?|not (that |so |really )?(dangerous|harmful|bad))\b|"
                           r"not (the )?(cigarettes?|smoking)\b", re.I)


def review_flags(passage: str, label: str, fmt: str) -> list[str]:
    """Heuristic hints for the instructor. They never accept or reject a row."""
    flags = []
    n = len(passage.split())
    f = FORMATS[fmt]
    if not f["min_words"] <= n <= f["max_words"]:
        flags.append(f"length {n} words (target {f['min_words']}-{f['max_words']})")
    if re.search(r"\d", passage):
        flags.append("contains a number")
    if _CITATION.search(passage):
        flags.append("possible invented source or evidence")
    if _LEAK.search(passage):
        flags.append("possible label leak (mentions exercise/fake/myth etc.)")
    if passage.count("#") > 2 or re.search(r"(^|\s)@\w", passage):
        flags.append("hashtags or handles beyond the format rules")
    if _HEDGE.search(passage):
        flags.append("check: hedged wording may weaken the assigned claim")
    if label == "false" and _AGAINST_FALSE.search(passage):
        flags.append("check: wording may argue against the assigned FALSE claim")
    if label == "true" and _AGAINST_TRUE.search(passage):
        flags.append("check: wording may argue against the assigned TRUE claim")
    return flags


# ----------------------------------------------------------------- records --
def make_row(*, row_id: str, source_type: str, generator_role: str | None, generator_model: str,
             slot: dict, passage: str, review_status: str, run_id: str | None, created_at: str,
             provenance: str) -> dict:
    return {
        "row_id": row_id,
        "source_type": source_type,            # live | fixture | recorded
        "provenance": provenance,
        "generator_role": generator_role,
        "generator_model": generator_model,
        "format": slot["format"],
        "intended_label": slot["label"],       # what the generator was ASKED to argue
        "claim_id": CLAIMS[slot["label"]]["claim_id"],
        "central_claim": CLAIMS[slot["label"]]["text"],
        "passage": passage,
        "review_status": review_status,        # awaiting_review | approved | excluded
        "review_note": "",
        "flags": review_flags(passage, slot["label"], slot["format"]),
        "generation_run_id": run_id,
        "created_at_utc": created_at,
        "exercise_label": EXERCISE_WARNING,
        "correction": CORRECTION,
        "correction_source": WHO_URL,
    }


def call_record(kind: str, role: str | None, res: CallResult, extra: dict | None = None) -> dict:
    rec = {"call_id": None, "kind": kind, "role": role}
    rec.update(res.to_record())
    rec.update(extra or {})
    return rec


def rows_from_generation(res: CallResult, *, role: str, slots: list[dict], run_id: str,
                         source_type: str = "live", id_prefix: str | None = None) -> tuple[list[dict], list[dict]]:
    """Turn one generation call into rows (awaiting review) and slot problems."""
    def problem_rows(kind: str, detail: str) -> list[dict]:
        return [{"generator_role": role, "generator_model": res.model_requested, "slot_id": s["slot_id"],
                 "label": s["label"], "format": s["format"], "problem": kind, "detail": detail,
                 "run_id": run_id} for s in slots]

    if not res.ok:
        return [], problem_rows(f"call_failed:{res.status}", res.message)
    accepted, problems = parse_generation(res.content or "", slots)
    by_id = {s["slot_id"]: s for s in slots}
    rows = []
    for sid, passage in accepted.items():
        slot = by_id[sid]
        prefix = id_prefix or f"{role[:3]}-{run_id}"
        rows.append(make_row(row_id=f"{prefix}-{slot['label']}-{FORMATS[slot['format']]['short']}",
                             source_type=source_type, generator_role=role,
                             generator_model=res.model_requested, slot=slot, passage=passage,
                             review_status="awaiting_review", run_id=run_id,
                             created_at=res.started_at_utc,
                             provenance=f"live OpenRouter output, {res.started_at_utc}"))
    out_problems = []
    for p in problems:
        slot = by_id.get(p["slot_id"])
        out_problems.append({"generator_role": role, "generator_model": res.model_requested,
                             "slot_id": p["slot_id"], "label": slot["label"] if slot else None,
                             "format": slot["format"] if slot else None, "problem": p["problem"],
                             "detail": PROBLEM_TEXT.get(p["problem"], p["problem"]), "run_id": run_id})
    return rows, out_problems


# ---------------------------------------------------------------- dataset --
class MixedSourceError(ValueError):
    pass


def new_dataset() -> dict:
    return {"source_type": None, "rows": [], "problems": [], "frozen": False, "frozen_hash": None,
            "frozen_order": [], "provenance": None}


def add_rows(dataset: dict, rows: list[dict], source_type: str, provenance: str | None = None) -> None:
    """Add rows of ONE source type. Live, fixture and recorded rows never mix."""
    if dataset["frozen"]:
        raise ValueError("The dataset is frozen. Unfreeze it before changing rows.")
    if dataset["source_type"] not in (None, source_type):
        raise MixedSourceError(f"The dataset holds {dataset['source_type']} rows; clear it before adding "
                               f"{source_type} rows. Fixtures, recorded and live rows never mix.")
    dataset["source_type"] = source_type
    if provenance:
        dataset["provenance"] = provenance
    dataset["rows"].extend(rows)


def replace_generator_rows(dataset: dict, role: str, rows: list[dict], problems: list[dict]) -> None:
    """A new batch for one generator replaces that generator's earlier rows and problems."""
    if dataset["frozen"]:
        raise ValueError("The dataset is frozen. Unfreeze it before generating again.")
    if dataset["source_type"] not in (None, "live"):
        raise MixedSourceError(f"The dataset holds {dataset['source_type']} rows; clear it first.")
    dataset["rows"] = [r for r in dataset["rows"] if r["generator_role"] != role]
    dataset["problems"] = [p for p in dataset["problems"] if p["generator_role"] != role]
    dataset["source_type"] = "live"
    dataset["provenance"] = "live OpenRouter output generated in this session"
    dataset["rows"].extend(rows)
    dataset["problems"].extend(problems)


def set_review(dataset: dict, row_id: str, status: str | None = None, note: str | None = None) -> None:
    """Change a review decision and/or note. None leaves that field unchanged."""
    if dataset["frozen"]:
        raise ValueError("The dataset is frozen.")
    if status is not None and status not in ("awaiting_review", "approved", "excluded"):
        raise ValueError(status)
    for r in dataset["rows"]:
        if r["row_id"] == row_id:
            if status is not None:
                r["review_status"] = status
            if note is not None:
                r["review_note"] = note
            return
    raise KeyError(row_id)


def balance_table(dataset: dict, roles=ROLES) -> list[dict]:
    """Counts per generator x label x format: generated, approved, excluded, failed."""
    out = []
    for role in roles:
        for slot in BALANCED_SLOTS:
            rows = [r for r in dataset["rows"] if r["generator_role"] == role
                    and r["intended_label"] == slot["label"] and r["format"] == slot["format"]]
            fails = [p for p in dataset["problems"] if p["generator_role"] == role
                     and p["label"] == slot["label"] and p["format"] == slot["format"]]
            out.append({"generator": role, "label": slot["label"], "format": slot["format"],
                        "generated": len(rows),
                        "approved": sum(r["review_status"] == "approved" for r in rows),
                        "awaiting_review": sum(r["review_status"] == "awaiting_review" for r in rows),
                        "excluded": sum(r["review_status"] == "excluded" for r in rows),
                        "generation_failures": len(fails)})
    return out


def balance_status(dataset: dict, per_cell: int = 1) -> tuple[bool, str]:
    table = balance_table(dataset)
    missing = [t for t in table if t["approved"] < per_cell]
    extra = [t for t in table if t["approved"] > per_cell]
    if not missing and not extra:
        return True, f"Balanced: {per_cell} approved example(s) in each of the 8 generator x label x format cells."
    parts = []
    if missing:
        parts.append(f"{len(missing)} cell(s) without an approved example")
    if extra:
        parts.append(f"{len(extra)} cell(s) with more than {per_cell}")
    return False, "Incomplete or imbalanced: " + "; ".join(parts) + "."


# --------------------------------------------------------------- fixtures --
def load_fixtures(path: Path | None = None) -> dict:
    return json.loads((path or HERE / "fixtures.json").read_text(encoding="utf-8"))


def fixture_rows(fixtures: dict) -> list[dict]:
    rows = []
    for fx in fixtures["examples"]:
        slot = {"slot_id": fx["slot_id"], "label": fx["label"], "format": fx["format"]}
        row = make_row(row_id=fx["row_id"], source_type="fixture", generator_role=fx["stands_in_for"],
                       generator_model="FIXTURE (hand-authored, not a model output)", slot=slot,
                       passage=fx["passage"], review_status="approved", run_id=None,
                       created_at=fixtures["authored"], provenance=fixtures["provenance"])
        row["review_note"] = "pre-reviewed hand-authored fixture"
        rows.append(row)
    return rows


def provider_routing(cfg: dict) -> dict:
    """Provider routing from models.json (same model, chosen endpoint), or {} for OpenRouter's default."""
    routing = cfg.get("provider_routing", {}) if isinstance(cfg, dict) else {}
    out = {}
    if isinstance(routing.get("order"), list) and routing["order"]:
        out["order"] = [str(x) for x in routing["order"]]
    if isinstance(routing.get("allow_fallbacks"), bool):
        out["allow_fallbacks"] = routing["allow_fallbacks"]
    return out


def load_models_config(path: Path | None = None) -> tuple[dict, str | None]:
    """Read models.json. Returns (config, problem) and never guesses IDs."""
    p = path or HERE / "models.json"
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
        ids = {r: cfg[r]["id"] for r in ROLES}
        if not all(isinstance(v, str) and v.strip() for v in ids.values()):
            raise KeyError("id")
        return cfg, None
    except FileNotFoundError:
        return {}, "models.json not found: preflight incomplete. Enter model IDs manually."
    except (ValueError, KeyError, TypeError):
        return {}, "models.json is unreadable or lacks economy/advanced IDs: preflight incomplete."


# ------------------------------------------------------------------ export --
def export_bundle(state: dict, app_version: str, extra: dict | None = None) -> str:
    """Wrapped JSON export. Holds the educational context and no secrets."""
    bundle = {
        "exercise_warning": EXERCISE_WARNING,
        "correction": CORRECTION,
        "correction_source": WHO_URL,
        "notice": ("Teaching material. 'intended_label' is what a generator was asked to argue; it is "
                   "not independently verified truth. Live rows count only after instructor review."),
        "exported_at_utc": now_utc(),
        "app_version": app_version,
        "claims": CLAIMS,
        "formats": FORMATS,
        "dataset": copy.deepcopy(state.get("dataset")),
        "single_examples": copy.deepcopy(state.get("singles", [])),
        "calls": copy.deepcopy(state.get("calls", [])),
    }
    bundle.update(extra or {})
    return json.dumps(bundle, indent=2, ensure_ascii=False)


def short_hash(*parts: str, n: int = 8) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:n]
