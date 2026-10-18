# Classroom lab: starter kit for a live build

This folder is used in a live lecture. A clock is running: **speed matters more than polish**.

## Your job

You write **one file: `app.py`** (Streamlit). Everything else is a tested kit. **Do not edit**
`lab.py`, `generation.py`, `detection.py`, `openrouter_client.py`, `fixtures.json`, `models.json`,
`smoke_test.py` or `tests/`.

## Work fast

- Do not explore. This file documents the whole API you need; read `lab.py` only if something here is unclear.
- No plan, no todo list, no subagents, no questions. Write `app.py` in one go.
- Do not write test files, READMEs or other files. Do not run `pytest` (the kit tests already pass).
- Change `app.py` only with your Write/Edit tools (no shell scripts, heredocs or `sed`).
- Check with exactly this command, unchanged (no pipes, redirects or `cd`; its output is short):
  `.venv/bin/python smoke_test.py` (offline, no key, a few seconds). If it fails, fix `app.py` and run it again.
  Anything else triggers a permission prompt in front of the audience.
- Never make a live or paid call, never start the Streamlit server, never read `.env` or `.streamlit/secrets.toml`.
- Final answer: at most 6 lines: what you built, the smoke-test result, the start command `.venv/bin/python -m streamlit run app.py`.

## Rules the app must keep

- Every model call happens only after an explicit `st.button` press. Store everything in `st.session_state`
  (`ss.setdefault(...)`) so reruns and widget changes never call a model.
- Offline mode toggle in the sidebar, **on by default**. Live buttons are disabled without a key.
- Show `lab.EXERCISE_WARNING` and `lab.CORRECTION` with a link to `lab.WHO_URL` permanently (top of the page),
  **outside** the passages. Never offer sharing or publishing.
- Show exact model IDs. Show `message` strings from the kit as they are (errors are already sanitized).
- Kit functions raise `ValueError` for a forbidden step (mixing fixtures and live rows, changing a frozen
  dataset, freezing nothing). Wrap every kit call made from a button in `try/except ValueError` and show `st.error(str(e))`.
- Never put the API key in session_state, on screen or in an export.
- Use `st.session_state["dataset"]` for the dataset and `st.session_state["detections"]` ({role: d}) for detector
  results (the smoke test reads both). When extending the app, keep every existing session_state key: the app
  stays running in the browser and must keep its generated rows after the code changes.
- Streamlit 1.66: use `width="stretch"`, not the deprecated `use_container_width`.

## App layout after Prompt A (build exactly this; labels verbatim)

There is **no review or approval step**: generated rows go straight to detection in Prompt B.
One page, no tabs yet (Prompt B adds tabs). Top to bottom:

1. `st.set_page_config(page_title="Classroom claim generator", layout="wide")`;
   `st.title("Classroom generator: TRUE vs FALSE tobacco claims")`;
   `st.warning(lab.EXERCISE_WARNING)`; `st.info(f"{lab.CORRECTION}  \nSource: [WHO tobacco fact sheet]({lab.WHO_URL})")`.
2. Sidebar: `st.header("Settings")`; `st.toggle("Offline mode (no network calls)", value=True, key="offline")`;
   key status `st.success(f"OpenRouter key found ({source})")` or
   `st.warning("No OpenRouter key found. Live buttons are disabled.")`; `models.json` problem as `st.error`;
   `st.subheader("Generator models")` with one `st.text_input(f"{role} model ID", key=f"model_{role}")` per role
   (prefill via `ss.setdefault(f"model_{role}", default_id)`, no `value=`) and a caption with the exact ID and
   `lab.documented_size`; `st.subheader("Provider routing")` with a caption and `st.json(lab.routing(cfg))`.
   Live = offline toggle off **and** a key.
3. `st.header("Generate a balanced set")`, a caption on the same 4 assignments, a caption why live generation is
   disabled (if it is), then `st.button("Generate balanced set (2 paid calls)", disabled=not live)`:
   `lab.generate` + `lab.store_generation` per role. (No single-example generator.)
4. `st.header("Offline fixtures")`, two columns: `st.button("Load the 8 offline fixtures (hand-authored)")` and
   `st.button("Clear dataset", on_click=...)` (callback sets a new dataset).
