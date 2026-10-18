# Lecture runbook: *AI or Reality? Can We Tell the Difference?* (60 min)

This is the instructor's guide for one live lecture: the image challenge, a short LLM introduction, a live build of a Streamlit app with an AI coding assistant, then a generator × detector comparison.

- Student-facing wording appears in **"quotes"** in the SAY column.
- Everything else is for the instructor only.
- Slide numbers (p…) refer to `lecture-slides.pdf` (53 pages).
- The presenter notes are in `lecture-slides-with-notes.pdf`.

---

## 1. What is in the package, and when to open what

| Path | What it is | When |
|---|---|---|
| `lecture-slides.pdf` | Audience deck (notes hidden). The main flow is p1–p29, the appendix p30–p52, and the final page p53 "Resources and contact". | Projected all lecture |
| `lecture-slides-with-notes.pdf` | Slide left, notes right (timings, what to click, fallbacks). | On your second screen |
| `live-coding-start/` | **Empty teaching folder**: only `models.json` (verified model IDs, sizes and routing). | Open in VS Code at 14:00 for Prompt A, keep it for Prompt B |
| `prompts/01-build-generator.md` | Prompt A, exact text (paste the text block only). | 14:45 |
| `prompts/02-add-detection.md` | Prompt B, exact text. | ~29:30 |
| `fallback/stage1-generator/` | Tested stage-one snapshot: the generator only. | If the live build is not usable at ~19:30 |
| `fallback/full-app/` | Tested complete app: Generate + Detect & compare, offline mode, recorded rehearsal run. | At 37:00 at the latest, and whenever the API fails |
| `docs/` | This runbook, the source/reuse map and the validation report. | Preparation |

Keep `fallback/` out of the VS Code workspace during class. The assistant should only ever see `live-coding-start/`.

---

## 2. Preflight

### The day before

1. **Python environment.** Tested with Python 3.12.13, streamlit 1.66.0 and requests 2.34.2. In a fresh virtual environment:
   ```bash
   cd lecture-package
   python -m pip install -r fallback/full-app/requirements.txt
   ```
   The same requirements cover `stage1-generator` and the app the assistant will build.
2. **Run the tests** (no network, no cost):
   ```bash
   (cd fallback/stage1-generator && python -m pytest -q tests)   # expect: 55 passed
   (cd fallback/full-app && python -m pytest -q tests)           # expect: 93 passed
   ```
3. **Coding assistant.** Install and log in to *Claude Code for VS Code* (version 2.1.301 at preparation).
   - It needs its **own Claude account** (subscription or pay-as-you-go). The OpenRouter key does not give you a coding assistant.
   - Check that the Command Palette shows **Claude Code: Open in New Tab** (shortcut ⌘⇧Esc).
4. **Choose the permission mode** from the mode menu under the Claude Code prompt box:
   - **Manual**: you approve each edit (slower, shows the review step).
   - **Edit automatically**: faster.
   - Do not use *Bypass permissions*.
   - Command prompts offer **Yes** / **Yes, and don't ask again**; proposed diffs offer **Accept** / **Reject**.
5. **Rehearse the offline path once.** Start `fallback/full-app` (see section 3) with the offline toggle on:
   1. Press **Load recorded rehearsal run (real outputs, no network)** in the sidebar and check that the matrix appears under *Detect & compare*.
   2. Restart, then try **Load the 8 offline fixtures (hand-authored)** → **Freeze the 8 approved row(s) (no network)** → **Show illustrative verdicts (hand-authored, NOT measured)**.

### 30 minutes before

1. **Reset the teaching folder** so it contains only `models.json`. Look first, then delete:
   ```bash
   cd lecture-package/live-coding-start
   pwd                                    # must end in /live-coding-start
   find . -mindepth 1 -maxdepth 1 ! -name models.json -print            # dry run: what would go
   find . -mindepth 1 -maxdepth 1 ! -name models.json -exec rm -rf {} + # then delete
   ls -la                                 # only models.json (plus . and ..)
   ```
   If `models.json` is missing or changed, copy it back from `fallback/full-app/models.json`; all three copies were identical at preparation.
