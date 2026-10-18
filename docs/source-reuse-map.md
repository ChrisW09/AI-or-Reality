# Source and reuse map

> **Page numbers.** The "new page" numbers below refer to an earlier 53-page draft of the deck. The current deck has 47 pages: main flow 1–26, appendix 27–46, *Resources and contact* on 47 (see `slides-latex/README.md`). The mapping from source slides to content is unchanged.

The lecture deck *AI or Reality? Can We Tell the Difference?* (60-minute edition with a live build) was prepared on 18 Oct 2026. This file records:

- what was supplied, and what was reused from it;
- where each reused item now sits in the new deck;
- what was changed, and what was deliberately removed.

Page numbers for the new deck refer to `lecture-slides.pdf`, which has 53 pages. Page numbers for the source deck refer to `ai-or-reality-models_no-notebooks.pdf`, which has 41 pages.

---

## 1. Inventory of the supplied folder

| Item | What it is | Used? |
|---|---|---|
| `ai-or-reality-models_no-notebooks.pdf` | The source presentation: 41 pages, 16:9, built from `src/main-nonb.tex` (no-notebook switch on `src/main.tex`) | **Yes.** It is the content source for the title, image challenge, thesis and LLM introduction, pages 1–18. |
| `src/main.tex` (1,991 lines), `main-nonb.tex`, `main-nonb-notes.tex`, `main-notes.tex`, `main-export.tex` | LaTeX source of the source deck, with switch wrappers | **Yes, `main.tex` only**, for the exact slide text, the TikZ diagrams (rebuilt and recoloured) and the speaker notes (used selectively). The wrapper files were not needed. |
| `src/references.bib` | Bibliography of the source deck (citation review of 16 Oct 2026) | **Yes.** 15 entries copied unchanged (see §7). |
| `src/figures/face_fake_a.jpg`, `face_real_b.jpg`, `arc_real.jpg`, `arc_ai.png` | Quiz images, Rounds 1–2 | **Yes** (see §5). |
| `src/figures/hotel_ai.jpg`, `src/generated/diff_0.jpg` … `diff_4.jpg` | Diffusion-strip images for source Part 2 (Images) | **No.** Part 2 lies outside the agreed cutoff. |
| `src/qa/fit.py`, `deficit.py`, `notes_fit.py` | Layout-QA scripts written for the source deck's theme | **No.** The new deck uses the chapter-00 template, so it was checked with its own LaTeX overfull-box log, a full-page render and a notes-fit check (see `validation-report.md`). |
| `src/qa/citation-review-2026-10-16.md` | Citation log of the source deck | Not needed. The reused references were copied after that review. |
| `src/README.md` | Build, timing and fact-check history of the source deck | Read for the build engine, timing and context only. |
| `chapter_00/chapter_00.tex` (2,925 lines) | **Visual and technical template** (Quantitative Research Methods, Chapter 0) | **Yes.** Lines 1–87 (the preamble) were copied verbatim; see §2. |
| `chapter_00/chapter_00.pdf`, `chapter_00a.pdf` (133 pages each) | Compiled template | Used as the visual reference: rendered and compared. |
| `chapter_00/images/ch00_profile.jpg` (640 × 800) | Presenter photograph, as used by the template's "About your lecturer" slide | **Yes**, new p2. |
| `chapter_00/profile.jpg` (2399 × 1599) | Original, uncropped photograph | **No.** The template's own processed portrait was used, so that the slide is identical to the template. |
| `chapter_00/images/ch00_*.png` (19 statistics figures) | Figures for the statistics refresher | No (off-topic). |
| `chapter_00/chapter_00_lab.ipynb`, `make_figures.py`, `.figures.stamp` | Lab notebook and figure generator for chapter 0 | No. |
| `chapter_00/*.aux, .log, .nav, .out, .snm, .toc, .vrb, .fls, .fdb_latexmk` | Build artefacts | No. The log was read to confirm the engine: pdfTeX, TeX Live 2026. |

No reference app, earlier prompts or other supporting images were supplied.

---

## 2. Template: what was reused, and the documented deviations

**Reused verbatim.** `slides-latex/template-preamble.tex` is `chapter_00/chapter_00.tex` lines 1–87, unchanged; that is everything before `\begin{document}`. It provides:

- `beamer` at `aspectratio=169` and 11pt, Madrid theme with the default colour theme, no navigation symbols, and the **frame-number footer**;
- the custom **headline with horizontal section navigation**;
- rounded blocks, the `accent` colour (RGB 38, 70, 140) and the Python `listings` style;
- the template's `tcolorbox` styles, used semantically throughout:
  - `takeaway` for key messages
  - `readme` for explanations
  - `numexample` for worked numbers and settings
  - `exercise` for votes and predictions
  - `solutionbox` for reveals
  - `labnote` for live-coding and course material
  - `mistake` for warnings;