5. The last messages (`ss["messages"]`, list of (kind, text), shown with `st.success`/`st.error`/`st.info`).
6. `st.header(f"Dataset ({n} rows)")`, a caption with the source, one card per row.
   Card = `st.container(border=True)`: bold row ID · format label · intended label; a caption "FIXTURE:
   hand-authored for the offline demonstration, NOT model output" or "role generator · `model ID` · provenance";
   the passage with `st.code(passage, language=None, wrap_lines=True)`; flags as `st.warning("Hints: ...")`.
   **No review radio, no note, no approve/exclude.**
7. `st.header("Generation failures")` (dataframe or "None."), `st.header("Calls: time and cost")` (kind, role,
   model, status, message, elapsed_s, cost via `lab.cost_text`, started_utc).
8. `st.download_button("Download JSON (everything, with exercise warning, no key)", lab.export_json(ds, [], calls),
   file_name="classroom_export.json")`.

Session-state keys: `dataset`, `calls`, `messages`, `offline`, `model_<role>`.
AppTest quirk: never give a widget a `format_func` that reads `st.session_state`; the smoke test then crashes.

## App layout after Prompt B (extend to exactly this; labels verbatim)

Keep the header, the sidebar and everything from Prompt A; add only what is listed here. Still **no review and no
separate freeze step**: the detectors assess every row; `lab.freeze_all(ds)` fixes order and blind IDs right
before the calls.

1. New session-state keys: `ss.setdefault("detections", {})`, `"det_messages"` (list of (kind, text)), `"pasted"`
   (list), and `ss.setdefault(f"det_model_{role}", default_id)` per role. `clear_dataset` also resets `detections`.
   Before generating or loading fixtures: unfreeze if frozen and reset `detections` (new rows, new verdicts).
2. Sidebar, after "Generator models": `st.subheader("Detector models")`, a caption "Chosen independently of the
   generators.", then `st.text_input(f"{role} detector model ID", key=f"det_model_{role}")` + caption with the exact ID.
3. After the sidebar: `tab_gen, tab_det = st.tabs(["Generate", "Detect & compare"], key="main_tabs", on_change="rerun")`
   (the key keeps the selected tab after `st.rerun()`). Everything of Prompt A below the sidebar goes into `tab_gen`,
   except the download button, which moves below both tabs.
4. `tab_det`, top to bottom:
   - `st.info(lab.DETECTION_NOTE)`; `st.expander("Evidence packet (identical for both detectors)")` with source,
     URL, retrieved date and the items E1–E4.
   - `st.header("Run the detectors")`; a caption that each detector gets every passage shuffled with a blind ID plus
     the evidence packet, never the label or the generator; `st.warning("No rows yet: generate a balanced set (or
     load the offline fixtures) in the Generate tab.")` if empty, else an `st.warning` why live is disabled.
     `st.button("Run both detectors (2 paid calls)")` and one column per role with
     `st.button(f"Retry {role} detector only (1 paid call)", key=f"retry_{role}")`, disabled unless live and rows
     exist. On click: `lab.freeze_all(ds)` (for both, or if not frozen yet), then `lab.detect` per role into
     `ss["detections"]`; never mix live with illustrative results; `st.rerun()` after.
     If `ds["source_type"] == "fixture"`: `st.button("Show illustrative verdicts (hand-authored, NOT measured)")` ->
     `lab.freeze_all(ds)`, `ss["detections"] = lab.illustrative_detections(ds)`. Then the last `det_messages`.
   - Use only detections whose `frozen_hash` equals the dataset's.
   - `st.header("Fake news or not? Every passage")`: an `st.warning` if illustrative; a caption per detector (model,
     message); `st.toggle("Reveal intended labels and generators", value=False, key="reveal")`; one dataframe row per
     `lab.frozen_rows(ds)` with blind ID, passage, (if revealed) intended label and generator, and per role
     `f"{role} says"` = `lab.fake_news_label(result)` and `f"{role} reason"` (reason + evidence ref, or the failure
     detail), plus `f"{role} correct"` via `lab.is_correct` when revealed; then each detector's format problems.
   - `st.header("2x2 matrix: generator (rows) x detector (columns)")`: if there are results, a header row of
     columns (detector role + exact model), then one row of columns per generator role (heading with role and model,
     or "Fixture set for the <role> slot") with `lab.cell_summary(...)` inside `st.container(border=True)`; else a
     caption "Run the detectors first."; then `st.caption(lab.SCORING_NOTE)` and `st.caption(lab.SMALL_SAMPLE_NOTE)`.
   - `st.header("Check a pasted passage (verdict only, never scored)")`:
     `st.text_area("Passage to check (treated as untrusted data)", key="paste_text")`, one
     ``st.checkbox(f"{role} detector (`{det_model}`)", value=True, key=f"paste_{role}")`` per role (model ID in backticks),
     `st.button(f"Check pasted passage ({n} paid call(s))", disabled=not live or not ticked)`: **never disable it on
     empty text** (a text area commits only on blur, so the click would be swallowed); on click with empty text show
     `st.error("Paste a passage into the text box first.")`, otherwise `lab.assess_pasted` per ticked role into
     `ss["pasted"]`; show each result in a bordered container (role, model, `lab.fake_news_label(p)`, reason,
     passage, "not scored").
