"""Classroom misinformation lab: generate, review, then assess claims.

Run with:  python -m streamlit run app.py

Every network call sits behind an explicit button. Results live in
st.session_state, so editing a widget or switching tabs never calls a model.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values

import detection as det
import generation as gen
import openrouter_client as orc

APP_VERSION = "full app (generator + detect & compare), 2026-10-18"
HERE = Path(__file__).parent
ENV_PATH = HERE / ".env"            # local secrets file, ignored by Git
RECORDED_PATH = HERE / "recorded_run.json"

st.set_page_config(page_title="Classroom misinformation lab", layout="wide")
st.markdown("""<style>
.passage {border-left: 4px solid #8a8f98; background: rgba(128,128,128,0.08); padding: 0.6rem 0.9rem;
          margin: 0.3rem 0 0.4rem 0; font-size: 1.05rem; line-height: 1.45; white-space: pre-wrap;}
.wrapper {font-size: 0.85rem; opacity: 0.85;}
table.matrix {border-collapse: collapse; width: 100%; font-size: 0.95rem;}
table.matrix th, table.matrix td {border: 1px solid rgba(128,128,128,0.45); padding: 0.5rem 0.7rem; vertical-align: top;}
table.matrix th {background: rgba(128,128,128,0.12); text-align: left;}
.big {font-size: 1.35rem; font-weight: 700;}
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
ss.setdefault("ds_epoch", 0)          # part of widget keys, so a cleared dataset starts with fresh widgets
ss.setdefault("detections", {})       # role -> detection run on the current frozen dataset
ss.setdefault("detection_archive", [])
ss.setdefault("pasted", [])
ss.setdefault("per_cell", 1)

CFG, CFG_PROBLEM = gen.load_models_config()
for role in gen.ROLES:
    ss.setdefault(f"gen_model_{role}", CFG.get(role, {}).get("id", ""))
    ss.setdefault(f"det_model_{role}", CFG.get(role, {}).get("id", ""))
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


def log_call(kind: str, role: str | None, res: orc.CallResult, extra: dict | None = None) -> str:
    call_id = f"c{len(ss.calls) + 1:02d}"
    ss.calls.append(gen.call_record(kind, role, res, {"call_id": call_id, **(extra or {})}))
    return call_id


def do_generate(role: str, slots: list[dict], kind: str) -> orc.CallResult:
    """Exactly one OpenRouter call for one generator."""
    model = ss[f"gen_model_{role}"].strip()
    structured = supports_structured(model)
    return orc.chat_completion(
        API_KEY, model, gen.build_messages(slots, structured),
        max_tokens=gen.max_tokens_for(len(slots)),
        temperature=gen.GEN_SETTINGS["temperature"], seed=gen.GEN_SETTINGS["seed"],
        response_format=gen.response_schema([s["slot_id"] for s in slots]) if structured else None,
        provider=current_routing())


def do_detect(role: str, items: list[dict]) -> orc.CallResult:
    """Exactly one OpenRouter call for one detector. Items hold only blind IDs and passages."""
    model = ss[f"det_model_{role}"].strip()
    structured = supports_structured(model)
    return orc.chat_completion(
        API_KEY, model, det.build_messages(items, structured),
        max_tokens=det.max_tokens_for(len(items)),
        temperature=det.DET_SETTINGS["temperature"], seed=det.DET_SETTINGS["seed"],
        response_format=det.response_schema([it["id"] for it in items]) if structured else None,
        provider=current_routing())


def clear_dataset() -> None:
    archive_detections("dataset cleared")
    ss.dataset = gen.new_dataset()
    ss.ds_epoch += 1
    ss.confirm_clear = False


def archive_detections(reason: str) -> None:
    if ss.detections:
        ss.detection_archive.append({"archived_at_utc": orc.now_utc(), "reason": reason,
                                     "detections": ss.detections})
        ss.detections = {}


