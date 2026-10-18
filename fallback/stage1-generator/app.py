"""Classroom misinformation lab (stage 1: generator).

Run with:  python -m streamlit run app.py

Every network call sits behind an explicit button. Results live in
st.session_state, so editing a widget or switching tabs never calls a model.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values

import generation as gen
import openrouter_client as orc

APP_VERSION = "stage-1 generator, 2026-10-18"
HERE = Path(__file__).parent
ENV_PATH = HERE / ".env"            # local secrets file, ignored by Git

st.set_page_config(page_title="Classroom misinformation lab", layout="wide")
st.markdown("""<style>
.passage {border-left: 4px solid #8a8f98; background: rgba(128,128,128,0.08); padding: 0.6rem 0.9rem;
          margin: 0.3rem 0 0.4rem 0; font-size: 1.05rem; line-height: 1.45; white-space: pre-wrap;}
.wrapper {font-size: 0.85rem; opacity: 0.85;}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ state --
def get_api_key() -> tuple[str | None, str | None]:
    """Environment first, then .env, then project Streamlit secrets. The key is never stored in session_state."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key, "environment variable"
    key = str(dotenv_values(ENV_PATH).get("OPENROUTER_API_KEY") or "").strip()
    if key:
        return key, ".env file"
    try:
        key = str(st.secrets.get("OPENROUTER_API_KEY", "")).strip()
    except Exception:  # no secrets file, or an unreadable one
        key = ""
    return (key, "Streamlit secrets") if key else (None, None)


ss = st.session_state
ss.setdefault("dataset", gen.new_dataset())
ss.setdefault("singles", [])
ss.setdefault("calls", [])
ss.setdefault("flash", [])
ss.setdefault("model_support", {})
ss.setdefault("ds_epoch", 0)   # part of widget keys, so a cleared dataset starts with fresh widgets

CFG, CFG_PROBLEM = gen.load_models_config()
for role in gen.ROLES:
    ss.setdefault(f"gen_model_{role}", CFG.get(role, {}).get("id", ""))
ss.setdefault("provider_order", ", ".join(gen.provider_routing(CFG).get("order", [])))
VERIFIED_STRUCTURED = {CFG[r]["id"] for r in gen.ROLES if r in CFG
                       and "structured_outputs" in CFG.get("preflight", {}).get("supported_parameters_both", [])}

API_KEY, KEY_SOURCE = get_api_key()


def flash(kind: str, text: str) -> None:
    ss.flash.append((kind, text))


def supports_structured(model: str) -> bool:
    if model in ss.model_support:
        return "structured_outputs" in ss.model_support[model]
    return model in VERIFIED_STRUCTURED


def documented_size(model: str) -> str:
    for role in gen.ROLES:
        if CFG.get(role, {}).get("id") == model:
            return f"{CFG[role]['documented_size']} (source: {CFG[role]['size_source']})"
    return "size not documented for this ID (do not call it small or large)"


def current_routing() -> dict:
    """Same-model endpoint routing from the sidebar (prefilled from models.json)."""
    order = [x.strip() for x in ss.provider_order.split(",") if x.strip()]
    return {"order": order, "allow_fallbacks": False} if order else {}


def do_generate(role: str, slots: list[dict], kind: str) -> orc.CallResult:
    """Exactly one OpenRouter call. Logged whether it succeeds or not."""
    model = ss[f"gen_model_{role}"].strip()
    structured = supports_structured(model)
    res = orc.chat_completion(
        API_KEY, model, gen.build_messages(slots, structured),
        max_tokens=gen.max_tokens_for(len(slots)),
        temperature=gen.GEN_SETTINGS["temperature"], seed=gen.GEN_SETTINGS["seed"],
        response_format=gen.response_schema([s["slot_id"] for s in slots]) if structured else None,
        provider=current_routing())
    call_id = f"c{len(ss.calls) + 1:02d}"
    ss.calls.append(gen.call_record(kind, role, res, {"call_id": call_id}))
    return res


def clear_dataset() -> None:
    ss.dataset = gen.new_dataset()
    ss.ds_epoch += 1
    ss.confirm_clear = False


def review_widget_key(row_id: str) -> str:
    return f"rev_{ss.ds_epoch}_{row_id}"


def on_review_change(row_id: str) -> None:
    gen.set_review(ss.dataset, row_id, status=ss[review_widget_key(row_id)])


def on_note_change(row_id: str) -> None:
    gen.set_review(ss.dataset, row_id, note=ss[f"note_{review_widget_key(row_id)}"])


def approve_clean(row_ids: list[str]) -> None:
    for rid in row_ids:
        gen.set_review(ss.dataset, rid, "approved", "approved in bulk after reading")


def cost_text(cost) -> str:
    return f"US${cost:.6f} (reported by OpenRouter)" if isinstance(cost, (int, float)) else "unavailable (not returned)"


def passage_card(row: dict, *, show_label: bool = True) -> None:
    label = gen.LABEL_NAMES[row["intended_label"]] if show_label else "hidden"
    who = (f"{row['generator_role']} generator · `{row['generator_model']}`"
           if row["source_type"] == "live" else f"{row['source_type'].upper()} · {row['provenance']}")
    st.markdown(f"<div class='wrapper'>Classroom example <b>{html.escape(row['row_id'])}</b> · "
                f"{gen.FORMATS[row['format']]['label']} · intended label: <b>{label}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='passage'>{html.escape(row['passage'])}</div>", unsafe_allow_html=True)
    st.caption(f"{who} · review: {row['review_status']}  \nCorrection: {gen.CORRECTION}")
    if row["flags"]:
        st.warning("Review flags: " + "; ".join(row["flags"]))


# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.header("Setup")
    st.toggle("Offline demonstration mode (no network calls)", key="offline", value=True)
    if API_KEY:
        st.success(f"OpenRouter key found ({KEY_SOURCE}). The key itself is never shown.")
    else:
        st.info("No OpenRouter key found. Offline mode works without one.")
    if CFG_PROBLEM:
        st.error(CFG_PROBLEM)
    else:
        st.caption(f"models.json loaded · preflight {CFG['preflight']['checked_at_utc']}")
    with st.expander("Request settings (identical for both models)"):
        st.write({"temperature": gen.GEN_SETTINGS["temperature"], "seed (determinism not guaranteed)":
                  gen.GEN_SETTINGS["seed"], "max_tokens one example": gen.GEN_SETTINGS["max_tokens_single"],
                  "max_tokens batch of 4": gen.max_tokens_for(4), "connect / read timeout (s)":
                  f"{orc.CONNECT_TIMEOUT_S} / {orc.READ_TIMEOUT_S}", "total deadline (s)": orc.TOTAL_DEADLINE_S,
                  "automatic retries": 0, "fallback models": "none"})
    st.text_input("Provider endpoint order (same model only; empty = OpenRouter default)", key="provider_order",
                  help="Prefilled from models.json. Sent as provider.order with allow_fallbacks=false: "
                       "one endpoint attempt, never another model.")
    if st.button("Check model IDs against OpenRouter (free model list)", key="btn_check_models",
                 disabled=ss.offline):
        models, msg = orc.list_models(API_KEY)
        if models is None:
            flash("error", msg)
        else:
            for role in gen.ROLES:
                mid = ss[f"gen_model_{role}"].strip()
                ss.model_support[mid] = models.get(mid, [])
                flash("success" if mid in models else "error",
                      f"{role}: `{mid}` " + ("is listed." if mid in models else "is NOT listed."))
    st.caption(APP_VERSION)

LIVE = not ss.offline
CAN_CALL = LIVE and bool(API_KEY)

# ----------------------------------------------------------------- header --
st.title("Classroom misinformation lab")
st.error(f"**{gen.EXERCISE_WARNING}**  \n{gen.CORRECTION} "
         f"[WHO tobacco fact sheet]({gen.WHO_URL})")
# Messages go into one fixed container, so the tabs below keep their position (and selection).
notices = st.container()
with notices:
    if LIVE and not API_KEY:
        st.warning("Live mode needs OPENROUTER_API_KEY in the environment, in .env or in .streamlit/secrets.toml. "
                   "Switch on offline mode to continue without a key.")
    for kind, text in ss.flash:
        getattr(st, kind)(text)
ss.flash = []

(tab_gen,) = st.tabs(["Generate"], key="main_tabs", on_change="rerun")  # tracked: no calls

with tab_gen:
    # ----------------------------------------------------- model choices --
    st.subheader("Generator models")
    c1, c2 = st.columns(2)
    for col, role in zip((c1, c2), gen.ROLES):
        with col:
            st.text_input(f"{role.capitalize()} generator model ID", key=f"gen_model_{role}",
                          disabled=ss.dataset["frozen"])
            mid = ss[f"gen_model_{role}"].strip()
            st.caption(f"Exact ID sent: `{mid or '(empty)'}`  \nDocumented size: {documented_size(mid)}  \n"
                       f"Structured output: {'yes' if supports_structured(mid) else 'not verified, plain JSON requested'}")

    # -------------------------------------------------------- one example --
    st.subheader("1 · One example")
    with st.form("single_form"):
        f1, f2, f3 = st.columns(3)
        role = f1.radio("Generator", gen.ROLES, horizontal=True, key="single_role")
        fmt = f2.radio("Format", list(gen.FORMATS), format_func=lambda k: gen.FORMATS[k]["label"], key="single_format")
        label = f3.radio("Central claim", ["false", "true"], format_func=lambda k: gen.LABEL_NAMES[k],
                         key="single_label")
        st.caption("Assigned claim: " + " / ".join(f"**{gen.LABEL_NAMES[k]}**: {v['text']}" for k, v in gen.CLAIMS.items()))
        submitted = st.form_submit_button("Show offline fixture" if not LIVE else "Generate one example (1 paid call)",
                                          disabled=LIVE and not API_KEY, key="btn_single")
    if submitted:
        slot = {"slot_id": "S1", "label": label, "format": fmt}
        if LIVE:
            with st.spinner(f"Calling {ss[f'gen_model_{role}']} ..."):
                res = do_generate(role, [slot], "generate_single")
            rows, problems = gen.rows_from_generation(res, role=role, slots=[slot], run_id=ss.calls[-1]["call_id"],
                                                      id_prefix=f"single{len(ss.singles) + 1}-{role[:3]}")
            if rows:
                ss.singles.insert(0, rows[0])
                flash("success", f"Example generated in {res.elapsed_s} s · cost {cost_text(res.cost_usd)}. "
                                 "It awaits instructor review.")
            else:
                flash("error", "No example stored: " + "; ".join(f"{p['problem']} ({p['detail']})" for p in problems))
        else:
            fx = [r for r in gen.fixture_rows(gen.load_fixtures())
                  if r["generator_role"] == role and r["intended_label"] == label and r["format"] == fmt]
            row = dict(fx[0], row_id=f"single{len(ss.singles) + 1}-{fx[0]['row_id']}")
            ss.singles.insert(0, row)
            flash("info", "Offline: showing a hand-authored FIXTURE, not a model output.")
        st.rerun()
    for row in ss.singles[:3]:
        with st.container(border=True):
            passage_card(row)
    if len(ss.singles) > 3:
        st.caption(f"{len(ss.singles) - 3} older single example(s) are kept in the export.")
    st.caption("Single examples are for exploration. They never enter the balanced dataset.")

    # --------------------------------------------------- balanced dataset --
    st.subheader("2 · Balanced dataset: 2 generators x 2 claims x 2 formats = 8 examples")
    st.dataframe([{"slot": s["slot_id"], "format": gen.FORMATS[s["format"]]["label"],
                   "word range": f"{gen.FORMATS[s['format']]['min_words']}-{gen.FORMATS[s['format']]['max_words']}",
                   "intended label": gen.LABEL_NAMES[s["label"]], "central claim (identical for both models)":
                   gen.CLAIMS[s["label"]]["text"]} for s in gen.BALANCED_SLOTS], hide_index=True)
    ds = ss.dataset
    b1, b2, b3, b4 = st.columns(4)
    if LIVE:
        go_both = b1.button("Generate balanced set (2 paid calls)", key="btn_gen_both",
                            disabled=not API_KEY or ds["frozen"] or ds["source_type"] not in (None, "live"))
        go_eco = b2.button("Regenerate economy only (1 call)", key="btn_gen_economy",
                           disabled=not API_KEY or ds["frozen"] or ds["source_type"] not in (None, "live"))
        go_adv = b3.button("Regenerate advanced only (1 call)", key="btn_gen_advanced",
                           disabled=not API_KEY or ds["frozen"] or ds["source_type"] not in (None, "live"))
        todo = list(gen.ROLES) if go_both else ["economy"] if go_eco else ["advanced"] if go_adv else []
        for role in todo:
            with st.spinner(f"{role}: one batch call to {ss[f'gen_model_{role}']} ..."):
                res = do_generate(role, gen.BALANCED_SLOTS, "generate_batch")
            rows, problems = gen.rows_from_generation(res, role=role, slots=gen.BALANCED_SLOTS,
                                                      run_id=ss.calls[-1]["call_id"])
            gen.replace_generator_rows(ds, role, rows, problems)
            flash("success" if rows and not problems else "warning" if rows else "error",
                  f"{role}: {len(rows)} of 4 examples stored, {len(problems)} problem(s), {res.elapsed_s} s, "
                  f"cost {cost_text(res.cost_usd)}." + ("" if res.ok else f" {res.message}"))
        if todo:
            st.rerun()
        if ds["source_type"] not in (None, "live"):
            st.caption(f"The dataset holds {ds['source_type']} rows. Clear it before generating live rows.")
    else:
        if b1.button("Load the 8 offline fixtures (hand-authored)", key="btn_load_fixtures",
                     disabled=ds["frozen"] or ds["source_type"] not in (None, "fixture") or bool(ds["rows"])):
            gen.add_rows(ds, gen.fixture_rows(gen.load_fixtures()), "fixture", gen.load_fixtures()["provenance"])
            flash("info", "Loaded 8 FIXTURES. They are hand-authored, not model outputs, and never count as a "
                          "measured generator comparison.")
            st.rerun()
    confirm = b4.checkbox("Confirm clear", key="confirm_clear")
    b4.button("Clear dataset", key="btn_clear", disabled=not confirm or ds["frozen"], on_click=clear_dataset)

    if ds["source_type"]:
        st.info(f"Dataset source: **{ds['source_type'].upper()}** · {ds['provenance']}")
    if ds["problems"]:
        st.error("Generation failures (these slots are missing from the dataset):")
        st.dataframe(ds["problems"], hide_index=True)

    # ----------------------------------------------------------- review --
    if ds["rows"]:
        st.subheader("3 · Instructor review")
        st.caption("Intended labels describe what the generator was asked to argue. Read each passage: does it "
                   "keep the assigned claim, without invented sources or numbers? Only approved rows can be scored.")
        clean_waiting = [r for r in ds["rows"] if r["review_status"] == "awaiting_review" and not r["flags"]]
        st.button(f"I have read them: approve the {len(clean_waiting)} waiting row(s) without flags",
                  key="btn_bulk_approve", disabled=not clean_waiting or ds["frozen"],
                  on_click=approve_clean, args=([r["row_id"] for r in clean_waiting],))
        options = ["awaiting_review", "approved", "excluded"]
        cols = st.columns(2)
        for i, role in enumerate(gen.ROLES):
            with cols[i]:
                st.markdown(f"**{role.capitalize()} slot**")
                for row in [r for r in ds["rows"] if r["generator_role"] == role]:
                    with st.container(border=True):
                        passage_card(row)
                        k = review_widget_key(row["row_id"])
                        if ss.get(k) != row["review_status"]:
                            ss[k] = row["review_status"]   # the dataset is the single source of truth
                        st.radio("Review decision", options, horizontal=True, key=k, disabled=ds["frozen"],
                                 on_change=on_review_change, args=(row["row_id"],))
                        if ss.get(f"note_{k}") != row["review_note"]:
                            ss[f"note_{k}"] = row["review_note"]
                        st.text_input("Review note (for example, why it is excluded)", key=f"note_{k}",
                                      disabled=ds["frozen"], on_change=on_note_change, args=(row["row_id"],))
        ok, msg = gen.balance_status(ds)
        (st.success if ok else st.warning)(msg)
        st.dataframe(gen.balance_table(ds), hide_index=True)

    # ----------------------------------------------------- export & log --
    st.subheader("4 · Export and call log")
    st.download_button("Download JSON export (with exercise warning, no secrets)",
                       data=gen.export_bundle({"dataset": ss.dataset, "singles": ss.singles, "calls": ss.calls},
                                              APP_VERSION),
                       file_name="classroom_misinformation_export.json", mime="application/json")
    with st.expander(f"Call log ({len(ss.calls)} call(s) in this session)"):
        if ss.calls:
            st.dataframe([{"call": c["call_id"], "kind": c["kind"], "role": c["role"], "model": c["model_requested"],
                           "status": c["status"], "started (UTC)": c["started_at_utc"], "elapsed s": c["elapsed_s"],
                           "provider": c["provider"],
                           "tokens in/out": f"{(c['usage'] or {}).get('prompt_tokens', '-')}/"
                                            f"{(c['usage'] or {}).get('completion_tokens', '-')}",
                           "cost": cost_text(c["cost_usd"]), "message": c["message"]} for c in ss.calls],
                         hide_index=True)
        else:
            st.caption("No calls yet.")
