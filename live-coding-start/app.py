"""Streamlit UI for the classroom misinformation generator.

All non-UI logic lives in generator.py. OpenRouter is called only inside
`if submitted:` of a form, so changing a widget never generates anything.
"""
import json
import os
from typing import Any, Dict, List, Optional

import streamlit as st

import generator as g

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = ["economy", "advanced"]
TEMPERATURE = 0.7

st.set_page_config(page_title="AI or Reality? Generator", layout="wide")
st.error(f"**{g.EXERCISE_WARNING}**\n\n{g.CORRECTION_TEXT}\n\nSource: [WHO tobacco fact sheet]({g.WHO_URL})")

st.session_state.setdefault("rows", [])
st.session_state.setdefault("calls", [])


def _safe_secrets() -> Any:
    """st.secrets as a plain dict, or None if there is no secrets.toml."""
    try:
        return dict(st.secrets)
    except Exception:
        return None


def _cost(cost_usd: Optional[float]) -> str:
    return f"${cost_usd:.6f}" if cost_usd is not None else "Cost not returned by API"


def _add_rows(rows: List[dict]) -> None:
    known = {r["row_id"] for r in st.session_state.rows}
    st.session_state.rows.extend(r for r in rows if r["row_id"] not in known)


def _fixtures() -> Optional[List[dict]]:
    try:
        return g.load_fixtures(os.path.join(HERE, "fixtures", "offline_fixtures.json"))
    except Exception as exc:  # missing or unbalanced fixture file
        st.error(f"Could not load offline fixtures: {exc}")
        return None


# ---------------------------------------------------------------- sidebar
models = g.load_models(os.path.join(HERE, "models.json"))
with st.sidebar:
    st.header("Settings")
    live = st.radio("Mode", ["Offline fixtures", "Live (OpenRouter)"]).startswith("Live")
    if not models["preflight_complete"]:
        st.warning(models["message"])
    model_ids: Dict[str, str] = {}
    for role in ROLES:
        model_ids[role] = st.text_input(f"{role.capitalize()} model ID", value=models[f"{role}_id"] or "").strip()
        st.code(model_ids[role] or "(empty)", language=None)
    if models["provider_routing"]:
        st.caption("Provider routing (sent as `provider`)")
        st.json(models["provider_routing"])
    api_key = g.get_api_key(secrets=_safe_secrets())
    st.write("API key: found" if api_key else "API key: not found")
    if st.button("Clear session data"):
        st.session_state.rows, st.session_state.calls = [], []
        st.rerun()


def _live_blocker() -> Optional[str]:
    if not api_key:
        return ("Live mode needs OPENROUTER_API_KEY (environment variable or .streamlit/secrets.toml). "
                "No API key found, so no call was made.")
    missing = [r for r in ROLES if not model_ids[r]]
    if missing:
        return f"Missing model ID for: {', '.join(missing)}. No call was made."
    return None


def run_live(role: str, assignments: List[dict], max_tokens: int, batch_id: str) -> None:
    """Exactly one OpenRouter call for one model; failures are reported, never replaced."""
    model_id = model_ids[role]
    settings = {"temperature": TEMPERATURE, "max_tokens": max_tokens,
                "response_format": "json_schema (strict)", "provider_routing": models["provider_routing"]}
    with st.spinner(f"Calling {role} model {model_id} ..."):
        res = g.call_openrouter(api_key, model_id, g.build_messages(assignments), max_tokens,
                                temperature=TEMPERATURE, provider_routing=models["provider_routing"])
    accepted, rejected = g.parse_and_validate(res["content"], assignments) if res["ok"] else ([], [])
    now = g.utc_now()
    by_slot = {a["slot_id"]: a for a in assignments}
    _add_rows([g.make_row(rec["passage"], by_slot[rec["slot_id"]], source="live", model_role=role,
                          model_id=model_id, settings=settings, batch_id=batch_id, generated_at_utc=now,
                          usage=res["usage"], cost_usd=res["cost_usd"], provider=res["provider"])
               for rec in accepted])
    st.session_state.calls.append({
        "batch_id": batch_id, "role": role, "model_id": model_id, "settings": settings, "timestamp": now,
        "ok": res["ok"], "error": res["error"], "http_status": res["http_status"], "usage": res["usage"],
        "cost_usd": res["cost_usd"], "provider": res["provider"], "response_model": res["response_model"],
        "accepted": len(accepted), "rejected": rejected})
    if not res["ok"]:
        st.error(f"{role} ({model_id}) failed: {res['error']} No other model was used.")
    else:
        msg = f"{role} ({model_id}): {len(accepted)} accepted, {len(rejected)} rejected. {_cost(res['cost_usd'])}".replace("$", "\\$")
        (st.warning if rejected else st.success)(msg)


# ---------------------------------------------------------------- generation
st.title("Classroom generator: AI or Reality?")
st.caption("Mode: " + ("LIVE (OpenRouter)" if live else "OFFLINE FIXTURES (hand-written, not model outputs)"))

