"""Classroom lab: generate clearly labelled TRUE/FALSE tobacco claims, review them, then compare two detectors.

Run with:  .venv/bin/python -m streamlit run app.py
Every model call sits behind an explicit button; everything lives in st.session_state.
"""
import streamlit as st

import lab

st.set_page_config(page_title="Classroom claim generator", layout="wide")
ss = st.session_state
ss.setdefault("dataset", lab.new_dataset())
ss.setdefault("singles", [])
ss.setdefault("single_problems", [])
ss.setdefault("calls", [])
ss.setdefault("messages", [])
ss.setdefault("epoch", 0)          # part of widget keys, so a cleared dataset gets fresh widgets
ss.setdefault("detections", {})    # role -> detection result on the current frozen dataset
ss.setdefault("det_messages", [])
ss.setdefault("pasted", [])

cfg, cfg_problem = lab.load_models()
defaults = lab.default_model_ids(cfg)
for role in lab.ROLES:
    ss.setdefault(f"model_{role}", defaults[role])
    ss.setdefault(f"det_model_{role}", defaults[role])
key, key_source = lab.get_api_key(st.secrets)
STATUSES = ["awaiting_review", "approved", "excluded"]


def say(kind: str, text: str) -> None:
    ss.messages.append((kind, text))


def say_det(kind: str, text: str) -> None:
    ss.det_messages.append((kind, text))


def log_call(res: dict) -> None:
    if res.get("call"):
        ss.calls.append(res["call"])


def clear_dataset() -> None:
    ss.dataset = lab.new_dataset()
    ss.detections = {}
    ss.epoch += 1
    ss.messages = [("info", "Dataset cleared.")]


def do_unfreeze() -> None:
    lab.unfreeze(ss.dataset)
    ss.detections = {}
    ss.confirm_unfreeze = False
    ss.det_messages = [("info", "Unfrozen. Detector results were cleared; reviews can change again.")]


def find_row(row_id: str, single: bool) -> dict:
    rows = ss.singles if single else ss.dataset["rows"]
    return next(r for r in rows if r["row_id"] == row_id)


def on_review(row_id: str, single: bool) -> None:
    k = f"rev_{ss.epoch}_{row_id}"
    status, note = ss[k], ss[f"note_{k}"]
    if single:
        row = find_row(row_id, True)
        row["review_status"], row["review_note"] = status, note
        return
    try:
        lab.set_review(ss.dataset, row_id, status, note)
    except ValueError as e:
        say("error", str(e))


def card(row: dict, single: bool = False) -> None:
    with st.container(border=True):
        fmt = lab.FORMATS[row["format"]]["label"]
        st.markdown(f"**{row['row_id']}** · {fmt} · intended label: **{lab.LABEL_NAMES[row['intended_label']]}**")
        if row["source_type"] == "fixture":
            st.caption("FIXTURE: hand-authored for the offline demonstration, NOT model output")
        else:
            st.caption(f"{row['generator_role']} generator · `{row['generator_model']}` · {row['provenance']}")
        st.code(row["passage"], language=None, wrap_lines=True)
        if row["flags"]:
            st.warning("Review flags: " + "; ".join(row["flags"]))
        k = f"rev_{ss.epoch}_{row['row_id']}"
        c1, c2 = st.columns([1, 2])
        c1.radio("Review", STATUSES, index=STATUSES.index(row["review_status"]), key=k, horizontal=True,
                 on_change=on_review, args=(row["row_id"], single), disabled=bool(ss.dataset["frozen"]) and not single)
        c2.text_input("Note (reason for an exclusion)", value=row.get("review_note", ""), key=f"note_{k}",
                      on_change=on_review, args=(row["row_id"], single))


def show_balance(ds: dict) -> None:
    st.dataframe(lab.balance_table(ds), width="stretch")
    ok, msg = lab.balance_status(ds)
    (st.success if ok else st.warning)(msg)


def generator_heading(ds: dict, role: str) -> str:
    if ds["source_type"] == "fixture":
        return f"**Fixture set for the {role} slot**  \nhand-authored, not a model"
    rows = [r for r in ds["rows"] if r["generator_role"] == role]
    model = rows[0]["generator_model"] if rows else ss[f"model_{role}"].strip()
    return f"**{role} generator**  \n`{model}`"


# ------------------------------------------------------------------ header --
st.title("Classroom generator: TRUE vs FALSE tobacco claims")
st.warning(lab.EXERCISE_WARNING)
st.info(f"{lab.CORRECTION}  \nSource: [WHO tobacco fact sheet]({lab.WHO_URL})")