2. **API key, off-screen, before you project.**
   - Open the VS Code integrated terminal you will use to start Streamlit and type:
     ```bash
     read -rs OPENROUTER_API_KEY; export OPENROUTER_API_KEY   # nothing is echoed or stored in history
     echo ${#OPENROUTER_API_KEY}                               # prints only the length
     ```
   - Export it only in that terminal, not in your shell profile.
   - Never type it on screen, and never paste it into the coding-assistant chat.
   - Alternative for the fallback apps: copy `.env.example` to `.env` in the app folder you will run (Git-ignored), off-screen. `.streamlit/secrets.toml` works too. The environment variable takes precedence. The app built live from Prompt A reads only the environment and Streamlit secrets.
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
5. **Session state is lost on restart.** The app's data lives in the browser session. Before stopping a server or switching apps, press **Download JSON export (with exercise warning, no secrets)**. The full app cannot import another app's export; the export is for the record.

### After the lecture

- **Rotate the OpenRouter key.** It was shared in a chat during preparation.

---

## 3. Launch commands

Run each from its own folder, in the terminal that holds the key. Each app opens in **offline mode**; switch it off in the sidebar for live calls.

```bash
# the app the assistant builds (after Prompt A)
cd lecture-package/live-coding-start && python -m streamlit run app.py
#   -> http://localhost:8501   (the assistant's report gives the exact command it tested)

# fallback 1: stage-one generator
cd lecture-package/fallback/stage1-generator && python -m streamlit run app.py
#   -> http://localhost:8501

# fallback 2: full app (generate + detect & compare)
cd lecture-package/fallback/full-app && python -m streamlit run app.py
#   -> http://localhost:8501
```

- **Two apps at once:** add `--server.port 8502` to the second one and open `http://localhost:8502`.
- **Stop an app:** press Ctrl+C in its terminal, after exporting the JSON if you want to keep the rows.
- The fallback apps bind to `localhost` and hide Streamlit's *Deploy* button (`.streamlit/config.toml`).

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
| 09:00–09:30 | p10 Thesis | – | **"Forgery used to be slow, skilled, expensive craft. That constraint just disappeared."** | → how the text machine works |
| 09:30–10:30 | p11 Next token | Ask one person to complete "The CFO approved the …" | **"A plausibility engine, not a database."** | – |
| 10:30–11:15 | p12 Tokens | – | **"The model never sees letters or words, only these pieces."** | German row: two-thirds more tokens. Do not overclaim beyond the slide |
| 11:15–12:15 | p13 Training vs inference | – | **"Nobody trains anything today: each button press is one logged inference call."** | Temperature 0.7 for writing, 0 for checking |
| 12:15–13:00 | p14 Plausibility | – | **"Today we use this property on purpose."** | Mata v. Avianca if there is time |
| 13:00–14:00 | p15 Learning materials | – | The invitation sentence on the slide; two learning paths. **"This hour replaces neither course."** | One minute only |
| 14:00–14:45 | p16 VS Code walkthrough | Switch screen to VS Code. **File → Open Folder… → `live-coding-start`**. Command Palette → **Claude Code: Open in New Tab**. Pick **Manual** or **Edit automatically** | **"Two different AIs today: the coding assistant writes the app; the models inside the app write and check the passages."** | Students often think one key does everything |
| 14:45–16:00 | p17 Prompt A | Open `prompts/01-build-generator.md`, copy the text block, paste, send. **Note the clock time** | **"This is a specification, not a magic word."** | A plan within seconds, then file writes and tests |
| 16:00–18:00 | p18 Agentic coding | Glance at VS Code; narrate ("it is writing fixtures", "it is running pytest") | **"Its report is a claim; the tests and the running app are the evidence."** Ask: **"What would you check first?"** | Answers: does it run? does it show the warning? any unwanted calls? |
| 18:00–20:00 | p19 Architecture | **~19:30: check the build** (section 5) | **"Every paid call is a button; editing a field never calls a model."** | Done → start it. Not done → fallback |
| 20:00–23:00 | p20 Eight examples | In the app: offline toggle **off** (key found). **Generate one example (1 paid call)** with a student's choice, then **Generate balanced set (2 paid calls)** | Collect the predictions on the slide **before** showing outputs | Both calls ≈11–13 s. Typical predictions: "the big model is more convincing", "it will refuse" |
| 23:00–29:00 | p21 Review | Go through the 8 cards. For each, ask the room: approve or exclude? Set the review radio and type the note for exclusions. Optional: **I have read them: approve the N waiting row(s) without flags** | **"Does it keep the assigned claim? Invented sources or numbers? Does it leak its label?"** | Hedging ("might"), vague "research suggests", invented ages. A reversed claim is the best moment: celebrate it. Flags can be false alarms |
| 29:00–32:00 | p22 Prompt B | **Download JSON export** first. Paste Prompt B into the same Claude Code conversation. **Note the time** | **"Extend, don't rebuild."** | It will run long (section 5) |
| 32:00–33:30 | p23 Fact-check vs authorship | – | **"We give both models the same four WHO sentences. Nobody searches the web."** Ask: **"Is this a fair test? What would make it harder?"** | Answers: unfamiliar claim; no evidence packet; indirect evidence |
| 33:30–35:30 | p24 Blinding | – | **"Why freeze before running? So nobody picks examples after seeing verdicts."** | Mention the prompt-injection test coming later |
| 35:30–37:00 | p25 Scoring | – | Walk one example: **"A true post judged 'contradicted' is a false positive."** **"Always say the denominator."** | **37:00: switch to `fallback/full-app`** |
| 37:00–40:00 | p26 Hypotheses | Show of hands for H1 and H2. In the full app's **Detect & compare** tab: check the counts table → **Freeze the N approved row(s) (no network)** → **Run both detectors (2 paid calls, N passages each)** | **"Hypotheses, not promises. We report ties, refusals and errors as they come."** | Both calls ≈11 s |
| 40:00–48:00 | p27 Reading the 2×2 | Live matrix first, then this slide (rehearsal) for comparison. Toggle **Reveal intended labels and generators**; read the reasons. Live demo (4 calls): paste the excluded reversed passage, then the injection text from the notes, into **Assess a pasted passage** → **Assess pasted passage (1 paid call per ticked detector)** | Read one cell aloud with its denominator: **"3 of 3, that is three items, not a percentage."** | In rehearsal, both pastes came back "contradicted" from both detectors |
| 48:00–55:00 | p28 Explanations and limits | Let the room argue | **"Did the detector assess the evidence, recognise a familiar claim, or respond to writing style?"** | Good answers: "8 items can't tell", "try an unfamiliar claim", "remove the evidence" |
| 55:00–59:00 | p29 Takeaways + exit | Read the three lines. Collect three one-sentence exit predictions. Questions | **"Never ship unverified output."** Callback to provenance | 59:00: click **Resources and contact** (skips the appendix) |
| 59:00–60:00 | p53 Resources and contact | Leave it on screen | Both repositories and the e-mail are clickable | End |