left, right = st.columns(2)
with left, st.form("single"):
    st.subheader("Single passage")
    role = st.selectbox("Model role", ROLES)
    fmt = st.selectbox("Format", list(g.FORMATS), format_func=lambda k: g.FORMATS[k]["label"])
    claim = st.selectbox("Claim", list(g.CLAIMS),
                         format_func=lambda k: f"{g.CLAIMS[k]['stance']}: {g.CLAIMS[k]['claim_text']}")
    submitted = st.form_submit_button("Generate one passage")
if submitted:
    assignment = next(a for a in g.ASSIGNMENTS if a["claim_id"] == claim and a["format"] == fmt)
    with left:
        if not live:
            fixtures = _fixtures()
            if fixtures:
                _add_rows([r for r in fixtures if r["generator"]["model_role"] == role
                           and r["label"]["slot_id"] == assignment["slot_id"]])
                st.info("OFFLINE FIXTURE — not a model output. Added below.")
        elif _live_blocker():
            st.error(_live_blocker())
        else:
            run_live(role, [assignment], g.MAX_TOKENS_SINGLE, g.new_batch_id())

with right, st.form("balanced"):
    st.subheader("Balanced dataset")
    st.caption("Same 4 assignments for both models; one call per model, no retries, no substitute model.")
    st.dataframe([{**a, "claim": g.CLAIMS[a["claim_id"]]["stance"],
                   "max_words": g.FORMATS[a["format"]]["max_words"]} for a in g.ASSIGNMENTS],
                 hide_index=True)
    submitted = st.form_submit_button("Generate balanced dataset (1 call per model)")
if submitted:
    with right:
        if not live:
            fixtures = _fixtures()
            if fixtures:
                _add_rows(fixtures)
                st.info(f"Loaded {len(fixtures)} OFFLINE FIXTURES — not model outputs.")
        elif _live_blocker():
            st.error(_live_blocker())
        else:
            batch_id = g.new_batch_id()
            for r in ROLES:
                run_live(r, g.ASSIGNMENTS, g.MAX_TOKENS_BATCH, batch_id)

# ---------------------------------------------------------------- rows
rows: List[dict] = st.session_state.rows
st.header(f"Passages ({len(rows)})")
for row in rows:
    gen, lab = row["generator"], row["label"]
    with st.container(border=True):
        if gen["source"] == "live":
            st.badge("LIVE — awaiting instructor review", color="orange")
        else:
            st.badge("OFFLINE FIXTURE — not a model output", color="gray")
        st.text(g.passage_only(row))
        st.caption(f"{row['row_id']} · {gen['model_role']} · {gen['model_id'] or 'no model'} · "
                   f"intended: {lab['stance']} ({lab['format']}) · "
                   f"call cost: {_cost(gen['cost_usd'])}".replace("$", "\\$"))
        st.json({k: row[k] for k in ("label", "generator", "review_status", "correction")}, expanded=False)

rejected = [dict(rej, batch_id=c["batch_id"], role=c["role"], model_id=c["model_id"])
            for c in st.session_state.calls for rej in c["rejected"]]
with st.expander(f"Rejected records ({len(rejected)}) — not added to the dataset"):
    for rej in rejected:
        st.markdown(f"**{rej['role']} · slot {rej['slot_id']}** — {rej['reason']}")
        if rej.get("passage"):
            st.text(rej["passage"])
with st.expander(f"Call log ({len(st.session_state.calls)})"):
    st.json(st.session_state.calls, expanded=False)

# ---------------------------------------------------------------- comparison
st.header("Generator comparison")
cmp_rows, cmp_msg = g.comparison_rows(rows)
if not rows:
    st.info("No passages yet.")
elif cmp_msg:
    (st.error if any(r["generator"]["source"] == "live" for r in rows) else st.info)(cmp_msg)
else:
    table: Dict[tuple, dict] = {}
    seen_calls = set()
    for r in cmp_rows:
        gen = r["generator"]
        t = table.setdefault((gen["model_role"], gen["model_id"]), {
            "role": gen["model_role"], "model_id": gen["model_id"], "passages": 0,
            "total_cost_usd": 0.0, "total_tokens": 0, "cost_missing": False})
        t["passages"] += 1
        call_key = (gen["batch_id"], gen["model_role"])  # usage/cost are per call, shared by its rows
        if call_key not in seen_calls:
            seen_calls.add(call_key)
            t["total_tokens"] += (gen["usage"] or {}).get("total_tokens") or 0
            if gen["cost_usd"] is None:
                t["cost_missing"] = True
            else:
                t["total_cost_usd"] += gen["cost_usd"]
    st.dataframe([{"role": t["role"], "model_id": t["model_id"], "passages": t["passages"],
                   "total cost": "Cost not returned by API" if t["cost_missing"] else _cost(t["total_cost_usd"]),
                   "total tokens": t["total_tokens"]} for t in table.values()], hide_index=True)

# ---------------------------------------------------------------- export
st.header("Export")
st.caption("Local download for the instructor. Do not publish or share.")
st.download_button("Download JSON", json.dumps(g.build_export(rows, models), indent=2),
                   file_name="classroom_generator_export.json", mime="application/json", disabled=not rows)