# ----------------------------------------------------------------- sidebar --
with st.sidebar:
    st.header("Settings")
    offline = st.toggle("Offline mode (no network calls)", value=True, key="offline")
    if key:
        st.success(f"OpenRouter key found ({key_source})")
    else:
        st.warning("No OpenRouter key found. Live buttons are disabled.")
    if cfg_problem:
        st.error(cfg_problem)
    st.subheader("Generator models")
    for role in lab.ROLES:
        st.text_input(f"{role} model ID", key=f"model_{role}")
        st.caption(f"Exact ID: `{ss[f'model_{role}'].strip()}` · {lab.documented_size(cfg, ss[f'model_{role}'].strip())}")
    st.subheader("Detector models")
    st.caption("Chosen independently of the generators.")
    for role in lab.ROLES:
        st.text_input(f"{role} detector model ID", key=f"det_model_{role}")
        st.caption(f"Exact ID: `{ss[f'det_model_{role}'].strip()}`")
    st.subheader("Provider routing")
    st.caption("Same model, chosen endpoint; sent with every request.")
    st.json(lab.routing(cfg) or {"routing": "OpenRouter default"})

live = (not offline) and bool(key)
ds = ss.dataset

tab_gen, tab_det = st.tabs(["Generate", "Detect & compare"], key="main_tabs", on_change="rerun")

# ============================================================ Generate tab ==
with tab_gen:
    if not live:
        st.caption("Live generation is disabled: " + ("offline mode is on." if offline else "no API key found."))

    st.header("Generate one example")
    c1, c2, c3 = st.columns(3)
    role1 = c1.selectbox("Model", list(lab.ROLES), key="single_role")
    c1.caption(f"Exact ID: `{ss[f'model_{role1}'].strip()}`")
    fmt1 = c2.selectbox("Format", list(lab.FORMATS), format_func=lambda f: lab.FORMATS[f]["label"], key="single_fmt")
    label1 = c3.radio("Claim", ["false", "true"], format_func=lambda l: lab.LABEL_NAMES[l], key="single_label")
    if st.button("Generate one example (1 paid call)", disabled=not live):
        try:
            res = lab.generate(key, role1, ss[f"model_{role1}"], lab.single_slot(label1, fmt1), cfg)
            log_call(res)
            ss.singles.extend(res["rows"])
            ss.single_problems.extend(res["problems"])
            say("success" if res["ok"] else "error", res["message"])
        except ValueError as e:
            say("error", str(e))

    st.header("Generate a balanced set")
    st.caption("One batch call per generator; both models get the same 4 assignments "
               "(TRUE/FALSE claim x social post/scientific paragraph).")
    if st.button("Generate balanced set (2 paid calls)", disabled=not live or bool(ds["frozen"])):
        for role in lab.ROLES:
            try:
                res = lab.generate(key, role, ss[f"model_{role}"], lab.balanced_slots(), cfg)
                log_call(res)
                lab.store_generation(ds, role, res)
                say("success" if res["ok"] else "error", res["message"])
            except ValueError as e:
                say("error", str(e))
                break

    st.header("Offline fixtures")
    o1, o2 = st.columns(2)
    if o1.button("Load the 8 offline fixtures (hand-authored)"):
        try:
            lab.load_fixtures(ds)
            say("info", "Loaded 8 hand-authored fixtures. They are NOT model output and never count as measurements.")
        except ValueError as e:
            say("error", str(e))
    o2.button("Clear dataset", on_click=clear_dataset, disabled=bool(ds["frozen"]))

    for kind, text in ss.messages[-6:]:
        getattr(st, kind)(text)

    st.header(f"Dataset ({len(ds['rows'])} rows)")
    if ds["source_type"]:
        st.caption(f"Source: {ds['source_type']} · {ds.get('provenance') or ''}")
    if ds["frozen"]:
        st.caption("The dataset is frozen: reviews are locked. Unfreeze it in the Detect & compare tab.")
    for row in ds["rows"]:
        card(row)
    if ss.singles:
        st.header(f"Single examples ({len(ss.singles)}, not part of the balanced dataset)")
        for row in ss.singles:
            card(row, single=True)

    st.header("Generation failures")
    problems = ds["problems"] + ss.single_problems
    if problems:
        st.dataframe(problems, width="stretch")
    else:
        st.caption("None.")

    st.header("Calls: time and cost")
    if ss.calls:
        st.dataframe([{"kind": c.get("kind"), "role": c.get("role"), "model": c.get("model_requested"),
                       "status": c.get("status"), "message": c.get("message"), "elapsed_s": c.get("elapsed_s"),
                       "cost": lab.cost_text(c.get("cost_usd")), "started_utc": c.get("started_at_utc")}
                      for c in ss.calls], width="stretch")
    else:
        st.caption("No calls yet.")

    st.header("Balance")
    show_balance(ds)

