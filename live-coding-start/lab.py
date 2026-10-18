"""High-level helpers for the live-coded app: one import, no Streamlit code here.

The app built live in the lecture (app.py) needs only this module. It wraps the
tested kit modules:

    openrouter_client.py  one HTTP request per call, no retries, sanitized errors
    generation.py         claims, formats, balanced design, parsing, review flags, export
    detection.py          evidence packet, blinding/freezing, verdict parsing, metrics

Every function that costs money says so in its docstring ("ONE paid call").
Nothing here reads widgets or session_state, so a Streamlit rerun never calls a
model unless the app calls one of these functions after a button press.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from dotenv import dotenv_values

import detection as det
import generation as gen
import openrouter_client as orc

HERE = Path(__file__).parent
APP_VERSION = "live-coded app on the lecture starter kit, 2026-10-18"

# Re-exported constants the UI shows.
EXERCISE_WARNING = gen.EXERCISE_WARNING
CORRECTION = gen.CORRECTION
WHO_URL = gen.WHO_URL
ROLES = gen.ROLES                      # ("economy", "advanced")
FORMATS = gen.FORMATS                  # {"social_post": {...}, "scientific_prose": {...}}
LABEL_NAMES = gen.LABEL_NAMES          # {"true": "TRUE claim (supported)", "false": "FALSE claim (contradicted)"}
CLAIMS = gen.CLAIMS
EVIDENCE_PACKET = det.EVIDENCE_PACKET
VERDICTS = det.VERDICTS
fmt_rate = det.fmt_rate                # {"num", "den", "value"} -> "3/4 = 75%" or "N/A"
cost_text_unavailable = "unavailable (not returned)"

DETECTION_NOTE = (
    "Evidence-assisted factual-claim assessment: both detectors get the same short WHO evidence packet, "
    "the same instructions and the same frozen passages. This is not web research, not an AI-authorship "
    "detector and not a validated fake-news classifier.")
SMALL_SAMPLE_NOTE = (
    "Small demonstration. Larger or more capable models are not guaranteed to write harder-to-detect "
    "misinformation or to give better verdicts. With 4 items per generator, one answer moves cell accuracy "
    "by 25 percentage points; with 2 items per truth label, one answer moves recall or the false-positive "
    "rate by 50 points. A familiar tobacco claim and the writing style may dominate the result.")
SCORING_NOTE = (
    "False claims are the positive class; 'contradicted' is a positive prediction. "
    "'insufficient_evidence' is an abstention, never a correct answer. Failures are not predictions. "
    "Overall success counts abstentions and failures as unsuccessful.")


# ------------------------------------------------------------ config/key --
def load_models() -> tuple[dict, str | None]:
    """Read models.json. Returns (config, problem). Never guesses model IDs."""
    return gen.load_models_config()


def default_model_ids(cfg: dict) -> dict:
    """{"economy": id, "advanced": id} from models.json, or "" when missing."""
    return {role: cfg.get(role, {}).get("id", "") for role in ROLES}


def routing(cfg: dict) -> dict:
    """Same-model endpoint routing from models.json, sent as the request's provider field."""
    return gen.provider_routing(cfg)


def documented_size(cfg: dict, model: str) -> str:
    for role in ROLES:
        if cfg.get(role, {}).get("id") == model:
            return cfg[role].get("documented_size", "size not documented")
    return "size not documented for this ID (do not call it small or large)"


def _structured_ok(cfg: dict, model: str) -> bool:
    verified = {cfg[r]["id"] for r in ROLES if r in cfg}
    return model in verified and "structured_outputs" in cfg.get("preflight", {}).get("supported_parameters_both", [])


