# Lecture runbook: *AI or Reality? Can We Tell the Difference?* (60 min)

This is the instructor's guide for one live lecture: the image challenge, a short LLM introduction, a live build of a Streamlit app with an AI coding assistant, then a generator × detector comparison.

- Student-facing wording appears in **"quotes"** in the SAY column.
- Everything else is for the instructor only.
- Slide numbers (p…) refer to `lecture-slides.pdf` (47 pages: main flow p1–p26, appendix p27–p46, *Resources and contact* p47).
- The presenter notes are in `lecture-slides-with-notes.pdf`.

**What changed on 18 Oct 2026.** The live build no longer starts from an empty folder. `live-coding-start/` now holds a tested **starter kit**, and the assistant writes only `app.py` on top of it. Both prompts are short. Measured in headless replays, each prompt now takes about **1 minute** instead of 6 and 17 (section 5). That means the lecture can stay in the assistant's own app from the first build to the end. The fallback apps are still there, but you should no longer need them.

---

## 1. What is in the package, and when to open what

| Path | What it is | When |
|---|---|---|
| `lecture-slides.pdf` | Audience deck (notes hidden) | Projected all lecture |
| `lecture-slides-with-notes.pdf` | Slide left, notes right (timings, what to click, fallbacks) | On your second screen |
| `live-coding-start/` | **Teaching folder = starter kit**: `CLAUDE.md`, `lab.py` and the tested modules, fixtures, `models.json`, `smoke_test.py`, `.claude/settings.json`, plus your `.venv/` and (optionally) `.env`. **No `app.py`**: the assistant writes it | Open in VS Code at 14:00 for Prompt A, keep it for Prompt B |
| `starter-kit/` | The pristine copy of the kit. `tools/reset-live-coding-start.sh` restores the teaching folder from it | Preparation only |
| `prompts/01-build-generator.md` | Prompt A, exact text (paste the text block only) | 14:45 |
| `prompts/02-add-detection.md` | Prompt B, exact text | ~29:30 |
| `fallback/stage1-generator/` | Tested stage-one snapshot: the generator only | Only if the live build fails |
| `fallback/full-app/` | Tested complete app: Generate + Detect & compare, offline mode, recorded rehearsal run | Only if the live build fails, or when the API fails (recorded run) |
| `docs/` | This runbook, the source/reuse map, the validation report, and the previous (empty-folder) prompts | Preparation |

Keep `fallback/` and `starter-kit/` out of the VS Code workspace during class. The assistant should only ever see `live-coding-start/`.

---

## 2. Preflight

### The day before

1. **Python environment inside the teaching folder.** Tested with Python 3.12.13, streamlit 1.66.0 and requests 2.34.2. The kit's `CLAUDE.md` and the permission file expect it at `live-coding-start/.venv/`:
   ```bash
   cd lecture-package/live-coding-start
   uv venv --python 3.12 .venv                 # or: python3.12 -m venv .venv
   uv pip install --python .venv/bin/python -r requirements.txt
   ```
   The same requirements cover both fallback apps.
2. **Run the tests** (no network, no cost):
   ```bash
   (cd live-coding-start && .venv/bin/python -m pytest -q tests)   # expect: 90 passed (the kit)
   (cd fallback/stage1-generator && ../../live-coding-start/.venv/bin/python -m pytest -q tests)   # expect: 55 passed
   (cd fallback/full-app && ../../live-coding-start/.venv/bin/python -m pytest -q tests)           # expect: 93 passed
   ```
3. **Coding assistant.** Install and log in to *Claude Code for VS Code* (CLI 2.1.302 and extension 2.1.301 at preparation).
   - It needs its **own Claude account** (subscription or pay-as-you-go). The OpenRouter key does not give you a coding assistant.
   - Check that the Command Palette shows **Claude Code: Open in New Tab** (shortcut ⌘⇧Esc).
   - Model: the default (**Opus 5.5**) is fine. In rehearsal, effort *high*, *medium* and *low* and fast mode all finished within the same 35–66 s band (section 5), so you do not need to change anything.
