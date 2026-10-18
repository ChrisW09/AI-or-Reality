# Prompt A: build the generator

**When:** minute 14:45, after the slide "Live build 1 in VS Code".
**Where:** VS Code → folder `live-coding-start/` (the starter kit) → Claude Code panel (Command Palette: *Claude Code: Open in New Tab*), permission mode **Edit automatically**.
**Before you paste:** the folder holds the starter kit (`CLAUDE.md`, `lab.py` and the tested modules, `smoke_test.py`, `.venv/`). There is no `app.py` yet; run `tools/reset-live-coding-start.sh` if there is. There is no API key in this prompt.
**Expect:** well under 1 minute. In headless rehearsal of this version (18 Oct 2026) it took 33–39 s in 3 runs with Claude Code 2.1.302 (Opus 5.5), smoke test included. Read the report, then start the app with `.venv/bin/python -m streamlit run app.py`.
**Same app every time:** `CLAUDE.md` pins the layout and the exact labels of the instructor-approved app (`reference-apps/app_after_prompt_a.py`), and the smoke test fails if a required button is missing. There is no review step: every generated row goes to detection. In those 3 replays the result matched the reference app's structure exactly. If a live result still differs, `tools/use-reference-app.sh a` puts the reference app in place in seconds.
**Fallback:** if there is no usable app after about 3 minutes, keep teaching and run `fallback/stage1-generator/` instead (see the runbook).

Paste everything inside the box below exactly as written, as one message.

*Change on 18 Oct 2026:* the original prompt (62 lines, empty folder) is replaced by this short one on top of the starter kit. The rules it used to spell out, such as one request per button, no retries, blinding and scoring, now live in the tested kit and in `CLAUDE.md`. The previous version is kept in `docs/previous-prompts/`.

```text
Build app.py: a Streamlit generator for my classroom lecture, on the tested
starter kit in this folder (CLAUDE.md lists its API). Write only app.py and
do not change the kit files.

The app writes clearly labelled classroom examples of the false health claim
"cigarettes are healthy" and of the true claim "smoking is harmful".

- Always visible at the top: exercise warning, correction and WHO link.
- Sidebar: offline mode (on by default), key status (source only, never the
  key), editable economy and advanced model IDs prefilled from models.json,
  and the provider routing.
- Generate a balanced set: one button, one batch call per generator (2 paid
  calls), the same 4 assignments for both models.
- Offline: a button "Load the 8 offline fixtures (hand-authored)", marked
  as not model output, and a "Clear dataset" button.
- Show every row as a card: passage, intended label, generator with exact
  model ID and hints. No review step: every row goes to detection later.
- Show generation failures and time and cost per call.
- A JSON download of everything (lab.export_json).

Then run the smoke test, fix any error, and give me the start command.
```