def do_unfreeze() -> None:
    archive_detections("unfrozen by instructor (results kept in the export)")
    det.unfreeze(ss.dataset)
    ss.confirm_unfreeze = False


def review_widget_key(row_id: str) -> str:
    return f"rev_{ss.ds_epoch}_{row_id}"


def on_review_change(row_id: str) -> None:
    gen.set_review(ss.dataset, row_id, status=ss[review_widget_key(row_id)])


def on_note_change(row_id: str) -> None:
    gen.set_review(ss.dataset, row_id, note=ss[f"note_{review_widget_key(row_id)}"])


def approve_clean(row_ids: list[str]) -> None:
    for rid in row_ids:
        gen.set_review(ss.dataset, rid, "approved", "approved in bulk after reading")


def load_recorded() -> None:
    data = json.loads(RECORDED_PATH.read_text(encoding="utf-8"))
    archive_detections("recorded rehearsal run loaded")
    ss.dataset = data["dataset"]
    ss.ds_epoch += 1
    ss.detections = data["detections"]
    flash("info", f"Loaded the RECORDED rehearsal run: {data['provenance']}")


def cost_text(cost) -> str:
    return f"US${cost:.6f} (reported by OpenRouter)" if isinstance(cost, (int, float)) else "unavailable (not returned)"


def passage_card(row: dict, *, show_label: bool = True) -> None:
    label = gen.LABEL_NAMES[row["intended_label"]] if show_label else "hidden"
    who = (f"{row['generator_role']} generator · `{row['generator_model']}`"
           if row["source_type"] in ("live", "recorded") else f"{row['source_type'].upper()} · {row['provenance']}")
    st.markdown(f"<div class='wrapper'>Classroom example <b>{html.escape(row['row_id'])}</b> · "
                f"{gen.FORMATS[row['format']]['label']} · intended label: <b>{label}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='passage'>{html.escape(row['passage'])}</div>", unsafe_allow_html=True)
    st.caption(f"{who} · review: {row['review_status']}"
               + (f" ({row['review_note']})" if row.get("review_note") else "")
               + f"  \nCorrection: {gen.CORRECTION}")
    if row["flags"]:
        st.warning("Review flags: " + "; ".join(row["flags"]))


def experiment_label(ds: dict, dets: dict) -> tuple[str, str]:
    kinds = {d["kind"] for d in dets.values()}
    src = ds["source_type"]
    if not dets:
        return "info", "No detector results yet."
    if kinds == {"illustrative"}:
        return "error", ("ILLUSTRATIVE ONLY: hand-authored passages AND hand-authored verdicts. "
                         "Nothing was measured; use it to explain the table, not to draw conclusions.")
    if src == "fixture":
        return "warning", ("FIXTURE CONTROL: live detectors on hand-authored passages. "
                           "This tests the detectors; it is NOT a generator comparison.")
    if kinds == {"recorded"}:
        return "warning", ("RECORDED rehearsal run: real model outputs from an earlier session, replayed. "
                           "Nothing was measured just now.")
    if src == "recorded":
        return "warning", "Live detector runs on RECORDED generations from an earlier session."
    if kinds == {"live"}:
        return "success", "MEASURED in this session: live generations, reviewed, frozen, then assessed by live detectors."
    return "warning", "Mixed result types; see the label of each detector column."


def generator_heading(ds: dict, role: str) -> str:
    rows = [r for r in ds["rows"] if r["generator_role"] == role]
    if ds["source_type"] == "fixture":
        return f"Fixture set {'A' if role == 'economy' else 'B'}<br><small>hand-authored, stands in for the {role} slot</small>"
    model = rows[0]["generator_model"] if rows else ss[f"gen_model_{role}"]
    tag = " (recorded)" if ds["source_type"] == "recorded" else ""
    return f"{role.capitalize()} generator{tag}<br><code>{html.escape(model)}</code>"


