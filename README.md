# Lecture package: *AI or Reality? Can We Tell the Difference?*

> **Classroom exercise material.** The app generates deliberately false health claims (for example, "cigarettes are healthy") for teaching. They are not health advice. **Smoking is harmful** ([WHO](https://www.who.int/news-room/fact-sheets/detail/tobacco)).

This package is a 60-minute lecture by Prof. Dr. Christoph Weisser (HSBI). It runs from an image challenge, through how LLMs write, to a live build of a Streamlit app with Claude Code in VS Code. The app first generates labelled misinformation, then checks claims with two OpenRouter models (economy `mistralai/ministral-8b-2512`, advanced `mistralai/mistral-large-2512`).

| Path | What it is |
|---|---|
| `lecture-slides.pdf` | Audience deck, 50 pages. Main flow p1–p26, appendix p27–p49, final page p50 "Resources and contact" |
| `lecture-slides-with-notes.pdf` | Same deck with presenter notes (timings, clicks, likely answers, fallbacks) |
| `slides-latex/` + `slides-latex.zip` | Editable LaTeX project (template `chapter_00` preamble unchanged, `main.tex`, notes, bibliography, images, build instructions) |
| `prompts/01-build-generator.md` | **Prompt A**, the exact text to paste (one sentence about provider routing was added after rehearsal) |
| `prompts/02-add-detection.md` | **Prompt B**, the exact text to paste |
| `live-coding-start/` | The **empty teaching folder** to open in VS Code during class. It holds only `models.json` |
| `fallback/stage1-generator/` + `.zip` | Tested stage-one snapshot (generator only); 55 offline tests |
| `fallback/full-app/` + `.zip` | Tested complete fallback app (generate + detect & compare, offline mode, recorded rehearsal run); 93 offline tests |
| `docs/runbook.md` | Preflight, launch commands, minute-by-minute plan, fallbacks |
| `docs/source-reuse-map.md` | What came from which source slide, the cutoff (p1–p18), images, quiz answers, the tokenisation deletion |
| `docs/validation-report.md` | What was tested and how (offline, mocked, live calls, agent replays, browser, LaTeX), plus open limits |
| `docs/screenshots/` | Screenshots from the actual app runs (no keys visible) |

Quick start (fallback app, offline, no key needed):

```bash
cd fallback/full-app
python -m pip install -r requirements.txt
python -m streamlit run app.py          # http://localhost:8501
```

For live mode, copy `.env.example` to `.env` in the app folder and replace the placeholder with your key (Git ignores `.env`), or export `OPENROUTER_API_KEY` in that terminal before starting. Then switch off "Offline demonstration mode" in the sidebar. Never type the key on screen, and never paste it into the coding assistant.

## License

Code, slides and texts are released under the [MIT License](LICENSE), with two exceptions:

- The third-party quiz images in `slides-latex/images/` (`face_fake_a.jpg`, `face_real_b.jpg`, `arc_real.jpg`, `arc_ai.png`) keep their own licences: public domain, CC BY-SA 4.0, CC0 and CC BY 3.0. See the image credits in the deck and section 5 of `docs/source-reuse-map.md`.
- The presenter photograph `slides-latex/images/ch00_profile.jpg` is not licensed for reuse.