4. **Trust the teaching folder once (important).** Open `live-coding-start/` in VS Code, open Claude Code, and accept the trust dialog. Until a folder is trusted, Claude Code **ignores the project's `permissions.allow` rules**: the smoke-test command would then ask for permission in front of the audience. Do this in the real folder, not a copy, because trust is stored per path.
5. **Choose the permission mode: Edit automatically.** VS Code takes its starting mode from its own settings (`claudeCode.initialPermissionMode`) or from the mode menu under the prompt box, not from the project file. Pick **Edit automatically** there.
   - With it, `app.py` edits and the one allowed command (`.venv/bin/python smoke_test.py`) need no clicks.
   - *Manual* also works but adds one click per edit.
   - Do not use *Bypass permissions*.
   - The project file `.claude/settings.json` denies reading `.env` and `.streamlit/secrets.toml` and blocks `curl`/`wget`. The deny rules cover the assistant's file tools; a Python script it ran could still open a file. The kit never asks it to.
6. **Dress rehearsal in VS Code (recommended, ~5 min).** Paste Prompt A, then Prompt B, exactly as in class, and note both times. This is the one check not yet done in the real extension (validation report §4). Then reset (below).
7. **Rehearse the offline path once.** In the app built during the dress rehearsal, with the offline toggle on:
   1. **Load the 8 offline fixtures (hand-authored)**.
   2. Under *Detect & compare*: **Show illustrative verdicts (hand-authored, NOT measured)**. There is no review or freeze step; the app blinds and freezes the passages itself.
   3. For the recorded rehearsal run (real outputs, no network), use `fallback/full-app`: sidebar → **Load recorded rehearsal run**.

### 30 minutes before

1. **Reset the teaching folder** to the clean kit. This deletes the assistant's `app.py` and anything else it wrote, and keeps `.venv/` and `.env`:
   ```bash
   lecture-package/tools/reset-live-coding-start.sh    # prints what it removes, then the folder contents
   ```
   Afterwards there is no `app.py`, and `(cd live-coding-start && .venv/bin/python -m pytest -q tests)` still gives 90 passed.
2. **API key, off-screen, before you project.** Choose one way:
   - **Environment variable:** in the VS Code integrated terminal you will use to start Streamlit:
     ```bash
     read -rs OPENROUTER_API_KEY; export OPENROUTER_API_KEY   # nothing is echoed or stored in history
     echo ${#OPENROUTER_API_KEY}                               # prints only the length
     ```
     Export it only in that terminal, not in your shell profile.
   - **`.env` file:** `live-coding-start/.env` with `OPENROUTER_API_KEY=...` (Git-ignored; the reset script keeps it). The kit reads the environment first, then `.env`, then `.streamlit/secrets.toml`.
   - Never type the key on screen, and never paste it into the coding-assistant chat.
3. **Check the remaining credit** without printing the key (it showed a US$50 limit at preparation):
   ```bash
   curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/key \
     | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print({k: d.get(k) for k in ('limit','limit_remaining','usage')})"
   ```
4. **Screen set-up.**
   - Slides on the projector, the notes PDF on your screen.
   - VS Code with no folder open and the terminal ready.
   - A browser tab for `http://localhost:8501`.
   - Zoom VS Code and the browser for the room (⌘+).
5. **Session state lives in the running server.** The app's rows live in the browser session of the running Streamlit server. They survive code changes: the kit sets `runOnSave = true`, so the app reloads itself when the assistant saves `app.py`, and the rows stay. They do **not** survive stopping the server (Ctrl+C). Before stopping a server or switching apps, download the JSON export. The export is for the record; no app imports it.

### After the lecture

- **Rotate the OpenRouter key.** It was shared in a chat during preparation.

---

## 3. Launch commands

Run each from its own folder, in the terminal that holds the key. Each app opens in **offline mode**; switch it off in the sidebar for live calls.

```bash
# the app the assistant builds (after Prompt A; Prompt B extends the same running app)
cd lecture-package/live-coding-start && .venv/bin/python -m streamlit run app.py
#   -> http://localhost:8501

# fallback 1: stage-one generator
cd lecture-package/fallback/stage1-generator && ../../live-coding-start/.venv/bin/python -m streamlit run app.py

# fallback 2: full app (generate + detect & compare, recorded run)
cd lecture-package/fallback/full-app && ../../live-coding-start/.venv/bin/python -m streamlit run app.py
```