# ==================================================== Detect & compare tab ==
with tab_det:
    st.info(lab.DETECTION_NOTE)
    ep = lab.EVIDENCE_PACKET
    with st.expander("Evidence packet (identical for both detectors)"):
        st.markdown(f"**Source:** {ep['source']}  \n**URL:** {ep['url']}  \n**Retrieved:** {ep['retrieved']}")
        for item in ep["items"]:
            st.markdown(f"- **{item['id']}** {item['text']}")

    # ---- Step 1: freeze
    st.header("Step 1: freeze the approved rows")
    show_balance(ds)
    n_approved = sum(r["review_status"] == "approved" for r in ds["rows"])
    if not ds["frozen"]:
        st.caption("Only approved rows enter. Freezing fixes the order and the blind IDs before any verdict exists.")
        if not ds["rows"]:
            st.warning("No rows yet: generate a balanced set (or load the offline fixtures) in the Generate tab.")
        elif n_approved == 0:
            st.warning("No approved rows yet: in the Generate tab, set **Review** to **approved** on every card you "
                       "accept (exclude the others with a note). Then freeze here.")
        if st.button(f"Freeze the {n_approved} approved row(s) (no network)", disabled=n_approved == 0):
            try:
                lab.freeze(ds)
                ss.detections = {}
                ss.det_messages = [("success", f"Frozen {len(ds['frozen_order'])} row(s).")]
            except ValueError as e:
                say_det("error", str(e))
            st.rerun()
    else:
        st.success(f"Frozen: {len(ds['frozen_order'])} row(s) · hash `{ds['frozen_hash'][:16]}` · "
                   "order and blind IDs fixed")
        u1, u2 = st.columns([2, 1])
        confirm = u1.checkbox("Confirm unfreeze (clears the detector results; changing the selection after "
                              "seeing verdicts would be post-hoc selection)", key="confirm_unfreeze")
        u2.button("Unfreeze", disabled=not confirm, on_click=do_unfreeze)
        with st.expander("Exactly what each detector receives (blind IDs + passages only)"):
            st.json(lab.detector_input(ds))

    # ---- Step 2: run
    st.header("Step 2: run the detectors")
    frozen = bool(ds["frozen"])
    det_live = live and frozen
    if not frozen:
        st.warning("The detector buttons unlock after Step 1: freeze the approved rows first.")
    elif not live:
        st.warning("Live detection is disabled: " + ("offline mode is on." if offline else "no API key found."))
    todo = []
    if st.button("Run both detectors (2 paid calls)", disabled=not det_live):
        todo = list(lab.ROLES)
    rc = st.columns(len(lab.ROLES))
    for col, role in zip(rc, lab.ROLES):
        if col.button(f"Retry {role} detector only (1 paid call)", disabled=not det_live, key=f"retry_{role}"):
            todo = [role]
    if todo:
        if any(d.get("kind") != "live" for d in ss.detections.values()):
            ss.detections = {}             # never mix illustrative and measured verdicts
        for role in todo:
            try:
                d = lab.detect(key, role, ss[f"det_model_{role}"], ds, cfg)
                log_call(d)
                ss.detections[role] = d
                say_det("success" if d["ok"] else "error", d["message"])
            except ValueError as e:
                say_det("error", str(e))
        st.rerun()
    if ds["source_type"] == "fixture":
        if st.button("Show illustrative verdicts (hand-authored, NOT measured)", disabled=not frozen):
            try:
                ss.detections = lab.illustrative_detections(ds)
                ss.det_messages = [("warning", "Illustrative verdicts loaded: hand-authored, NOT measured.")]
            except ValueError as e:
                say_det("error", str(e))
            st.rerun()
    for kind, text in ss.det_messages[-6:]:
        getattr(st, kind)(text)

    dets = {r: d for r, d in ss.detections.items() if frozen and d.get("frozen_hash") == ds.get("frozen_hash")}

    # ---- Results
    st.header("Results")
    if not frozen:
        st.caption("Freeze the dataset first.")
    elif not dets:
        st.caption("No detector results yet.")
    else:
        if any(d["kind"] == "illustrative" for d in dets.values()):
            st.warning("These verdicts are ILLUSTRATIVE: hand-authored, NOT measured.")
        for role, d in dets.items():
            st.caption(f"{role} detector: `{d['detector_model']}` · {d['message']}")
        reveal = st.toggle("Reveal intended labels and generators", value=False, key="reveal")
        table = []
        for row in lab.frozen_rows(ds):
            entry = {"blind ID": row["blind_id"], "passage": row["passage"]}
            if reveal:
                entry["intended label"] = lab.LABEL_NAMES[row["intended_label"]]
                entry["generator"] = (f"fixture ({row['generator_role']} slot)" if row["source_type"] == "fixture"
                                      else f"{row['generator_role']}: {row['generator_model']}")
            for role in lab.ROLES:
                res = dets.get(role, {}).get("results", {}).get(row["row_id"])
                if res is None:
                    entry[f"{role} verdict"] = "not run"
                elif res["status"] == "predicted":
                    entry[f"{role} verdict"] = res["verdict"]
                    entry[f"{role} reason"] = res["reason"]
                    entry[f"{role} evidence"] = res["evidence_ref"]
                    if reveal:
                        ok = lab.is_correct(row, res)
                        entry[f"{role} correct"] = "abstained" if ok is None else ("yes" if ok else "no")
                else:
                    entry[f"{role} verdict"] = f"FAILURE: {res.get('detail', '')}"
            table.append(entry)
        st.dataframe(table, width="stretch", hide_index=True)
        for role, d in dets.items():
            if d.get("problems"):
                st.warning(f"{role} detector: format problems (counted as failures, not predictions)")
                st.dataframe(d["problems"], width="stretch")

    # ---- Matrix
    st.header("2x2 matrix: generator (rows) x detector (columns)")
    if frozen:
        m = lab.matrix(ds, dets)
        hdr = st.columns(len(lab.ROLES) + 1)
        hdr[0].markdown("**generator \\ detector**")
        for i, d_role in enumerate(lab.ROLES):
            model = dets[d_role]["detector_model"] if d_role in dets else ss[f"det_model_{d_role}"].strip()
            hdr[i + 1].markdown(f"**{d_role} detector**  \n`{model}`")
        for g_role in lab.ROLES:
            cols = st.columns(len(lab.ROLES) + 1)
            cols[0].markdown(generator_heading(ds, g_role))
            for i, d_role in enumerate(lab.ROLES):
                with cols[i + 1].container(border=True):
                    st.markdown(lab.cell_summary(m.get((g_role, d_role))))
    else:
        st.caption("Freeze the dataset first.")
    st.caption(lab.SCORING_NOTE)
    st.caption(lab.SMALL_SAMPLE_NOTE)

    # ---- Pasted passage
    st.header("Assess a pasted passage (verdict only, never scored)")
    text = st.text_area("Passage to assess (treated as untrusted data)", key="paste_text")
    ticked = [r for r in lab.ROLES
              if st.checkbox(f"{r} detector (`{ss[f'det_model_{r}'].strip()}`)", value=True, key=f"paste_{r}")]
    # Not disabled on empty text: a text area only commits on blur, so a disabled button would swallow the click.
    if st.button(f"Assess pasted passage ({len(ticked)} paid call(s))", disabled=not live or not ticked):
        if not text.strip():
            st.error("Paste a passage into the text box first.")
        for role in ticked if text.strip() else []:
            p = lab.assess_pasted(key, role, ss[f"det_model_{role}"], text, cfg)
            log_call(p)
            ss.pasted.append(p)
    if not live:
        st.warning("Live assessment is disabled: " + ("offline mode is on." if offline else "no API key found."))
    elif not ticked:
        st.warning("Tick at least one detector.")
    for p in reversed(ss.pasted):
        with st.container(border=True):
            st.markdown(f"**{p['role']} detector** `{p['detector_model']}` · "
                        + (f"verdict **{p['verdict']}** · evidence {p['evidence_ref']}"
                           if p["status"] == "predicted" else f"FAILURE: {p.get('detail', '')}"))
            if p["status"] == "predicted":
                st.write(p["reason"])
            st.code(p["passage"], language=None, wrap_lines=True)
            st.caption(p["message"] + " · not scored")

# ------------------------------------------------------------------ export --
st.download_button("Download JSON (everything, with exercise warning, no key)",
                   lab.export_json(ds, ss.singles, ss.calls, ss.detections, ss.pasted),
                   file_name="classroom_export.json", mime="application/json")
