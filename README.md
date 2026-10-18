# AI or Reality? Can We Tell the Difference?

A 60-minute lecture by Prof. Dr. Christoph Weisser (Hochschule Bielefeld, HSBI).
- **First half:** students try to tell real images and quotes from AI-generated ones. They then learn how large language models write: next-token prediction, tokens, training versus inference, and why fluent text can still be false.
- **Second half:** a Streamlit app is built live with Claude Code. It generates labelled health misinformation, and a small and a large model check each claim against WHO evidence.

> **Classroom exercise material.** The app writes deliberately false health claims for teaching. They are not health advice. **Smoking is harmful** ([WHO](https://www.who.int/news-room/fact-sheets/detail/tobacco)).

## The live build: about a minute per prompt

Claude Code does not start from an empty folder. `live-coding-start/` holds a tested **starter kit** (see [`starter-kit/README.md`](starter-kit/README.md)):
- the OpenRouter client, the claims and the balanced design;
- blinding and scoring;
- offline fixtures;
- a smoke test;
- a `CLAUDE.md` with the rules and the API.

The assistant writes one file, `app.py`, on top of it:

| Prompt | What it builds | Measured (headless Claude Code 2.1.302, Opus 5.5, 18 Oct 2026) |
|---|---|---|
| [A](prompts/01-build-generator.md), 24 lines | the generator: one example, a balanced set, offline fixtures, review cards, export | 35–61 s in 7 runs |
| [B](prompts/02-add-detection.md), 21 lines | the *Detect & compare* tab: freeze, both detectors, the 2 × 2 matrix, a pasted-passage check | 39–66 s in 7 runs |

Both times include the assistant running the smoke test. From an empty folder with the earlier long prompts, the same builds took about 6 and 17 minutes.

The running app reloads itself when `app.py` changes, and the reviewed rows survive. So Prompt B extends the app in front of the class, without a restart.

## What's here

- `lecture-slides.pdf`: the slides (47 pages). `lecture-slides-with-notes.pdf` adds the presenter notes, and `slides-latex/` holds the LaTeX source.
- `live-coding-start/`: the teaching folder that you open in VS Code (the starter kit, no `app.py`).
- `starter-kit/`: the pristine kit. `tools/reset-live-coding-start.sh` restores the teaching folder from it before class.
- `prompts/`: the two prompts pasted into Claude Code during the live build.
- `fallback/`: tested versions of the app, with setup steps in each folder's README. With the kit you should not need them, but they stay ready.
- `docs/`:
  - the runbook (preflight, minute-by-minute plan, fallbacks);
  - the validation notes, including the timing replays;
  - the source/reuse map;
  - the earlier empty-folder prompts.

## Quick start (preparation)

```bash
cd lecture-package/live-coding-start
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -q tests         # 87 passed
```

Then open the folder once in VS Code with Claude Code and accept the trust dialog. Set the permission mode to **Edit automatically**. Without trust, the allowed smoke-test command asks for permission. The full checklist is in [`docs/runbook.md`](docs/runbook.md).

## License

MIT (see [LICENSE](LICENSE)), except the third-party quiz images, which keep their own licences, and the presenter photograph, which is not licensed for reuse.