def get_api_key(secrets: Any = None) -> tuple[str | None, str | None]:
    """(key, source): environment, then .env next to this file, then Streamlit secrets.

    Pass st.secrets as `secrets`. The key must never be printed, stored in
    session_state or exported.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key, "environment variable"
    key = str(dotenv_values(HERE / ".env").get("OPENROUTER_API_KEY") or "").strip()
    if key:
        return key, ".env file"
    try:
        key = str((secrets or {}).get("OPENROUTER_API_KEY", "")).strip()
    except Exception:  # no secrets file, or an unreadable one
        key = ""
    return (key, "Streamlit secrets") if key else (None, None)


def cost_text(cost: Any) -> str:
    return f"US${cost:.6f}" if isinstance(cost, (int, float)) else cost_text_unavailable


# ------------------------------------------------------------- generation --
def single_slot(label: str, fmt: str) -> list[dict]:
    """One assignment: label "true"/"false", fmt "social_post"/"scientific_prose"."""
    if label not in CLAIMS or fmt not in FORMATS:
        raise ValueError("label must be 'true' or 'false', fmt a key of FORMATS")
    return [{"slot_id": "S1", "label": label, "format": fmt}]


def balanced_slots() -> list[dict]:
    """The four assignments each generator gets: TRUE/FALSE x social/science."""
    return gen.balanced_slots()


def generate(api_key: str | None, role: str, model: str, slots: list[dict], cfg: dict) -> dict:
    """ONE paid call to one generator for the given slots.

    Returns {"rows": [...], "problems": [...], "call": {...}, "ok": bool, "message": str}.
    Rows start as "awaiting_review"; the intended label is kept apart from the passage.
    A failed call is never retried and never replaced by another model.
    """
    model = (model or "").strip()
    structured = _structured_ok(cfg, model)
    res = orc.chat_completion(
        api_key, model, gen.build_messages(slots, structured),
        max_tokens=gen.max_tokens_for(len(slots)),
        temperature=gen.GEN_SETTINGS["temperature"], seed=gen.GEN_SETTINGS["seed"],
        response_format=gen.response_schema([s["slot_id"] for s in slots]) if structured else None,
        provider=routing(cfg))
    run_id = gen.short_hash(role, model, res.started_at_utc, str(len(slots)), n=6)
    rows, problems = gen.rows_from_generation(res, role=role, slots=slots, run_id=run_id)
    call = gen.call_record("generate", role, res, {"run_id": run_id})
    msg = (f"{role} generator: {len(rows)}/{len(slots)} passage(s), {res.elapsed_s} s, cost {cost_text(res.cost_usd)}"
           + ("" if res.ok else f". {res.message}"))
    return {"rows": rows, "problems": problems, "call": call, "ok": res.ok and not problems, "message": msg}


def new_dataset() -> dict:
    """{"source_type", "rows", "problems", "frozen", ...}. Keep it in st.session_state."""
    return gen.new_dataset()


def store_generation(dataset: dict, role: str, result: dict) -> None:
    """A new balanced batch for one generator replaces that generator's earlier rows."""
    gen.replace_generator_rows(dataset, role, result["rows"], result["problems"])


def load_fixtures(dataset: dict) -> None:
    """Add the 8 hand-authored offline fixtures (pre-approved, clearly marked, not model output).

    Raises generation.MixedSourceError if the dataset already holds live rows.
    """
    fx = gen.load_fixtures()
    gen.add_rows(dataset, gen.fixture_rows(fx), "fixture", fx["provenance"])


def set_review(dataset: dict, row_id: str, status: str | None = None, note: str | None = None) -> None:
    """status: "awaiting_review" | "approved" | "excluded". Raises if the dataset is frozen."""
    gen.set_review(dataset, row_id, status, note)


def balance_table(dataset: dict) -> list[dict]:
    """8 rows: generator x label x format with generated/approved/excluded/failure counts."""
    return gen.balance_table(dataset)


def balance_status(dataset: dict) -> tuple[bool, str]:
    return gen.balance_status(dataset)


def export_json(dataset: dict, singles: list | None = None, calls: list | None = None,
                detections: dict | None = None, pasted: list | None = None) -> str:
    """Wrapped JSON export with the exercise warning and correction. Contains no key."""
    extra = {"detections": detections or {}, "pasted_assessments": pasted or [],
             "evidence_packet": EVIDENCE_PACKET, "scoring_note": SCORING_NOTE}
    return gen.export_bundle({"dataset": dataset, "singles": singles or [], "calls": calls or []},
                             APP_VERSION, extra)