- `fontawesome5`, `hyperref`, `booktabs` and `colortbl`.

The engine is **pdfLaTeX**, as in the template.

The **About your lecturer** slide (new p2) reproduces the template's slide 2: the same clipped, rounded photograph at `0.72\textheight`, the same name line, degrees and four bullets. The template's course-repository line was replaced by the e-mail line alone; both repositories appear on p15 and p53.

**Lecture additions** live in a separate file, `slides-latex/lecture-setup.tex`, and override only the title fields:

- title-slide content;
- links to the two course repositories;
- a `\slidesource` macro that copies the look of the template's `\islpsource`;
- quiz badges and token chips from the source deck, recoloured to `accent`;
- a plain-text listing style for the prompts (no shell escape).

**Documented deviations**

| Deviation | Reason |
|---|---|
| `\AtBeginSection[]{}` switches off the template's automatic "Outline" frame at each section. | Six outline frames do not fit a 60-minute lecture with two live builds. The overview slide (p3) and the template's headline navigation take over that role. |
| Bibliography uses `biblatex` with `backend=bibtex`, not biber. `date` fields became `year`/`month`, and `csquotes` was added. | On the preparation machine biber fails to start with "extracting arm64 binary with lipo failed". This happens both inside and outside the sandbox, and also under Rosetta. The bibtex backend needs only a standard TeX Live. |
| Presenter-notes edition via `pgfpages` ("show notes on second screen=right"), built from `main-notes.tex`. | The template has no notes mechanism. This follows the source deck's approach. |
| Box titles that contain a comma are wrapped in double braces, `[{{…}}]`. | The template's boxes pass the title straight into `title=#1`, so a comma would end the option list. |
| No frame subtitles; the source deck's subtitles became a lead line in the body. | The template does not use frame subtitles. |
| Source-deck palette (violet = synthetic, amber = real, teal = verification) mapped to the template's `accent`, teal and red. | Only the template's visual design is used. |

---

## 3. Content cutoff

**Decision.** Reuse runs **through source p18**, the end of source Part 1 "Text". Question 1 and its solution (source p17–18) go to the appendix, and their rule is echoed on the takeaway slide (new p29). Source pages **19–41 are not reused**: Part 2 Images, Part 3 Video & voice, verification, closing, backup, credits and references.

**Why it was a question.** Two boundaries were plausible after inspecting the deck: p16 (the last technical slide) and p18 (the end of Part 1, including the chat question). I asked one focused question during preparation, and you chose *"p18, Q1 to appendix (Recommended)"*.

| Source page | Source title | New deck | How |
|---|---|---|---|
| 1 | Title: *AI or Reality? Can We Tell the Difference?* | **p1** | Main flow, in template style (§4) |
| 2 | Round 1 of 3 — One of these people does not exist | **p4** | Main flow; vote line made mode-neutral (hands up, or chat if online) |
| 3 | A is synthetic — and most rooms cannot tell | **p5** | Main flow; findings in a `solutionbox` |
| 4 | Round 2 of 3 — One is a photograph, one is a prompt | **p6** | Main flow |
| 5 | B was the prompt | **p7** | Main flow; "tells" in a `solutionbox` |
| 6 | Round 3 of 3 — One of these is Warren Buffett | **p8** | Main flow |
| 7 | A was the machine | **p9** | Main flow; "for this session" changed to "for an earlier session" (the quote was generated for the source session) |
| 8 | Thesis (dark slide): evidence was expensive to fake | **p10** | Main flow, template style; last line adapted to "Today: how a language model writes text — and what it takes to check a claim it writes" |
| 9 | Three families — one architecture underneath | **p43** | Appendix (today covers only the text lane) |
| 10 | Part divider "1 · Text" | — | Not reused. Replaced by the template's section headline "How LLMs write" |
| 11 | Idea 1 — Language models predict the next token | **p11** | Main flow; "Idea 1 —" dropped from the title |
| 12 | What the model actually reads: tokens, not words | **p12** | Main flow, **with the mandatory deletion** (§6) |
| 13 | One level deeper: attention | **p44** | Appendix |
| 14 | Why the same prompt never gives the same answer | **p13** (condensed) + **p45** (full) | Inference column of the new "Training happens once — inference happens on every request" slide; full slide in the appendix |
| 15 | From raw predictor to assistant — three stages | **p13** (condensed) + **p46** (full) | Training column of the new p13; full slide in the appendix |
| 16 | Plausibility is the product — truth is not guaranteed | **p14** | Main flow |
| 17 | Your turn — the chat, please (Question 1 of 3) | **p47** | Appendix, optional |
| 18 | The pattern behind your answers (Solution 1) | **p48** | Appendix; its rule "never ship unverified output" reappears in takeaway 3 on **p29** |