- **Two apps at once:** add `--server.port 8502` to the second one and open `http://localhost:8502`.
- **Stop an app:** press Ctrl+C in its terminal, after exporting the JSON if you want to keep the rows.
- All apps bind to `localhost` and hide Streamlit's *Deploy* button (`.streamlit/config.toml`).

---

## 4. Minute by minute

| Time | Slide | DO (click / type) | SAY (student-facing) | EXPECT / TRANSITION |
|---|---|---|---|---|
| 00:00–00:45 | p1 Title | – | **"One hour, one experiment. We will generate false health claims on purpose. They stay labelled in this room. Smoking is harmful."** | Online: ask everyone to open the chat; in the room, votes are by show of hands |
| 00:45–01:45 | p2 About your lecturer | – | One sentence on why: **"I build AI applications, so I care about what they get wrong."** | → the plan |
| 01:45–03:00 | p3 Overview | – | Read the five steps; say the exercise rule aloud | → **"Before any theory, a game."** |
| 03:00–04:00 | p4 Round 1, faces | Everyone decides first, then votes at once (online: type, then "3, 2, 1, send") | **"Which face is real? One word: what gave it away?"** Then: **"What accuracy do people reach in controlled studies?"** | Guesses run high. Do not reveal yet |
| 04:00–05:00 | p5 Reveal 1 | – | **"A double failure: we can't tell, and we think we can."** | Exact figures are in the notes (48.2 %, 59.0 %, 7.7 %) |
| 05:00–06:00 | p6 Round 2, Arc de Triomphe | Vote as before | **"What are you looking at: lighting, crowds, snow in Paris?"** | Split room |
| 06:00–06:45 | p7 Reveal 2 | – | **"'It never snows like that in Paris' is reasoning about the world, not the pixels."** | → **"Now try words."** |
| 06:45–07:45 | p8 Round 3, Buffett | Read both quotes aloud, then vote | – | – |
| 07:45–09:00 | p9 Reveal 3 | Score check: **"How many of three did you get?"** | **"Three rounds, three coin flips. So what changed?"** | Usually 1–2 of 3. Provenance is the thought to hold |
| 09:00–10:30 | p10 Next token | Ask one person to complete "The CFO approved the …" | **"A plausibility engine, not a database."** | – |
| 10:30–11:15 | p11 Tokens | – | **"The model never sees letters or words, only these pieces."** | German row: two-thirds more tokens. Do not overclaim beyond the slide |
| 11:15–12:15 | p12 Training vs inference, p13 Size and context | – | **"Nobody trains anything today: each button press is one logged inference call."** | Temperature 0.7 for writing, 0 for checking |
| 12:15–13:00 | p14 Plausibility | – | **"Today we use this property on purpose."** | Mata v. Avianca if there is time |
| 13:00–14:00 | p15 Learning materials | – | The invitation sentence on the slide; two learning paths. **"This hour replaces neither course."** | One minute only |
| 14:00–14:45 | p16 VS Code walkthrough | Switch screen to VS Code. **File → Open Folder… → `live-coding-start`**. Command Palette → **Claude Code: Open in New Tab**. Mode: **Edit automatically** | **"Two different AIs today: the coding assistant writes the app; the models inside the app write and check the passages."** **"The folder holds a tested starter kit; the assistant writes the app on top."** | Students often think one key does everything |
| 14:45–16:00 | p17 Prompt A | Open `prompts/01-build-generator.md`, copy the text block, paste, send. **Note the clock time** | **"This is a specification, not a magic word."** | It reads `CLAUDE.md`, writes `app.py` in one go, runs the smoke test. **Done in about 1 minute** |
| 16:00–18:00 | p18 Agentic coding | Show its report and the smoke-test line (`SMOKE TEST PASSED …`). Then in the key terminal: `.venv/bin/python -m streamlit run app.py` | **"Its report is a claim; the tests and the running app are the evidence."** Ask: **"What would you check first?"** | Answers: does it run? does it show the warning? any unwanted calls? Open the app in the browser now |
| 18:00–20:00 | p19 Architecture | Click through the running app (offline toggle still on): the warning, the sidebar, the disabled live buttons | **"Every paid call is a button; editing a field never calls a model."** | **Not done or not working by ~18:00 → fallback** (section 6) |
| 20:00–23:00 | p20 Eight examples | In the app: offline toggle **off** (key found). **Generate balanced set (2 paid calls)** | Collect the predictions on the slide **before** showing outputs | Both calls ≈11–13 s. Typical predictions: "the big model is more convincing", "it will refuse" |
| 23:00–29:00 | (app; p20 stays up) Read the cards | Read the 8 cards together. There is **no approve/exclude step**: every passage goes to the detectors. Ask the room which ones look fake | **"Does it keep the assigned claim? Invented sources or numbers? Does it leak its label?"** | Hedging ("might"), vague "research suggests", invented ages. A reversed claim is the best moment: celebrate it, and predict what the detectors will say. The "Hints" can be false alarms |
| 29:00–30:30 | p21 Prompt B | Optional insurance: download the JSON export. **Leave the app running.** Paste Prompt B into the same Claude Code conversation. **Note the time** | **"Extend, don't rebuild."** | **Done in about 1 minute.** Keep the browser visible: the app reloads on every save, the new tab appears, the generated rows stay |
| 30:30–33:30 | p22 Fact-check vs authorship | – | **"We give both models the same four WHO sentences. Nobody searches the web."** Ask: **"Is this a fair test? What would make it harder?"** | Answers: unfamiliar claim; no evidence packet; indirect evidence. **Not usable by ~33:00 → fallback** |
| 33:30–35:30 | p23 Blinding | – | **"Why freeze before running? So nobody picks examples after seeing verdicts."** | Mention the prompt-injection test coming later |
| 35:30–37:00 | p24 Scoring | – | Walk one example: **"A true post judged 'contradicted' is a false positive."** **"Always say the denominator."** | Stay in the assistant's app |
| 37:00–40:00 | p25 Hypotheses | Show of hands for H1 and H2. In the **Detect & compare** tab: **Run both detectors (2 paid calls)**. The app blinds, shuffles and freezes all passages first | **"Hypotheses, not promises. We report ties, refusals and errors as they come."** | Both calls ≈11 s |
| 40:00–48:00 | (app) Reading the 2×2 | Read the matrix in the app; the rehearsal matrix is in the appendix (p35–p36) for comparison. Toggle **Reveal intended labels and generators**; read the reasons. Live demo: paste a reversed passage (if there was one), then the injection text from the notes, into **Check a pasted passage** (1 paid call per ticked detector) | Read one cell aloud with its denominator: **"3 of 3, that is three items, not a percentage."** | In rehearsal, both pastes came back "contradicted" from both detectors |
| 48:00–55:00 | (discussion) Explanations and limits | Let the room argue | **"Did the detector assess the evidence, recognise a familiar claim, or respond to writing style?"** | Good answers: "8 items can't tell", "try an unfamiliar claim", "remove the evidence" |
| 55:00–59:00 | p26 Takeaways + exit | Read the three lines. Collect three one-sentence exit predictions. Questions | **"Never ship unverified output."** Callback to provenance. Optional: **"Both builds took about a minute each, because the risky parts were tested code."** | 59:00: click **Resources and contact** (skips the appendix) |
| 59:00–60:00 | p47 Resources and contact | Leave it on screen | Both repositories and the e-mail are clickable | End |

