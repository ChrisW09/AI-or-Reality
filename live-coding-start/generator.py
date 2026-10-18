"""Non-UI logic for the classroom misinformation generator (OpenRouter + offline fixtures).

Classroom exercise only: generated passages about "cigarettes are healthy" are deliberate
misinformation. Smoking is harmful. This module never stores, logs or exports an API key.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

EXERCISE_WARNING = (
    "CLASSROOM EXERCISE: This page contains deliberately generated health misinformation "
    "for teaching. Do not share or publish any passage. Smoking is harmful to health."
)
CORRECTION_TEXT = (
    "Fact: Tobacco smoking is harmful. It kills up to half of its users and causes cancer, "
    "heart disease, stroke and lung disease. Cigarettes are not healthy."
)
WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/tobacco"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TIMEOUT_SECONDS = (10, 60)  # (connect, read)
MAX_TOKENS_SINGLE = 300
MAX_TOKENS_BATCH = 1200
DEFAULT_TEMPERATURE = 0.7
LABEL_NOTE = "Intended label set by the exercise design; not independently verified truth."

CLAIMS: Dict[str, dict] = {
    "CLAIM_SUPPORTED": {
        "claim_id": "CLAIM_SUPPORTED", "stance": "supported", "intended_truth": "true",
        "claim_text": "Smoking cigarettes is harmful to health and causes diseases such as "
                      "lung cancer and heart disease.",
        "source_url": WHO_URL,
    },
    "CLAIM_CONTRADICTED": {
        "claim_id": "CLAIM_CONTRADICTED", "stance": "contradicted", "intended_truth": "false",
        "claim_text": "Smoking cigarettes is healthy.",
        "source_url": WHO_URL,
    },
}

FORMATS: Dict[str, dict] = {
    "social_post": {"label": "Social media post", "max_words": 50},
    "scientific_prose": {"label": "Short scientific-style prose", "max_words": 80},
}

ASSIGNMENTS: List[dict] = [
    {"slot_id": "S1", "claim_id": "CLAIM_SUPPORTED", "format": "social_post"},
    {"slot_id": "S2", "claim_id": "CLAIM_SUPPORTED", "format": "scientific_prose"},
    {"slot_id": "S3", "claim_id": "CLAIM_CONTRADICTED", "format": "social_post"},
    {"slot_id": "S4", "claim_id": "CLAIM_CONTRADICTED", "format": "scientific_prose"},
]

MODEL_ROLES = ("economy", "advanced")
_HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- small helpers
def utc_now() -> str:
    """Current UTC time, ISO 8601 with a trailing Z (seconds precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_batch_id() -> str:
    """Batch id like 'B20261018T120000Z-1a2b3c'."""
    return "B" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def _resolve(path: str) -> str:
    """Use the path as given; if relative and missing, try next to this module."""
    if os.path.isabs(path) or os.path.exists(path):
        return path
    return os.path.join(_HERE, path)


def _clean_routing(routing: Any) -> Optional[dict]:
    """Keep only 'order' and 'allow_fallbacks' of a provider routing object."""
    if not isinstance(routing, dict) or "order" not in routing:
        return None
    return {"order": list(routing.get("order") or []),
            "allow_fallbacks": bool(routing.get("allow_fallbacks", False))}


# ---------------------------------------------------------------- config / key
def load_models(path: str = "models.json") -> dict:
    """Read the non-secret preflight file with the economy and advanced model ids."""
    out = {"preflight_complete": False, "economy_id": None, "advanced_id": None,
           "provider_routing": None, "info": {}, "message": ""}
    try:
        with open(_resolve(path), encoding="utf-8") as fh:
            info = json.load(fh)
    except FileNotFoundError:
        out["message"] = "Preflight incomplete: models.json was not found."
        return out
    except (OSError, ValueError):
        out["message"] = "Preflight incomplete: models.json could not be read as JSON."
        return out
    if not isinstance(info, dict):
        out["message"] = "Preflight incomplete: models.json is not a JSON object."
        return out
    out["info"] = info
    ids = {}
    for role in MODEL_ROLES:
        entry = info.get(role)
        mid = entry.get("id") if isinstance(entry, dict) else None
        ids[role] = mid.strip() if isinstance(mid, str) and mid.strip() else None
    missing = [r for r in MODEL_ROLES if ids[r] is None]
    if missing:
        out["message"] = "Preflight incomplete: models.json is missing the id for: " + ", ".join(missing) + "."
        return out
    out.update(preflight_complete=True, economy_id=ids["economy"], advanced_id=ids["advanced"],
               provider_routing=_clean_routing(info.get("provider_routing")),
               message="Preflight complete: model ids loaded from models.json.")
    return out


def get_api_key(env: Optional[dict] = None, secrets: Any = None) -> Optional[str]:
    """Return OPENROUTER_API_KEY from env (default os.environ), else from secrets; never logs."""
    env = os.environ if env is None else env
    key = env.get("OPENROUTER_API_KEY")
    if isinstance(key, str) and key.strip():
        return key.strip()
    if secrets is not None:
        try:
            key = secrets["OPENROUTER_API_KEY"]
            if isinstance(key, str) and key.strip():
                return key.strip()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- prompt
def build_messages(assignments: List[dict]) -> List[dict]:
    """System + user messages with identical constraints for any model."""
    system = (
        "You are helping with a university classroom exercise on health misinformation. "
        "Students will later try to tell passages apart; an instructor reviews every passage "
        "and nothing is published. Follow the assignment table exactly."
    )
    rows = []
    for a in assignments:
        claim, fmt = CLAIMS[a["claim_id"]], FORMATS[a["format"]]
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            a["slot_id"], a["claim_id"], claim["claim_text"], a["format"], fmt["label"], fmt["max_words"]))
    user = "\n".join([
        "Classroom exercise. Write exactly one passage per assignment below.",
        "Rules:",
        "1. Each passage must assert its assigned claim; keep the claim's stance unchanged "
        "(do not soften, reverse, correct or add disclaimers to it).",
        "2. Respect max_words for each passage.",
        "3. Do not invent citations, researchers, institutions, DOIs, numerical findings or statistics. "
        "No percentages and no 'a study found' statements.",
        "4. No hashtags, no links, no calls to share, like or forward.",
        "5. Copy slot_id, claim_id and format exactly from the table.",
        '6. Return ONLY JSON of the form {"records": [{"slot_id": "...", "claim_id": "...", '
        '"format": "...", "passage": "..."}]} with one record per assignment and no other text.',
        "",
        "| slot_id | claim_id | claim_text | format | format_label | max_words |",
        "|---|---|---|---|---|---|",
    ] + rows)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def response_format_schema() -> dict:
    """OpenRouter structured-output response_format (strict JSON schema)."""
    record = {
        "type": "object",
        "properties": {k: {"type": "string"} for k in ("slot_id", "claim_id", "format", "passage")},
        "required": ["slot_id", "claim_id", "format", "passage"],
        "additionalProperties": False,
    }
    return {"type": "json_schema", "json_schema": {
        "name": "classroom_records", "strict": True,
        "schema": {"type": "object", "properties": {"records": {"type": "array", "items": record}},
                   "required": ["records"], "additionalProperties": False}}}


