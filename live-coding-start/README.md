# Starter kit for the live build

This folder is what `live-coding-start/` contains before class. During the lecture, Claude Code
writes **one file, `app.py`**, on top of it: Prompt A builds the generator, Prompt B adds the
*Detect & compare* tab.

> **Classroom exercise material.** The app writes deliberately false health claims for teaching.
> They are not health advice. **Smoking is harmful** ([WHO](https://www.who.int/news-room/fact-sheets/detail/tobacco)).

## Why a kit

In rehearsal, an empty folder took about 6 minutes for Prompt A and 17 minutes for Prompt B. Most of
that time went into an HTTP client, parsers, scoring code and the test suites for them. The kit
holds those parts, already tested. The assistant writes the app around them: about 250–360 lines
of Streamlit UI, session state and buttons, checked by one offline smoke test.

The parts where a bug would quietly corrupt the result are tested code, not live code:
- error handling and the single-request rule
- blinding: what a detector may see
- scoring: abstentions, failures and denominators

| File | What it does |
|---|---|
| `CLAUDE.md` | Instructions Claude Code loads automatically: work fast, write only `app.py`, the API of `lab.py`, the rules the app must keep |
| `.claude/settings.json` | Permission mode *accept edits*, allows exactly the smoke-test command, denies reading `.env` and secrets |
| `lab.py` | The one module the app imports: models and key, `generate`, fixtures, review, `freeze`, `detect`, `matrix`, `assess_pasted`, export |
| `openrouter_client.py` | One HTTP request per call, finite timeouts, no retries, no model fallback, sanitized errors |
| `generation.py` | Fixed claims, formats and the balanced 2 × 2 × 2 design, strict parsing, review flags, export |
| `detection.py` | WHO evidence packet, freezing and blind IDs, verdict parsing, metrics with denominators |
| `fixtures.json` | 8 hand-authored offline examples and illustrative (not measured) verdicts |
| `models.json` | Verified model IDs, sizes and provider routing (non-secret preflight result) |
| `smoke_test.py` | Starts `app.py` with Streamlit AppTest and clicks every button once: offline, no key, network blocked |
| `tests/` | 87 offline tests for the kit (`.venv/bin/python -m pytest -q tests`) |

The kit modules are the same code as `fallback/full-app/` (`openrouter_client.py`, `generation.py`,
`detection.py` and `fixtures.json` are identical copies). `lab.py` is a thin facade over them.

## Setup (once, before class)

```bash
cd lecture-package/live-coding-start
uv venv --python 3.12 .venv            # or: python3.12 -m venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -q tests    # expect: 87 passed
```

The API key: export `OPENROUTER_API_KEY` in the terminal that runs Streamlit, or put it in `.env`
(Git-ignored, never read by the assistant). Start the app with:

```bash
.venv/bin/python -m streamlit run app.py
```

## The approved app

`CLAUDE.md` pins the layout of both approved apps, `../reference-apps/app_after_prompt_a.py` and `app_after_prompt_b.py`, with exact labels. `smoke_test.py` checks that the required buttons exist. `../tools/use-reference-app.sh a|b` installs a reference app directly if a live build ever differs.

## Reset before class

```bash
lecture-package/tools/reset-live-coding-start.sh
```

This restores `live-coding-start/` from this folder and deletes the assistant's `app.py`. It keeps
`.venv/` and `.env`.