The builds now finish early, which frees about 4 minutes around p18–p19 and 2–3 minutes around p21–p22. Spend them on reading the cards (23:00–29:00) or on the pasted-passage demo. Don't move later slides earlier.

---

## 5. The two live builds, with real rehearsal timings

**How they were measured (18 Oct 2026).**
- Real Claude Code CLI 2.1.302 in headless mode (`claude -p`), model Opus 5.5.
- Each run used a fresh copy of the kit with the `.venv`. Prompt A ran first, then Prompt B in the same conversation (`--resume`).
- Times are wall-clock, including CLI start-up and the assistant's own smoke-test run.
- No API key was present, and no paid OpenRouter call was made.
- The smoke-test command was passed as an allowed tool, which mirrors a trusted folder.
- Not measured: the VS Code extension itself, and your reading time. Hence the dress rehearsal in §2.

| Setup | Prompt A | Prompt B |
|---|---|---|
| **Before:** empty folder, 62/71-line prompts (fresh agents, earlier rehearsal) | 379 s (~6.3 min) | 999–1061 s (~17 min) |
| **Now:** starter kit, final prompts, default settings (3 runs) | **46, 54, 61 s** | **50, 55, 66 s** |
| Now, near-final kit: effort high / medium / low / fast mode + medium (1 run each) | 48 / 46 / 35 / 51 s | 60 / 39 / 50 / 47 s |

