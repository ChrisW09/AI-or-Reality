# Slides: *AI or Reality? Can We Tell the Difference?* (60-minute lecture with a live build)

This is the LaTeX source of `../lecture-slides.pdf` (audience edition) and `../lecture-slides-with-notes.pdf` (slide left, presenter notes right).

## Build

```bash
latexmk -pdf main.tex          # audience edition  -> main.pdf
latexmk -pdf main-notes.tex    # presenter notes   -> main-notes.pdf
latexmk -c                     # remove auxiliary files
```

- **Engine:** pdfLaTeX, the same as the template `chapter_00.tex`.
- **Bibliography:** biblatex with the **bibtex backend**, so no biber is needed.
  - The source deck used biber, but on the preparation machine biber fails to start ("extracting arm64 binary with lipo failed").
  - If biber works on your machine, you can switch `backend=bibtex` to `backend=biber` in `lecture-setup.tex`.
- **Packages:** TeX Live 2023 or later with `beamer`, `tikz`, `tcolorbox`, `listings`, `fontawesome5`, `booktabs`, `colortbl`, `biblatex` and `csquotes`.
- **No shell escape**, and no syntax highlighting that would need one: the prompts are typeset with `listings`.

## Files

| File | Role |
|---|---|
| `template-preamble.tex` | `chapter_00.tex` lines 1–87, **unchanged** (Madrid theme, 16:9, colours, boxes, headline, footer) |
| `lecture-setup.tex` | additions only: notes switch, bibliography, title-slide fields, small helpers, prompt listing style; the template's per-section outline frames are switched off |
| `main.tex` | all frames and presenter notes (`\note{...}`) |
| `main-notes.tex` | defines `\shownotes` and inputs `main.tex` |
| `references.bib` | entries reused from the source deck plus the new ones (WHO, model cards, OpenRouter, Streamlit) |
| `images/` | presenter photo (from chapter 00), quiz images (from the source deck), app screenshots (from the rehearsal run) |
| `prompts/*.txt` | exact prompt text, extracted from `../prompts/*.md` |
| `data/*.tex` | rehearsal tables generated from `../fallback/full-app/recorded_run.json` |
| `tools/` | the two generators below |

## Keep slides, prompts and app consistent

```bash
python tools/extract_prompts.py                                           # after editing ../prompts/*.md
python tools/make_rehearsal_table.py ../fallback/full-app/recorded_run.json   # after a new recorded run
```

The prompt Markdown files are the single source of truth. The slides input the extracted text by line range: the excerpt frames use lines 1–7 (Prompt A) and 1–4 (Prompt B), and the appendix frames show every line. If a prompt changes length, check the `firstline`/`lastline` values in `main.tex`.

## Template quirk

The template's box environments put their title straight into `title=#1`, so a title that contains a comma must be wrapped in double braces: `\begin{readme}[{{Title, with comma}}]`.

## Deck structure

The main flow is pages 1–29, the appendix pages 30–52, and the final page 53 is **Resources and contact**. The button on page 29 skips the appendix. `../docs/source-reuse-map.md` maps every reused source slide to its new page.