5. Below both tabs: the download button from Prompt A, now `lab.export_json(ds, [], calls, detections, pasted)`.

## `import lab`: everything you need

```python
cfg, problem = lab.load_models()          # models.json; problem is a str or None (show it)
lab.default_model_ids(cfg)                # {"economy": "mistralai/...", "advanced": "mistralai/..."}
lab.routing(cfg)                          # {"order": ["mistral/eu"], "allow_fallbacks": False} (applied automatically)
lab.documented_size(cfg, model_id)        # str
key, source = lab.get_api_key(st.secrets) # (None, None) if missing; show only `source`, never the key
lab.ROLES                                 # ("economy", "advanced")
lab.FORMATS                               # {"social_post": {"label": ...}, "scientific_prose": {"label": ...}}
lab.LABEL_NAMES                           # {"true": "TRUE claim (supported)", "false": "FALSE claim (contradicted)"}
lab.cost_text(x)                          # "US$0.000160" or "unavailable (not returned)"

# generation: each generate() call is ONE paid request
lab.balanced_slots()                      # 4 slots: TRUE/FALSE x social/science (same for both models)
res = lab.generate(key, role, model_id, slots, cfg)
#   res = {"rows": [row...], "problems": [...], "call": {...}, "ok": bool, "message": str}
ds = lab.new_dataset()                    # dict, keep in session_state
lab.store_generation(ds, role, res)       # replaces that generator's earlier rows (balanced set only); raises ValueError
                                          #   if ds holds fixtures or is frozen
lab.load_fixtures(ds)                     # 8 hand-authored offline rows, pre-approved; raises ValueError if ds has live rows
lab.export_json(ds, singles, calls, detections, pasted)  # JSON str for st.download_button

# row fields: row_id, source_type ("live"|"fixture"), provenance, generator_role, generator_model,
#   format, intended_label ("true"|"false"), central_claim, passage, review_status, review_note,
#   flags (list of review hints), created_at_utc
# problem fields: generator_role, slot_id, label, format, problem, detail
# ds fields: source_type, rows, problems, frozen, frozen_hash, frozen_order, blind_ids

# detection (step 2): each detect()/assess_pasted() call is ONE paid request
lab.freeze_all(ds)                        # USE THIS: takes every row (max 8), then hash, shuffled order, blind IDs; re-freezes
                                          #   if already frozen; no network; raises ValueError if there are no rows
lab.freeze(ds)                            # (approved rows only; not needed in this app)
lab.unfreeze(ds)
lab.frozen_rows(ds)                       # frozen rows in frozen order, each with "blind_id"
lab.detector_input(ds)                    # exactly what a detector sees: [{"id": blind_id, "text": passage}]
d = lab.detect(key, role, model_id, ds, cfg)
#   d = {"kind": "live", "detector_model", "results": {row_id: result}, "problems", "call", "ok", "message"}
#   result = {"status": "predicted", "verdict", "reason", "evidence_ref"} or {"status": "failure", "detail"}
lab.illustrative_detections(ds)           # offline, frozen fixtures only: {role: d}, kind "illustrative" (NOT measured)
m = lab.matrix(ds, detections)            # {(generator_role, detector_role): metrics or None}; detections = {role: d}
lab.cell_summary(metrics)                 # markdown for one cell, with denominators
lab.is_correct(row, result)               # True / False / None (abstention or failure)
lab.fake_news_label(result)               # "FAKE NEWS (contradicted ...)" / "not fake news (...)" / "unsure (...)" / failure / not run
p = lab.assess_pasted(key, role, model_id, text, cfg)   # verdict only, never scored
#   p = {"status", "verdict", "reason", "evidence_ref", "detail", "call", "message"}
lab.EVIDENCE_PACKET                       # {"source", "url", "retrieved", "items": [{"id", "text"}]}
lab.DETECTION_NOTE, lab.SCORING_NOTE, lab.SMALL_SAMPLE_NOTE   # show these texts in the detection tab
```