All 7 runs passed the smoke test, both by the assistant's own report and when re-run independently, with no permission denials in the final 3. A browser check in Chrome confirmed that the app reloads itself 0.3 s after `app.py` is saved and keeps its 8 reviewed rows (validation report §4).

**Plan accordingly**

1. **Prompt A at ~14:45.** Expect the report within about a minute, while you are still on p17–p18.
2. **Start it** in your key terminal (`.venv/bin/python -m streamlit run app.py`) and open the browser.
   - **Not usable by ~18:00:** start `fallback/stage1-generator` (or `fallback/full-app`) and let the assistant finish in the background.
3. **Prompt B at ~29:30**, in the same Claude Code conversation, with the app still running. When the report arrives, the new tab is already in the browser.
   - **Not usable by ~33:00:** start `fallback/full-app` (second port or after Ctrl+C), then regenerate (2 calls, ≈12 s) or load the recorded run. The fallback app still has the older review step.

**Same app every time.** `CLAUDE.md` describes both approved apps section by section with exact labels: `reference-apps/app_after_prompt_a.py` and `app_after_prompt_b.py`. `smoke_test.py` fails if a required button is missing.
- In the final 3 replays of the simplified version (A then B), Prompt A took 33–39 s and Prompt B 60–66 s.
- Both results had exactly the reference structure: the same sidebar, tabs, sections, buttons, labels and order.
- If a live build ever looks different or breaks, run `tools/use-reference-app.sh a` (after Prompt A) or `b` (after Prompt B). It keeps the live build as `app.py.live-build.bak` and installs the reference app; the running app reloads and keeps its rows.

**No review step (simplified on 18 Oct 2026).** Generated passages go straight to the detectors: *Run both detectors* calls `lab.freeze_all`, which takes every row, fixes a shuffled order and blind IDs, and only then calls the models. The blinding is unchanged. The detector buttons need only live mode and at least one generated row; if something is missing, the tab says so in a yellow box. The trade-off: a passage where a model argued the opposite of its assignment keeps its *intended* label, so it counts against the detector. Point this out when it happens.

**If the assistant's app shows a traceback** after Prompt B, say: **"Its report was a claim."** Then type one line into Claude Code: *"The app shows this error: <first line>. Fix app.py and rerun the smoke test."* Expect about 30 s. If that fails too, use the fallback.

---

## 6. Fallback decision table

| Situation | What you see | What to do | What to say |
|---|---|---|---|
| Assistant asks for permission | A prompt for a command | Answer **Yes** once; afterwards check that the folder is trusted and the mode is *Edit automatically* | "It asks before it runs anything I did not allow." |
| Assistant slow or stuck | No report by ~18:00 (A) or ~33:00 (B) | Start the matching fallback; let the assistant continue | "In rehearsal this took about a minute. Today it didn't, so we continue with the tested version." |
| Assistant's app fails to start or shows errors | Traceback in terminal/browser | One fix request (section 5), then the fallback. Do not debug by hand | "Its report was a claim; here is why we review." |
| **401** | "Invalid or disabled API key (HTTP 401)." | Check the key terminal (`echo ${#OPENROUTER_API_KEY}`) or `.env`, off-screen | Read the message aloud: errors are reported, not hidden |
| **402** | "Insufficient credits on the OpenRouter account or key (HTTP 402)." | Recorded run in `fallback/full-app` | Same |
| **403** | "Request blocked (HTTP 403): key budget, permission, moderation or guardrail." | Recorded run | Same |
| **429** | "Rate limited (HTTP 429). Wait, then use the explicit retry button." | Wait ~10 s, then **one** explicit retry: the single-detector retry button, or regenerate. The other model's results are kept. Routing is `mistral/eu` from `models.json` | "One retry, by hand, logged." |
| **5xx / provider** or **timeout** | "Model provider error or no provider available…", or "Stopped waiting after 60 s (total deadline)." | One explicit retry, as for 429 | – |
| Still failing after one retry | – | `fallback/full-app` → sidebar → **Load recorded rehearsal run (real outputs, no network)** | **"This is recorded from the rehearsal on 18 October, not measured now."** |
| Model declines or writes the opposite claim | Generation failure listed, or reversed text on a card | Say it aloud before running the detectors. A declined slot is simply missing (the matrix shows the smaller denominator). A reversed passage keeps its intended label, so a correct detector looks wrong on it. Optionally regenerate the **whole batch before running the detectors**, never after verdicts | "The label is what we asked for, not what it wrote. We report this; we do not pick examples after seeing results." |
| No network at all | – | Offline toggle on. **Load the 8 offline fixtures (hand-authored)** → *Detect & compare* → **Show illustrative verdicts (hand-authored, NOT measured)**, or the recorded run in `fallback/full-app` | **"No live comparison has been measured today. These verdicts are hand-written illustrations."** |
| No network, and no coding assistant either | Claude Code cannot reach its service | Run `fallback/full-app` offline | "The coding assistant is a cloud service too." |
| Projector hard to read | – | Browser and VS Code zoom (⌘+); the full prompt texts are on p28–p31, the kit on p32 | – |
| Running late | – | Shorten p20 predictions and the paste demo; keep p24 (scoring), the matrix discussion and p26 | – |

