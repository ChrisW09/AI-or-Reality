# Prompt B: add detection and the comparison

**When:** minute 29:30, after reading the generated cards, in the **same** project folder and the same Claude Code conversation (a new conversation also works, because `CLAUDE.md` and the prompt describe everything it needs).
**Before you paste:** keep the Streamlit app running. Prompt B only changes `app.py` and keeps the session-state keys, and the kit's `.streamlit/config.toml` sets `runOnSave = true`, so the app reloads by itself each time the assistant saves and the generated rows stay in the browser session (checked in Chrome on 18 Oct 2026: the new tab appeared 0.3 s after the save, with all 8 rows kept). If the tab does not appear, press **R** in the browser. As insurance, download the JSON export first.
**Expect:** about 1 minute. In headless rehearsal of this version (18 Oct 2026) it took 60–66 s in 3 runs with Claude Code 2.1.302 (Opus 5.5), smoke test included. No review or freeze step: `lab.freeze_all` blinds and shuffles every passage right before the detector calls.
**Same app every time:** `CLAUDE.md` pins the layout and exact labels of the instructor-approved app (`reference-apps/app_after_prompt_b.py`), and the smoke test checks its buttons. In 3 replays of A then B, both results matched the reference apps' structure exactly. If a live result differs, run `tools/use-reference-app.sh b`.
**If the app shows HTTP 429 (rate limited):** this is Mistral's short burst limit, not a bug. Wait about 10 s, then press **Retry <role> detector only (1 paid call)**; the other detector's results are kept. In rehearsal it cleared within seconds.
**Fallback:** if the extension is not usable after about 3 minutes, switch to `fallback/full-app/` (see the runbook).

Paste everything inside the box below exactly as written, as one message.

*Change on 18 Oct 2026:* the original prompt (71 lines) is replaced by this short one. The evidence packet, blinding, verdict parsing and scoring rules now live in the tested kit (`detection.py`, `lab.py`) and in `CLAUDE.md`. The previous version is kept in `docs/previous-prompts/`.

```text
Add a second tab "Detect & compare" to app.py, using the detection part of
the kit (CLAUDE.md). Keep the generator working. Write only app.py.

- Show lab.DETECTION_NOTE and the evidence packet (source, URL, retrieved).
- Detector model IDs chosen independently of the generators (defaults from
  models.json).
- "Run both detectors (2 paid calls)" on all generated passages, plus one
  button per detector for an explicit single retry. No review or freeze
  step: lab.freeze_all blinds and shuffles the passages first. Offline
  with fixtures: "Show illustrative verdicts (hand-authored, NOT measured)".
- Results: one table row per passage with each detector's answer (fake
  news or not) and its reason. A toggle reveals intended labels and
  generators, hidden by default.
- The 2x2 matrix, generator rows x detector columns, with lab.cell_summary
  in each cell, plus lab.SCORING_NOTE and lab.SMALL_SAMPLE_NOTE.
- Check a pasted passage: text area, tick the detectors, one button (1 paid
  call per ticked detector). Verdict only, never scored.
- Add detections and pasted results to the JSON download.

Then run the smoke test, fix any error, and give me the restart command.
```