# -------------------------------------------------------------- detection --
def freeze(dataset: dict) -> None:
    """Freeze the approved rows (max 8): fixed hash, deterministic shuffled order, blind IDs. No network."""
    det.freeze(dataset)


def unfreeze(dataset: dict) -> None:
    det.unfreeze(dataset)


NO_REVIEW_NOTE = "no review step (simplified classroom flow): every generated row is assessed"


def freeze_all(dataset: dict) -> None:
    """Simplified flow without a review step: take every row, then freeze it. No network.

    Re-freezes if the dataset was already frozen, so it always matches the current rows. The blinding is the
    same as with freeze(): detectors see only blind IDs and passages. Raises ValueError for no rows or more than 8.
    """
    if dataset.get("frozen"):
        det.unfreeze(dataset)
    for r in dataset["rows"]:
        if r["review_status"] != "approved":
            r["review_status"] = "approved"
            r["review_note"] = r.get("review_note") or NO_REVIEW_NOTE
    det.freeze(dataset)


def fake_news_label(result: dict | None) -> str:
    """Plain-language reading of one verdict: contradicted = fake news, supported = not fake news."""
    if not result:
        return "not run"
    if result.get("status") != "predicted":
        return "failure (no valid answer)"
    return {"contradicted": "FAKE NEWS (contradicted by the evidence)",
            "supported": "not fake news (supported by the evidence)",
            "insufficient_evidence": "unsure (insufficient evidence)"}[result["verdict"]]


def frozen_rows(dataset: dict) -> list[dict]:
    """The frozen rows in the frozen (shuffled) order, each with its blind ID under "blind_id"."""
    by_id = {r["row_id"]: r for r in dataset["rows"]}
    return [{**by_id[rid], "blind_id": dataset["blind_ids"][rid]} for rid in dataset.get("frozen_order", [])]


def detector_input(dataset: dict) -> list[dict]:
    """Exactly what a detector receives: [{"id": blind_id, "text": passage}]. Nothing else."""
    return det.frozen_items(dataset)


def detect(api_key: str | None, role: str, model: str, dataset: dict, cfg: dict) -> dict:
    """ONE paid call: one detector assesses every frozen passage.

    Sends only blind IDs, passages, the evidence packet and fixed instructions.
    Returns {"kind": "live", "detector_model", "results": {row_id: {...}}, "problems",
    "call", "ok", "message"}. Each result is {"status": "predicted", "verdict", "reason",
    "evidence_ref"} or {"status": "failure", "failure_kind", "detail"}.
    """
    if not dataset.get("frozen"):
        raise ValueError("Freeze the dataset before running a detector.")
    model = (model or "").strip()
    items = det.frozen_items(dataset)
    structured = _structured_ok(cfg, model)
    res = orc.chat_completion(
        api_key, model, det.build_messages(items, structured),
        max_tokens=det.max_tokens_for(len(items)),
        temperature=det.DET_SETTINGS["temperature"], seed=det.DET_SETTINGS["seed"],
        response_format=det.response_schema([it["id"] for it in items]) if structured else None,
        provider=routing(cfg))
    results, problems = det.results_from_call(res, dataset)
    n_ok = sum(v["status"] == "predicted" for v in results.values())
    msg = (f"{role} detector: {n_ok}/{len(items)} valid assessments, {res.elapsed_s} s, cost {cost_text(res.cost_usd)}"
           + ("" if res.ok else f". {res.message}"))
    return {"kind": "live", "role": role, "detector_model": model, "frozen_hash": dataset["frozen_hash"],
            "results": results, "problems": problems, "ok": n_ok == len(items), "message": msg,
            "call": gen.call_record("detect", role, res, {"frozen_hash": dataset["frozen_hash"]})}