---

## 5. The two live builds, with real rehearsal timings

In rehearsal, fresh agents ran each prompt in an empty copy of the project. The ~2-minute target was **not** met:

| Build | Rehearsal result | Elapsed |
|---|---|---|
| Prompt A | working generator, offline tests passing | 379 s each in two replays (~6.3 min) |
| Prompt B | working Detect & compare tab, offline tests passing | 1061 s and 999 s (~17 min) |

**Plan accordingly**

1. **Prompt A at ~14:45.** Talk through p18–p19 while it works.
2. **Check at ~19:30.**
   - **Usable** (it reports passing checks and gives a start command): start it in your key terminal and carry on at 20:00.
   - **Not usable yet:** keep teaching and start the stage-one snapshot instead:
     ```bash
     cd lecture-package/fallback/stage1-generator && python -m streamlit run app.py
     ```
     Let the assistant finish in the background.
   - Rows do not move between apps. If you generate in `stage1-generator` or in the assistant's app, then at 37:00 in `fallback/full-app` you either regenerate the balanced set (2 calls, ≈12 s, plus a quick re-review) or load the recorded run. To avoid that, you may run `fallback/full-app` from 19:30 instead: its *Generate* tab is the stage-one generator, and the reviewed rows carry straight into *Detect & compare*.
3. **Prompt B at ~29:30**, in the same Claude Code conversation in `live-coding-start/`.
4. **At 37:00, switch to `fallback/full-app` regardless.**
   1. Export the JSON from the running app.
   2. Stop the app with Ctrl+C, or start the full app with `--server.port 8502`.
   3. Open the matching URL.