def cell_html(m: dict) -> str:
    if m is None:
        return "<i>not run</i>"
    warn = "" if m["balanced"] else "<br><b>imbalanced cell</b>"
    return (f"<span class='big'>{m['correct']}/{m['eligible']}</span> correct of eligible "
            f"({det.fmt_rate(m['overall_success'])})<br>"
            f"coverage: {det.fmt_rate(m['coverage'])} answered<br>"
            f"abstentions: {m['abstentions']} · failures: {m['failures']} "
            f"(service {m['fail_service']}, format {m['fail_format']})<br>"
            f"false-claim recall: {det.fmt_rate(m['false_claim_recall'])}<br>"
            f"false positives: {m['fp']} of {m['n_true']} true · rate {det.fmt_rate(m['false_positive_rate'])}<br>"
            f"answered-only accuracy: {det.fmt_rate(m['answered_accuracy'])}{warn}")


def all_metrics(ds: dict) -> dict:
    frozen = set(ds.get("frozen_order", []))
    out = {}
    for g in gen.ROLES:
        rows = [r for r in ds["rows"] if r["row_id"] in frozen and r["generator_role"] == g]
        for d in gen.ROLES:
            dres = ss.detections.get(d)
            out[f"{g}_generator__{d}_detector"] = det.cell_metrics(rows, dres["results"]) if dres else None
    return out


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
    st.text_input("Provider endpoint order (same model only; empty = OpenRouter default)", key="provider_order",
                  help="Prefilled from models.json. Sent as provider.order with allow_fallbacks=false: "
                       "one endpoint attempt, never another model.")
    with st.expander("Request settings (identical for both models)"):
        st.write({"generation temperature": gen.GEN_SETTINGS["temperature"],
                  "detection temperature": det.DET_SETTINGS["temperature"],
                  "seed (determinism not guaranteed)": gen.GEN_SETTINGS["seed"],
                  "max_tokens: one example / batch of 4": f"{gen.GEN_SETTINGS['max_tokens_single']} / {gen.max_tokens_for(4)}",
                  "max_tokens: detector batch of 8": det.max_tokens_for(8),
                  "connect / read timeout (s)": f"{orc.CONNECT_TIMEOUT_S} / {orc.READ_TIMEOUT_S}",
                  "total deadline (s)": orc.TOTAL_DEADLINE_S, "automatic retries": 0, "fallback models": "none"})
    if st.button("Check model IDs against OpenRouter (free model list)", key="btn_check_models",
                 disabled=ss.offline):
        models, msg = orc.list_models(API_KEY)
        if models is None:
            flash("error", msg)
        else:
            ids = {ss[f"{k}_model_{r}"].strip() for k in ("gen", "det") for r in gen.ROLES}
            for mid in sorted(ids):
                ss.model_support[mid] = models.get(mid, [])
                flash("success" if mid in models else "error",
                      f"`{mid}` " + ("is listed." if mid in models else "is NOT listed."))
        st.rerun()
    if RECORDED_PATH.exists():
        st.button("Load recorded rehearsal run (real outputs, no network)", key="btn_load_recorded",
                  on_click=load_recorded, disabled=ss.dataset["frozen"] and ss.dataset["source_type"] == "live")
    st.caption(APP_VERSION)

LIVE = not ss.offline

# ----------------------------------------------------------------- header --
st.title("Classroom misinformation lab")
st.error(f"**{gen.EXERCISE_WARNING}**  \n{gen.CORRECTION} [WHO tobacco fact sheet]({gen.WHO_URL})")
# Messages go into one fixed container, so the tabs below keep their position (and selection).
notices = st.container()
with notices:
    if LIVE and not API_KEY:
        st.warning("Live mode needs OPENROUTER_API_KEY in the environment, in .env or in .streamlit/secrets.toml. "
                   "Switch on offline mode to continue without a key.")
    for kind, text in ss.flash:
        getattr(st, kind)(text)
ss.flash = []