---

## 7. Costs, timings and routing seen in rehearsal (18 Oct 2026)

**Coding assistant:** each headless build cost about US$0.22–0.40 (Prompt A) and US$0.45–0.69 (Prompt B) in Claude usage over 11 runs, as estimated by Claude Code (`total_cost_usd`). On a subscription this counts against the plan's usage.

**Generation:** a balanced set (2 calls) took ≈11–13 s in the browser and cost about US$0.0009. Per call:

| Model | Time | Cost |
|---|---|---|
| economy (`mistralai/ministral-8b-2512`) | ≈3–5 s | ≈US$0.00016 |
| advanced (`mistralai/mistral-large-2512`) | ≈6 s | ≈US$0.0007–0.001 |

**Detection:** both detectors on 7 passages took ≈11 s and cost about US$0.0014 (economy US$0.00023, advanced US$0.0012).

**Pasted passage:** 2 calls cost about US$0.0005 or less.

**Routing:**
- Every request sends `provider: {"order": ["mistral/eu"], "allow_fallbacks": false}` (from `models.json`, applied by the kit). This selects the EU endpoint of the **same** model: exactly one endpoint attempt, no other model, no hidden retry.
- Reason: in rehearsal, OpenRouter's default endpoint for `mistral-large-2512` returned HTTP 429 ("temporarily rate-limited upstream"), while the EU endpoint answered.
- The app records the cost OpenRouter returns, or "unavailable".

---

## 8. What to say about the results

- **Hypotheses, not promises.** A larger model is not guaranteed to write harder-to-detect misinformation or to give better verdicts. Report ties, refusals, errors, abstentions and results against expectation as they are.
- **The rehearsal result was a tie.**
  - 7 eligible rows: one excluded at review, because the economy model was asked for the true claim and argued the false one. So the design was **incomplete**.
  - Every cell scored every item correctly: economy-generator cells 3/3, advanced-generator cells 4/4, no abstentions, no failures.
  - **"A tie at 100 % does not show that model size doesn't matter. It shows this test is too easy to tell them apart."**
- **Always give denominators.** "3/3" is three items.
  - With 4 items per cell, one answer moves accuracy by **25 percentage points**.
  - With 2 items per label, one answer moves recall or the false-positive rate by **50 points**.
- **`insufficient_evidence` is an abstention**, never a correct negative. Failures are not predictions.
- **What it cannot show:**
  - one familiar claim, with the evidence handed over
  - both models from one vendor
  - intended labels, not checked by a reviewer (no review step in the simplified app)
  - not a validated classifier, not an AI-authorship detector, not independent medical verification

  Ask: **"Did the detector assess the evidence, recognise a familiar claim, or respond to writing style?"**
- **About the build:** the assistant was fast because the parts where a bug would quietly corrupt the result (blinding, scoring, error handling) were tested code it did not write. **"Speed came from preparation, not from trusting the assistant more."**
- **Closing line:** convincing wording is not evidence; a model verdict is not independent verification; human and source review remain necessary.