# ---------------------------------------------------------------- API call
def _result(**kw: Any) -> dict:
    base = {"ok": False, "content": None, "finish_reason": None, "usage": None, "cost_usd": None,
            "provider": None, "response_model": None, "http_status": None, "error": None}
    base.update(kw)
    return base


def _status_message(status: int) -> str:
    if status in (401, 403):
        return "HTTP {}: invalid or unauthorized API credentials.".format(status)
    if status == 402:
        return "HTTP 402: insufficient OpenRouter credits."
    if status == 429:
        return "HTTP 429: rate-limited. No automatic retry was made and no other model was used."
    if status == 400:
        return "HTTP 400: request rejected by OpenRouter."
    if status >= 500:
        return "HTTP {}: provider error.".format(status)
    return "HTTP {}: request failed.".format(status)


def _redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return text[:200]


def call_openrouter(api_key: str, model_id: str, messages: List[dict], max_tokens: int,
                    temperature: float = 0.7, provider_routing: Optional[dict] = None,
                    session: Any = None) -> dict:
    """Exactly one POST to OpenRouter; no retries, no fallback models. Errors are sanitized."""
    if not api_key:
        return _result(error="No API key found. Set OPENROUTER_API_KEY in the environment or Streamlit secrets.")
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "response_format": response_format_schema(),
            "usage": {"include": True}}
    if provider_routing is not None:
        body["provider"] = provider_routing
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
               "X-Title": "AI or Reality classroom"}
    poster = session.post if session is not None else requests.post
    try:
        resp = poster(OPENROUTER_URL, headers=headers, json=body, timeout=TIMEOUT_SECONDS)
    except requests.Timeout:
        return _result(error="Request timed out (connect 10 s / read 60 s). No retry was made.")
    except requests.ConnectionError:
        return _result(error="Network error: could not reach OpenRouter. No retry was made.")
    except requests.RequestException:
        return _result(error="Request failed before a response was received. No retry was made.")

    status = getattr(resp, "status_code", None)
    try:
        data = resp.json()
    except Exception:
        data = None
    if status != 200:
        msg = _status_message(int(status or 0))
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            msg += " Detail: " + _redact(err["message"], api_key)
        return _result(http_status=status, error=msg)
    if not isinstance(data, dict):
        return _result(http_status=status, error="OpenRouter returned a non-JSON response.")

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    cost = usage.get("cost") if usage else None
    meta = {"http_status": status, "usage": usage, "provider": data.get("provider"),
            "response_model": data.get("model"),
            "cost_usd": float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None}
    if isinstance(data.get("error"), dict):
        return _result(error="API error: " + _redact(str(data["error"].get("message", "")), api_key), **meta)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return _result(error="empty output: no choices returned.", **meta)
    choice = choices[0]
    finish = choice.get("finish_reason")
    meta["finish_reason"] = finish
    if choice.get("error"):
        cerr = choice["error"]
        detail = cerr.get("message", "") if isinstance(cerr, dict) else str(cerr)
        return _result(error="Model error: " + _redact(str(detail), api_key), **meta)
    content = (choice.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        return _result(error="empty output: the model returned no content.", **meta)
    meta["content"] = content
    if finish == "length":
        return _result(error="output truncated at max_tokens; records were not used.", **meta)
    return _result(ok=True, **meta)


# ---------------------------------------------------------------- validation
_REFUSAL_RE = re.compile(r"I can['’]t|I cannot|I['’]m sorry|I am unable|as an AI|I won['’]t",
                         re.IGNORECASE)
_CITATION_RES = [
    (re.compile(r"10\.\d{4,}/"), "DOI"),
    (re.compile(r"\bet al\b", re.IGNORECASE), "'et al'"),
    (re.compile(r"doi:", re.IGNORECASE), "'doi:'"),
    (re.compile(r"\d+(\.\d+)?\s?%"), "percentage"),
    (re.compile(r"study (published|found)[^.]*\d", re.IGNORECASE), "study with numbers"),
]
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*(.*?)\s*```$", re.DOTALL)


def check_passage(passage: Any, max_words: int) -> Optional[str]:
    """Return a rejection reason for one passage, or None if it is acceptable."""
    if not isinstance(passage, str) or not passage.strip():
        return "passage missing or empty"
    words = len(passage.split())
    if words > max_words:
        return "too long ({} words > {})".format(words, max_words)
    if _REFUSAL_RE.search(passage):
        return "looks like a refusal"
    for rx, name in _CITATION_RES:
        if rx.search(passage):
            return "invented-citation pattern ({})".format(name)
    return None


def parse_and_validate(content: str, assignments: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Parse model JSON and split records into (accepted, rejected) against the assignments."""
    text = (content or "").strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return [], [{"slot_id": None, "reason": "invalid JSON"}]
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return [], [{"slot_id": None, "reason": "missing 'records' list"}]

    expected = {a["slot_id"]: a for a in assignments}
    by_slot: Dict[str, List[dict]] = {}
    rejected: List[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            rejected.append({"slot_id": None, "reason": "malformed record"})
            continue
        sid = rec.get("slot_id")
        if sid not in expected:
            rejected.append({"slot_id": sid, "reason": "unknown slot_id", "passage": rec.get("passage")})
            continue
        by_slot.setdefault(sid, []).append(rec)

    accepted: List[dict] = []
    for a in assignments:
        sid = a["slot_id"]
        recs = by_slot.get(sid, [])
        if not recs:
            rejected.append({"slot_id": sid, "reason": "missing"})
            continue
        if len(recs) > 1:
            for r in recs:
                rejected.append({"slot_id": sid, "reason": "duplicate slot_id", "passage": r.get("passage")})
            continue
        rec, passage = recs[0], recs[0].get("passage")
        if rec.get("claim_id") != a["claim_id"]:
            reason = "changed claim"  # type: Optional[str]
        elif rec.get("format") != a["format"]:
            reason = "changed format"
        else:
            reason = check_passage(passage, FORMATS[a["format"]]["max_words"])
        if reason:
            rejected.append({"slot_id": sid, "reason": reason, "passage": passage})
        else:
            accepted.append({"slot_id": sid, "claim_id": a["claim_id"], "format": a["format"],
                             "passage": passage.strip()})
    return accepted, rejected


# ---------------------------------------------------------------- rows
def make_row(passage: str, assignment: dict, *, source: str, model_role: str,
             model_id: Optional[str], settings: dict, batch_id: str,
             generated_at_utc: str, usage: Optional[dict] = None,
             cost_usd: Optional[float] = None, provider: Optional[str] = None) -> dict:
    """Build one dataset row with separate passage, generator, label and correction fields."""
    if source not in ("live", "offline_fixture"):
        raise ValueError("source must be 'live' or 'offline_fixture'")
    claim, slot_id = CLAIMS[assignment["claim_id"]], assignment["slot_id"]
    return {
        "row_id": "{}-{}-{}".format(batch_id, model_role, slot_id),
        "passage": passage,
        "generator": {"source": source, "model_role": model_role, "model_id": model_id,
                      "settings": dict(settings), "batch_id": batch_id,
                      "generated_at_utc": generated_at_utc, "usage": usage,
                      "cost_usd": cost_usd, "provider": provider},
        "label": {"slot_id": slot_id, "claim_id": claim["claim_id"], "stance": claim["stance"],
                  "intended_truth": claim["intended_truth"], "claim_text": claim["claim_text"],
                  "format": assignment["format"], "label_note": LABEL_NOTE},
        "review_status": "awaiting_instructor_review" if source == "live"
                         else "offline_fixture_not_a_measurement",
        "correction": {"text": CORRECTION_TEXT, "url": WHO_URL},
        "exercise_wrapper": {"warning": EXERCISE_WARNING,
                             "context": "Classroom health-misinformation exercise"},
    }


def passage_only(row: dict) -> str:
    """The only field a later classifier may receive."""
    return row["passage"]


def load_fixtures(path: str = "fixtures/offline_fixtures.json") -> List[dict]:
    """Load the 8 hand-written offline fixtures as full rows; ValueError if not balanced."""
    with open(_resolve(path), encoding="utf-8") as fh:
        data = json.load(fh)
    fixtures = data.get("fixtures") if isinstance(data, dict) else None
    if not isinstance(fixtures, list):
        raise ValueError("Fixture file has no 'fixtures' list.")
    by_slot = {a["slot_id"]: a for a in ASSIGNMENTS}
    seen: Dict[Tuple[str, str], str] = {}
    for fx in fixtures:
        key = (fx.get("model_role"), fx.get("slot_id"))
        if key[0] not in MODEL_ROLES or key[1] not in by_slot:
            raise ValueError("Unknown fixture role/slot: {}".format(key))
        if key in seen:
            raise ValueError("Duplicate fixture for {}".format(key))
        seen[key] = fx.get("passage", "")
    if len(seen) != len(MODEL_ROLES) * len(ASSIGNMENTS):
        raise ValueError("Fixtures are not balanced: each role must cover all slots exactly once.")
    written = data.get("written_at_utc", "")
    return [make_row(seen[(role, a["slot_id"])], a, source="offline_fixture", model_role=role,
                     model_id=None, settings={"note": "hand-written offline fixture"},
                     batch_id="OFFLINE", generated_at_utc=written)
            for role in MODEL_ROLES for a in ASSIGNMENTS]


def comparison_rows(rows: List[dict]) -> Tuple[List[dict], Optional[str]]:
    """Rows usable for a measured comparison (live only), or ([], reason)."""
    live = [r for r in rows if r.get("generator", {}).get("source") == "live"]
    if len(live) == len(rows):  # all live (or no rows at all)
        return live, None
    if not live:
        return [], "Offline fixtures are not measurements; no comparison."
    return [], "Cannot mix offline fixtures and live rows in a measured comparison."


def build_export(rows: List[dict], models_info: Optional[dict] = None) -> dict:
    """Export payload; never takes or contains an API key."""
    models = None
    if isinstance(models_info, dict):
        if "economy_id" in models_info or "advanced_id" in models_info:
            eco, adv = models_info.get("economy_id"), models_info.get("advanced_id")
        else:  # raw models.json content
            eco = (models_info.get("economy") or {}).get("id")
            adv = (models_info.get("advanced") or {}).get("id")
        models = {"economy_id": eco, "advanced_id": adv,
                  "provider_routing": _clean_routing(models_info.get("provider_routing"))}
    return {
        "exercise_context": {
            "warning": EXERCISE_WARNING,
            "correction": {"text": CORRECTION_TEXT, "url": WHO_URL},
            "notice": "Do not publish or share. Intended labels are not independently verified truth.",
            "exported_at_utc": utc_now(),
        },
        "models": models,
        "rows": rows,
    }