5. **At the end** (55–59), show the assistant's own extended app **only if it has finished**, and say how long it took.

**Switching apps cleanly:** press Download JSON export, then Ctrl+C in the app's terminal (or use a second port), start the other app and switch the offline toggle off again. Never close the key terminal.

---

## 6. Fallback decision table

| Situation | What you see | What to do | What to say |
|---|---|---|---|
| Assistant slow, stuck, or asking many permission questions | No start command by ~19:30 | Answer prompts briefly. At 19:30 start `fallback/stage1-generator` (or `fallback/full-app`); let the assistant continue | "The 2-minute target is a target. In rehearsal it took about 6 minutes." |
| Assistant's app fails to start or shows errors | Traceback in terminal/browser | Do not debug live. Switch to the fallback | "Its report was a claim; here is why we review." |
| Prompt B slow | Still working at 37:00 | Switch to `fallback/full-app` (planned anyway) | "In rehearsal this took 17 minutes; we continue with the tested version." |
| **401** | "Invalid or disabled API key (HTTP 401)." | Check the key terminal (`echo ${#OPENROUTER_API_KEY}`), off-screen | Read the message aloud: errors are reported, not hidden |
| **402** | "Insufficient credits on the OpenRouter account or key (HTTP 402)." | Recorded run (below) | Same |
| **403** | "Request blocked (HTTP 403): key budget, permission, moderation or guardrail." | Recorded run | Same |
| **429** | "Rate limited (HTTP 429). Wait, then use the explicit retry button." | Wait ~10 s, then **one** explicit retry: *Regenerate economy/advanced only (1 call)* or *Run economy/advanced detector only (1 call)*. The other model's results are kept. Check the sidebar endpoint order is `mistral/eu`; change routing only before the first call and for both roles | "One retry, by hand, logged." |
| **5xx / provider** or **timeout** | "Model provider error or no provider available…", or "Stopped waiting after 60 s (total deadline)." | One explicit retry, as for 429 | – |
| Still failing after one retry | – | Sidebar → **Load recorded rehearsal run (real outputs, no network)** | **"This is recorded from the rehearsal on 18 October, not measured now."** |
| Model declines or writes the opposite claim | Generation failure listed, or a review flag / reversed text | **Exclude with a note.** An incomplete design is a legitimate result; the app labels it "Incomplete or imbalanced". Optionally regenerate the **whole batch of one generator, before freezing**, never after verdicts | "We report this; we do not pick examples after seeing results." |
| No network at all | – | Offline toggle on. **Load the 8 offline fixtures (hand-authored)** → **Freeze…** → **Show illustrative verdicts (hand-authored, NOT measured)**, or the recorded run | **"No live comparison has been measured today. These verdicts are hand-written illustrations."** |
| Projector hard to read | – | Browser and VS Code zoom (⌘+); the full prompt texts are on p31–p38; the app uses a wide layout | – |
| Running late | – | Shorten p20 predictions and the p27 paste demo; keep p25 (scoring), p28 and p29 | – |

---

## 7. Costs, timings and routing seen in rehearsal (18 Oct 2026)

**Generation:** a balanced set (2 calls) took ≈11–13 s in the browser and cost about US$0.0009. Per call:

| Model | Time | Cost |
|---|---|---|
| economy (`mistralai/ministral-8b-2512`) | ≈3–5 s | ≈US$0.00016 |
| advanced (`mistralai/mistral-large-2512`) | ≈6 s | ≈US$0.0007–0.001 |

**Detection:** both detectors on 7 passages took ≈11 s and cost about US$0.0014 (economy US$0.00023, advanced US$0.0012).

**Pasted passage:** 2 calls cost about US$0.0005 or less.

**Routing:**
- Every request sends `provider: {"order": ["mistral/eu"], "allow_fallbacks": false}` (from `models.json`, editable in the sidebar). This selects the EU endpoint of the **same** model: exactly one endpoint attempt, no other model, no hidden retry.
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
  - labels reviewed by one person
  - not a validated classifier, not an AI-authorship detector, not independent medical verification

  Ask: **"Did the detector assess the evidence, recognise a familiar claim, or respond to writing style?"**
- **Closing line:** convincing wording is not evidence; a model verdict is not independent verification; human and source review remain necessary.