tab_gen, tab_det = st.tabs(["Generate", "Detect & compare"], key="main_tabs", on_change="rerun")  # tracked: no calls

# =================================================================== GENERATE
with tab_gen:
    ds = ss.dataset
    st.subheader("Generator models")
    c1, c2 = st.columns(2)
    for col, role in zip((c1, c2), gen.ROLES):
        with col:
            st.text_input(f"{role.capitalize()} generator model ID", key=f"gen_model_{role}", disabled=ds["frozen"])
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
            call_id = log_call("generate_single", role, res)
            rows, problems = gen.rows_from_generation(res, role=role, slots=[slot], run_id=call_id,
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
            ss.singles.insert(0, dict(fx[0], row_id=f"single{len(ss.singles) + 1}-{fx[0]['row_id']}"))
            flash("info", "Offline: showing a hand-authored FIXTURE, not a model output.")
        st.rerun()
    for row in ss.singles[:3]:
        with st.container(border=True):
            passage_card(row)
    if len(ss.singles) > 3:
        st.caption(f"{len(ss.singles) - 3} older single example(s) are kept in the export.")
    st.caption("Single examples are for exploration. They never enter the balanced dataset.")

    # --------------------------------------------------- balanced dataset --
    per_cell = ss.per_cell
    st.subheader(f"2 · Balanced dataset: 2 generators x 2 claims x 2 formats = {8 * per_cell} examples")
    st.dataframe([{"slot": s["slot_id"], "format": gen.FORMATS[s["format"]]["label"],
                   "word range": f"{gen.FORMATS[s['format']]['min_words']}-{gen.FORMATS[s['format']]['max_words']}",
                   "intended label": gen.LABEL_NAMES[s["label"]], "central claim (identical for both models)":
                   gen.CLAIMS[s["label"]]["text"]} for s in gen.BALANCED_SLOTS], hide_index=True)
    with st.expander("Optional preparation extension (not needed in the lecture)"):
        st.radio("Examples per design cell", [1, 3], horizontal=True, key="per_cell",
                 format_func=lambda n: "1 per cell: 8 examples (live lecture)" if n == 1
                 else "3 per cell: 24 examples (preparation only; still one call per model)",
                 disabled=bool(ds["rows"]))
    b1, b2, b3, b4 = st.columns(4)
    blocked = ds["frozen"] or ds["source_type"] not in (None, "live")
    if LIVE:
        go_both = b1.button("Generate balanced set (2 paid calls)", key="btn_gen_both", disabled=not API_KEY or blocked)
        go_eco = b2.button("Regenerate economy only (1 call)", key="btn_gen_economy", disabled=not API_KEY or blocked)
        go_adv = b3.button("Regenerate advanced only (1 call)", key="btn_gen_advanced", disabled=not API_KEY or blocked)
        todo = list(gen.ROLES) if go_both else ["economy"] if go_eco else ["advanced"] if go_adv else []
        for role in todo:
            slots = gen.balanced_slots(per_cell)
            with st.spinner(f"{role}: one batch call to {ss[f'gen_model_{role}']} ..."):
                res = do_generate(role, slots, "generate_batch")
            call_id = log_call("generate_batch", role, res)
            rows, problems = gen.rows_from_generation(res, role=role, slots=slots, run_id=call_id)
            gen.replace_generator_rows(ss.dataset, role, rows, problems)
            flash("success" if rows and not problems else "warning" if rows else "error",
                  f"{role}: {len(rows)} of {len(slots)} examples stored, {len(problems)} problem(s), "
                  f"{res.elapsed_s} s, cost {cost_text(res.cost_usd)}." + ("" if res.ok else f" {res.message}"))
        if todo:
            st.rerun()
        if ds["source_type"] not in (None, "live"):
            st.caption(f"The dataset holds {ds['source_type']} rows. Clear it before generating live rows.")
    else:
        if b1.button("Load the 8 offline fixtures (hand-authored)", key="btn_load_fixtures",
                     disabled=blocked or bool(ds["rows"]) or per_cell != 1):
            fx = gen.load_fixtures()
            gen.add_rows(ss.dataset, gen.fixture_rows(fx), "fixture", fx["provenance"])
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
        st.caption("Intended labels describe what the generator was asked to argue. Read each passage: does it keep "
                   "the assigned claim, without invented sources or numbers? Only approved rows can be scored.")
        if ds["frozen"]:
            st.info("The dataset is frozen for detection; review decisions are locked.")
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
        ok, msg = gen.balance_status(ds, per_cell)
        (st.success if ok else st.warning)(msg)
        st.dataframe(gen.balance_table(ds), hide_index=True)

# ===================================================================== DETECT
with tab_det:
    ds = ss.dataset
    cap = det.LIVE_CAP if ss.per_cell == 1 else det.EXTENSION_CAP
    st.subheader("Evidence-assisted factual-claim assessment")
    st.info("Both detector models get **the same** short evidence packet, the same fixed instructions and the same "
            "frozen passages, and must answer `supported`, `contradicted` or `insufficient_evidence`. This is an "
            "LLM-based classroom classifier: not a validated fake-news detector, not an AI-authorship detector, and "
            "not independent web research or medical verification.")
    with st.expander(f"Evidence packet sent to both detectors ({det.EVIDENCE_PACKET['source']}, retrieved "
                     f"{det.EVIDENCE_PACKET['retrieved']})"):
        st.dataframe(det.EVIDENCE_PACKET["items"], hide_index=True)
        st.markdown(f"Source: [{det.EVIDENCE_PACKET['url']}]({det.EVIDENCE_PACKET['url']})")
    st.caption("Detectors never receive intended labels, generator identity, review metadata, generation prompts, "
               "the correction text or the exercise wrapper. Passages are sent as untrusted data under blind IDs.")

    d1, d2 = st.columns(2)
    for col, role in zip((d1, d2), gen.ROLES):
        with col:
            st.text_input(f"{role.capitalize()} detector model ID", key=f"det_model_{role}")
            mid = ss[f"det_model_{role}"].strip()
            st.caption(f"Exact ID sent: `{mid or '(empty)'}` · chosen independently of the generators  \n"
                       f"Documented size: {documented_size(mid)}")

    # ---------------------------------------------------------- freeze --
    st.subheader("1 · Freeze the reviewed dataset")
    approved = [r for r in ds["rows"] if r["review_status"] == "approved"]
    waiting = [r for r in ds["rows"] if r["review_status"] == "awaiting_review"]
    excluded = [r for r in ds["rows"] if r["review_status"] == "excluded"]
    st.write(f"Source: **{(ds['source_type'] or 'none').upper()}** · approved {len(approved)} · awaiting review "
             f"{len(waiting)} (not scored) · excluded {len(excluded)} · generation failures {len(ds['problems'])}")
    if excluded:
        st.dataframe([{"row": r["row_id"], "generator": r["generator_role"], "label": r["intended_label"],
                       "format": r["format"], "exclusion note": r["review_note"]} for r in excluded], hide_index=True)
    ok, msg = gen.balance_status(ds, ss.per_cell)
    (st.success if ok else st.warning)(msg)
    with st.expander("Counts per generator x reviewed label x format"):
        st.dataframe(gen.balance_table(ds), hide_index=True)
    if not ds["frozen"]:
        if st.button(f"Freeze the {len(approved)} approved row(s) (no network)", key="btn_freeze",
                     disabled=not approved or len(approved) > cap):
            det.freeze(ds, cap)
            flash("success", f"Frozen {len(approved)} rows · dataset hash {ds['frozen_hash'][:12]} · order fixed.")
            st.rerun()
        if len(approved) > cap:
            st.error(f"More than {cap} approved rows: the comparison is capped at {cap}.")
    else:
        st.success(f"Frozen: {len(ds['frozen_order'])} rows · hash `{ds['frozen_hash'][:12]}` · deterministic "
                   "shuffled order and blind IDs fixed before any verdict.")
        u1, u2 = st.columns([1, 3])
        conf = u1.checkbox("Confirm unfreeze", key="confirm_unfreeze")
        u1.button("Unfreeze", key="btn_unfreeze", disabled=not conf, on_click=do_unfreeze)
        u2.caption("Unfreezing after seeing verdicts and then changing the selection would be post-hoc selection. "
                   "Earlier results are archived and stay in the export.")

    # ------------------------------------------------------------- run --
    st.subheader("2 · Run the detectors")
    items = det.frozen_items(ds) if ds["frozen"] else []
    if not ds["frozen"]:
        st.caption("Freeze the dataset first.")
    elif LIVE:
        r1, r2, r3 = st.columns(3)
        go_both = r1.button(f"Run both detectors (2 paid calls, {len(items)} passages each)", key="btn_detect_both",
                            disabled=not API_KEY)
        go_e = r2.button("Run economy detector only (1 call)", key="btn_detect_economy", disabled=not API_KEY)
        go_a = r3.button("Run advanced detector only (1 call)", key="btn_detect_advanced", disabled=not API_KEY)
        todo = list(gen.ROLES) if go_both else ["economy"] if go_e else ["advanced"] if go_a else []
        for role in todo:
            with st.spinner(f"{role} detector: one batch call to {ss[f'det_model_{role}']} ..."):
                res = do_detect(role, items)
            call_id = log_call("detect_batch", role, res, {"frozen_hash": ds["frozen_hash"]})
            results, problems = det.results_from_call(res, ds)
            if role in ss.detections:
                ss.detection_archive.append({"archived_at_utc": orc.now_utc(), "reason": f"{role} detector re-run",
                                             "detections": {role: ss.detections[role]}})
            ss.detections[role] = {"kind": "live", "detector_model": res.model_requested, "call_id": call_id,
                                   "frozen_hash": ds["frozen_hash"], "results": results, "problems": problems,
                                   "status": res.status, "elapsed_s": res.elapsed_s, "cost_usd": res.cost_usd,
                                   "started_at_utc": res.started_at_utc}
            n_ok = sum(v["status"] == "predicted" for v in results.values())
            flash("success" if n_ok == len(items) else "warning" if n_ok else "error",
                  f"{role} detector: {n_ok}/{len(items)} valid assessments, {res.elapsed_s} s, "
                  f"cost {cost_text(res.cost_usd)}." + ("" if res.ok else f" {res.message}"))
        if todo:
            st.rerun()
    elif ds["source_type"] == "fixture":
        if st.button("Show illustrative verdicts (hand-authored, NOT measured)", key="btn_illustrative"):
            fx = gen.load_fixtures()
            for role in gen.ROLES:
                verdicts = {v["row_id"]: v for v in fx["illustrative_verdicts"][role]}
                results = {}
                for rid in ds["frozen_order"]:
                    v = verdicts.get(rid)
                    results[rid] = ({"status": "predicted", "verdict": v["verdict"], "reason": v["reason"],
                                     "evidence_ref": v["evidence_ref"]} if v else
                                    {"status": "failure", "failure_kind": "format",
                                     "detail": "illustrative missing assessment"})
                ss.detections[role] = {"kind": "illustrative", "detector_model": "ILLUSTRATIVE (hand-authored)",
                                       "frozen_hash": ds["frozen_hash"], "results": results, "problems": [],
                                       "status": "illustrative", "elapsed_s": None, "cost_usd": None,
                                       "started_at_utc": None}
            st.rerun()
    else:
        st.caption("Offline mode: detectors need live mode. A recorded rehearsal run can be loaded from the sidebar.")

    # --------------------------------------------------------- results --
    st.subheader("3 · Results: generator x detector")
    if ds["frozen"] and ss.detections:
        kind, text = experiment_label(ds, ss.detections)
        getattr(st, kind)(text)
        metrics = all_metrics(ds)
        head = "".join(
            f"<th>{role.capitalize()} detector<br><code>{html.escape(ss.detections[role]['detector_model'])}</code>"
            f"<br><small>{ss.detections[role]['kind'].upper()}</small></th>" if role in ss.detections
            else f"<th>{role.capitalize()} detector<br><small>not run</small></th>" for role in gen.ROLES)
        body = "".join(
            f"<tr><th>{generator_heading(ds, g)}</th>"
            + "".join(f"<td>{cell_html(metrics[f'{g}_generator__{d}_detector'])}</td>" for d in gen.ROLES)
            + "</tr>" for g in gen.ROLES)
        st.markdown(f"<table class='matrix'><tr><th></th>{head}</tr>{body}</table>", unsafe_allow_html=True)
        st.warning("**Read with care.** A larger or more capable model is not guaranteed to write harder-to-detect "
                   "misinformation, nor to give better verdicts. With four items per generator, one answer changes "
                   "cell accuracy by 25 percentage points; with two items per truth label in each cell, recall and "
                   "false-positive rate change by 50 points per item. Familiar tobacco claims and writing style may "
                   "dominate the result. This is a small demonstration, not evidence of a general effect.")
        with st.expander("Definitions and denominators"):
            st.markdown(
                "- **Positive class:** a FALSE claim. `contradicted` is a positive prediction, `supported` a negative one.\n"
                "- **Eligible:** frozen, approved rows from this generator (the denominator for success and coverage).\n"
                "- **Correct:** a false item predicted `contradicted`, or a true item predicted `supported`.\n"
                "- **Overall success = correct / eligible.** Abstentions and failures count as unsuccessful.\n"
                "- **Coverage = answered / eligible**, where answered means `supported` or `contradicted`.\n"
                "- **Abstention:** `insufficient_evidence`. It is never a true negative and never correct.\n"
                "- **Failures:** service (the call failed) or format (missing, duplicate, unknown or invalid item).\n"
                "- **False-claim recall = false items predicted contradicted / all eligible false items.**\n"
                "- **False-positive rate = true items predicted contradicted / all eligible true items.**\n"
                "- **Answered-only accuracy = correct / answered.**\n"
                "- **N/A:** the denominator is zero.")

        st.markdown("**Every example** (deterministic shuffled order, fixed at freezing)")
        reveal = st.toggle("Reveal intended labels and generators", key="reveal", value=False)
        by_id = {r["row_id"]: r for r in ds["rows"]}
        table = []
        for n, rid in enumerate(ds["frozen_order"], 1):
            r = by_id[rid]
            line = {"#": n, "blind ID": ds["blind_ids"][rid], "passage": r["passage"]}
            if reveal:
                line.update({"generator": r["generator_role"], "intended label": r["intended_label"],
                             "format": gen.FORMATS[r["format"]]["short"]})
            for d in gen.ROLES:
                res = (ss.detections.get(d) or {}).get("results", {}).get(rid)
                if res is None:
                    line[f"{d} verdict"] = "not run"
                elif res["status"] != "predicted":
                    line[f"{d} verdict"] = f"FAILURE ({res['failure_kind']})"
                else:
                    line[f"{d} verdict"] = f"{res['verdict']} [{res['evidence_ref']}]"
                if reveal:
                    c = det.is_correct(r, res)
                    line[f"{d} correct?"] = "yes" if c else "no" if c is False else "abstain/fail"
                line[f"{d} reason"] = (res or {}).get("reason") or (res or {}).get("detail", "")
            table.append(line)
        st.dataframe(table, hide_index=True, column_config={"passage": st.column_config.TextColumn(width="large")})
        with st.expander("Detector call details"):
            st.dataframe([{"detector": d, "kind": v["kind"], "model": v["detector_model"], "status": v["status"],
                           "started (UTC)": v["started_at_utc"], "elapsed s": v["elapsed_s"],
                           "cost": cost_text(v["cost_usd"]), "format problems": len(v["problems"])}
                          for d, v in ss.detections.items()], hide_index=True)
    else:
        st.caption("Results appear here after the detectors have run on a frozen dataset.")

    # ---------------------------------------------------------- pasted --
    st.subheader("4 · Assess a pasted passage (verdict only, never scored)")
    with st.form("paste_form"):
        text = st.text_area("Passage", key="paste_text", max_chars=2000, height=120)
        p1, p2 = st.columns(2)
        use_e = p1.checkbox("Economy detector", value=True, key="paste_economy")
        use_a = p2.checkbox("Advanced detector", value=True, key="paste_advanced")
        go_paste = st.form_submit_button("Assess pasted passage (1 paid call per ticked detector)",
                                         disabled=not LIVE or not API_KEY, key="btn_paste")
    if not LIVE:
        st.caption("Pasted passages need live mode; offline mode has no verdicts for arbitrary text.")
    if go_paste:
        if not text.strip():
            flash("warning", "Paste a passage first.")
        else:
            entry = {"passage": text.strip(), "submitted_at_utc": orc.now_utc(), "results": {}}
            for role in [r for r, use in zip(gen.ROLES, (use_e, use_a)) if use]:
                res = do_detect(role, [{"id": "X1", "text": text.strip()}])
                call_id = log_call("detect_pasted", role, res)
                if res.ok:
                    preds, problems = det.parse_assessments(res.content or "", ["X1"])
                    entry["results"][role] = ({"status": "predicted", **preds["X1"]} if "X1" in preds else
                                              {"status": "failure", "failure_kind": "format",
                                               "detail": "; ".join(det.PROBLEM_TEXT.get(p["problem"], p["problem"])
                                                                   for p in problems)})
                else:
                    entry["results"][role] = {"status": "failure", "failure_kind": "service",
                                              "detail": f"{res.status}: {res.message}"}
                entry["results"][role].update(model=res.model_requested, call_id=call_id)
            ss.pasted.insert(0, entry)
        st.rerun()
    for entry in ss.pasted[:3]:
        with st.container(border=True):
            st.markdown(f"<div class='passage'>{html.escape(entry['passage'])}</div>", unsafe_allow_html=True)
            for role, res in entry["results"].items():
                if res["status"] == "predicted":
                    st.write(f"**{role}** `{res['model']}`: **{res['verdict']}** [{res['evidence_ref']}]: {res['reason']}")
                else:
                    st.write(f"**{role}** `{res['model']}`: FAILURE ({res['failure_kind']}): {res['detail']}")
            st.caption("No verified label: verdict only; it does not affect any accuracy figure.")

# ============================================================ EXPORT & LOG
st.divider()
st.subheader("Export and call log")
export = gen.export_bundle(
    {"dataset": ss.dataset, "singles": ss.singles, "calls": ss.calls}, APP_VERSION,
    extra={"evidence_packet": det.EVIDENCE_PACKET, "detector_instructions": det.INSTRUCTIONS,
           "generator_system_prompt": gen.SYSTEM_PROMPT,
           "detections": ss.detections, "detection_archive": ss.detection_archive, "pasted_passages": ss.pasted,
           "experiment_label": experiment_label(ss.dataset, ss.detections)[1],
           "metrics": all_metrics(ss.dataset) if ss.dataset["frozen"] else None,
           "metric_definitions": "positive class = false claim; contradicted = positive prediction; "
                                 "insufficient_evidence = abstention; overall success counts abstentions and "
                                 "failures as unsuccessful"})
st.download_button("Download JSON export (with exercise warning, no secrets)", data=export,
                   file_name="classroom_misinformation_export.json", mime="application/json", key="btn_export")
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