def illustrative_detections(dataset: dict) -> dict:
    """Offline only: hand-authored verdicts for the frozen FIXTURE rows. NOT measured.

    Returns {role: detection} shaped like detect(); kind is "illustrative".
    """
    if dataset.get("source_type") != "fixture" or not dataset.get("frozen"):
        raise ValueError("Illustrative verdicts need the frozen offline fixtures.")
    fx = gen.load_fixtures()
    out = {}
    for role in ROLES:
        verdicts = {v["row_id"]: v for v in fx["illustrative_verdicts"][role]}
        results = {}
        for rid in dataset["frozen_order"]:
            v = verdicts.get(rid)
            results[rid] = ({"status": "predicted", "verdict": v["verdict"], "reason": v["reason"],
                             "evidence_ref": v["evidence_ref"]} if v else
                            {"status": "failure", "failure_kind": "format", "detail": "illustrative missing assessment"})
        out[role] = {"kind": "illustrative", "role": role, "detector_model": "ILLUSTRATIVE (hand-authored, NOT measured)",
                     "frozen_hash": dataset["frozen_hash"], "results": results, "problems": [], "ok": True,
                     "message": "illustrative verdicts (hand-authored, NOT measured)", "call": None}
    return out


def matrix(dataset: dict, detections: Mapping[str, dict]) -> dict:
    """{(generator_role, detector_role): metrics or None} for the 2x2 comparison.

    metrics: correct, eligible, answered, abstentions, failures, tp/fn/fp/tn, n_false, n_true,
    overall_success, coverage, false_claim_recall, false_positive_rate, answered_accuracy
    (rates are {"num", "den", "value"}; format them with fmt_rate), balanced.
    """
    frozen = set(dataset.get("frozen_order", []))
    out = {}
    for g in ROLES:
        rows = [r for r in dataset["rows"] if r["row_id"] in frozen and r["generator_role"] == g]
        for d in ROLES:
            dres = detections.get(d)
            out[(g, d)] = det.cell_metrics(rows, dres["results"]) if dres else None
    return out


def cell_summary(m: dict | None) -> str:
    """Markdown text for one matrix cell, always with denominators."""
    if m is None:
        return "_not run_"
    return (f"**{m['correct']}/{m['eligible']} correct** (overall success {fmt_rate(m['overall_success'])})  \n"
            f"coverage {fmt_rate(m['coverage'])} · abstentions {m['abstentions']} · failures {m['failures']}  \n"
            f"false-claim recall {fmt_rate(m['false_claim_recall'])}  \n"
            f"false positives {m['fp']} of {m['n_true']} true (rate {fmt_rate(m['false_positive_rate'])})  \n"
            f"answered-only accuracy {fmt_rate(m['answered_accuracy'])}"
            + ("" if m["balanced"] else "  \n**imbalanced cell**"))


def is_correct(row: dict, result: dict | None) -> bool | None:
    """True/False for an answered item, None for an abstention or failure."""
    return det.is_correct(row, result)


def assess_pasted(api_key: str | None, role: str, model: str, text: str, cfg: dict) -> dict:
    """ONE paid call: assess one pasted passage. Verdict only; it never enters any score.

    Returns {"role", "detector_model", "status": "predicted"|"failure", "verdict", "reason",
    "evidence_ref", "detail", "call", "message"}.
    """
    model = (model or "").strip()
    items = [{"id": "X1", "text": (text or "").strip()}]
    structured = _structured_ok(cfg, model)
    res = orc.chat_completion(
        api_key, model, det.build_messages(items, structured),
        max_tokens=det.max_tokens_for(1),
        temperature=det.DET_SETTINGS["temperature"], seed=det.DET_SETTINGS["seed"],
        response_format=det.response_schema(["X1"]) if structured else None,
        provider=routing(cfg))
    out = {"role": role, "detector_model": model, "passage": items[0]["text"], "scored": False,
           "call": gen.call_record("assess_pasted", role, res)}
    if not res.ok:
        out.update(status="failure", detail=f"{res.status}: {res.message}")
    else:
        preds, problems = det.parse_assessments(res.content or "", ["X1"])
        if "X1" in preds:
            out.update(status="predicted", **preds["X1"])
        else:
            out.update(status="failure", detail="; ".join(det.PROBLEM_TEXT.get(p["problem"], p["problem"])
                                                          for p in problems))
    out["message"] = (f"{role} detector on pasted passage: {out.get('verdict', 'failure')}, {res.elapsed_s} s, "
                      f"cost {cost_text(res.cost_usd)}")
    return out