The LLM introduction runs from minute 09 to 13. It covers p10 and p11–14 (five frames). The full versions of p13–15 and 17–18 stay available in the appendix, so nothing from the requested range was dropped silently.

**Speaker notes.** Notes on reused slides come from the source deck's notes. Zoom- and notebook-specific instructions were removed or made mode-neutral, and timing marks were re-planned for the new 60-minute schedule. Exact figures kept for Q&A include Nightingale & Farid, Miller et al., Jakesch et al., InstructGPT, Mata v. Avianca and NewsGuard. New slides have new notes.

**New slides, not from the source:** p3, p13 (combined), p15–29, p30–42 and p49–53. p49 (image credits) reuses the source credit lines for the reused images.

---

## 4. Title slide and presenter

| Field | Source |
|---|---|
| Title *AI or Reality? Can We Tell the Difference?* | Source title slide, verbatim |
| Author *Prof. Dr. Christoph Weisser* | Source title slide |
| Institute *Hochschule Bielefeld – University of Applied Sciences and Arts (HSBI)* | Source title slide (`\institute`) |
| E-mail *christoph.weisser@hsbi.de* (clickable `mailto:`) | Source title slide; matches the template and the official HSBI profile, re-checked on 18 Oct 2026 (the `mailto:` link is present on the page) |
| Date *2026* | Source title slide (year only; no lecture date added) |
| "All images are credited in the appendix." | Adapted from the source note "all images credited at the end" |
| Subtitle *Fluent text, false claims and a live experiment with language models* | **New**, describing this lecture |
| Kicker "ONLINE SESSION · HOW THE MODELS WORK" | **Not used**: the delivery mode of this lecture is not specified, and the subtitle replaces it |

**Presenter slide (p2).** It is a verbatim copy of the template's chapter-00 slide 2:

- *Prof. Dr. rer. pol. Christoph Weisser*, *MLitt (St Andrews), MSc (Oxford)*;
- Professor of Mathematics, in particular Business Data Science, at HSBI;
- former Technical Lead for Artificial Intelligence and Industrial PhD Supervisor at BASF;
- Research: Data Science, Machine Learning and Artificial Intelligence;
- Focus: application of AI in business and industry.

Photograph: `images/ch00_profile.jpg` (640 × 800), the file the template uses, at the template's size and aspect ratio. No biography was added beyond the template's. The HSBI profile also shows "Business Data Science" and "Fachbereich Wirtschaft", which is consistent with the bullets.

---

## 5. Images and quiz answers

| File in `slides-latex/images/` | Origin | Pixels | Licence / credit (from source credits slide, source p36) | New page |
|---|---|---|---|---|
| `face_fake_a.jpg` | `src/figures/` | 800 × 800 | "Woman 1.jpg": StyleGAN2 / thispersondoesnotexist.com output, via Wikimedia Commons, public domain (PD-algorithm) | p4, p5 |
| `face_real_b.jpg` | `src/figures/` | 800 × 800 | "Headshot C. Estelle Smith" by FauxNeme, CC BY-SA 4.0, via Wikimedia Commons; cropped | p4 |
| `arc_real.jpg` | `src/figures/` | 960 × 688 | "Arc de Triomphe de l'Étoile at night" by Wilfredor, CC0, via Wikimedia Commons | p6, p7 |
| `arc_ai.png` | `src/figures/` | 960 × 480 | "Christmas at Arc de Triomphe 2023" by Sérgio Valle Duarte via Midjourney, CC BY 3.0, via Wikimedia Commons | p6, p7 |
| `ch00_profile.jpg` | `chapter_00/images/` | 640 × 800 | Presenter photograph from the author's chapter-00 deck | p2 |
| `card_excluded_crop.png` | Screenshot of this lecture's app (recorded rehearsal, 18 Oct 2026), cropped | 804 × 712 | Own screenshot; no key visible | p21 |
| `app_matrix.png` | Screenshot of this lecture's app (Detect & compare tab, recorded rehearsal) | 1640 × 1022 | Own screenshot; no key visible | p42 |

All images are included at their original resolution and aspect ratio (`height=` or `width=` only, never both). Diagrams are TikZ, rebuilt from the source deck's code.

**Quiz answers.** All were verified from the source deck's reveal slides and credits, so none needed an "unknown provenance" note:

| Round | A | B | Revealed on |
|---|---|---|---|
| 1 (faces) | synthetic (StyleGAN2, 2019 technology) | real portrait | p5 |
| 2 (Arc de Triomphe) | real long-exposure photograph (2024) | Midjourney render, prompt public | p7 |
| 3 (Buffett) | generated by a large language model for the source session | Warren Buffett, Berkshire Hathaway shareholder letter for 2013 | p9 |

---

## 6. Mandatory correction: tokenisation slide (source p12 → new p12)

**Removed from the slide, the notes and the references.** The deleted wording is deliberately not reproduced here.

1. The **third tokenizer row**: its token-count label, its caption naming a numeric example, and every chip of that row, including the highlighted number chips and their colour style. The chip macro for numeric tokens was not carried over.
2. The **right-hand bullet** about how a tokenizer splits numbers, including its claim about arithmetic.
3. The **speaker-note paragraph** that explained that row and cited the digit-grouping study.
4. The **chat question** in the notes about handing number-heavy documents to a language model.
5. The **source-line clause** citing the digit-grouping paper. That paper's bibliography entry was not copied into `references.bib`.
6. The takeaway now reads "The model never sees **letters or words**". The digit reference was dropped, so that no trace of the deleted example remains.

**Kept and rebalanced.** The English row (6 tokens) and the German row (10 tokens) are kept. The chips are now one size larger, and the language-pricing point moved into a full-width `readme` box. The takeaway box and the source line (tokenizer and date as in the source; Petrov et al. 2023) remain, with no empty placeholder. No replacement claim about tokenizers or arithmetic was added.

**Verification (18 Oct 2026).** A regex search ran over:

- the text extracted from both compiled PDFs, including the notes pane of `lecture-slides-with-notes.pdf`;
- every deck source file (`main.tex`, `main-notes.tex`, `lecture-setup.tex`, `template-preamble.tex`, `data/*.tex`, `references.bib`).

It used 27 exact and near-match patterns: fragments of the deleted row, the bullet, the note and the cited authors, plus generic number and arithmetic terms. **It found 0 hits in the deck.** The only match anywhere was the template preamble's unrelated `\euro` macro definition. Page 12 was also inspected visually in the rendered PDF.

---

## 7. Factual sources

**New on the slides**

| Source | Used for |
|---|---|
| WHO fact sheet **"Tobacco and nicotine"**, dated 26 June 2026, `https://www.who.int/news-room/fact-sheets/detail/tobacco`, retrieved 18 Oct 2026 | Correction text (p3, app); evidence packet on p23 and verbatim on p39. E1 verbatim (Key facts); E2 verbatim (Overview); E3 shortened, without the number of cancer types (Overview); E4 verbatim without the death figure (section "Second-hand smoke kills") |
| Mistral AI model cards on Hugging Face: *Ministral 3 8B Instruct 2512* (8.4B language model + 0.4B vision encoder) and *Mistral Large 3 675B Instruct 2512* (41B active / 675B total) | Documented model sizes (p19, p40, `models.json`) |
| OpenRouter API documentation (quickstart, authentication, models, structured outputs, provider routing, parameters, errors and debugging, usage accounting), read 18 Oct 2026 | App design and settings (p16, p19, p40) |
| Streamlit documentation (session state, forms, secrets, AppTest) | App design (p19) |
| Claude Code for VS Code extension, version 2.1.301 (labels read from the installed package) | UI names on p16 |

**Reused from the source deck** (15 `references.bib` entries, unchanged):

- Nightingale & Farid 2022 and Miller et al. 2023 (p5)
- Jakesch et al. 2023 and Buffett 2014 (p9)
- Vaswani et al. 2017 (p11, p43, p44)
- Petrov et al. 2023 (p12)
- Ouyang et al. 2022 and Holtzman et al. 2020 (p13, p45, p46)
- Bahdanau et al. 2015 (p44)
- Goodfellow et al. 2014, Ho et al. 2020, Rombach et al. 2022 and Chen et al. 2025 (p43)
- Mata v. Avianca 2023 (p48, notes)
- NewsGuard 2026 (notes)

The tokenizer note "o200k_base, 1 Sept 2026" on p12 is carried over from the source and was not re-run.

**App-derived content** (from this lecture's own app, not external sources):

- p21: screenshot of the excluded rehearsal row;
- p27: rehearsal 2 × 2 matrix, generated from `fallback/full-app/recorded_run.json` by `slides-latex/tools/make_rehearsal_table.py`;
- p41: every rehearsal example and call;
- p42: matrix screenshot;
- p21 rehearsal counts: the economy model reversed its TRUE claim in 2 of 5 reviewed batches, the advanced model in 0 of 4.

All of these are real outputs measured on 18 Oct 2026, labelled as rehearsal results and never as today's live result.
