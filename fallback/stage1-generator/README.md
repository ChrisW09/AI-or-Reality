# Classroom misinformation lab: stage 1 (generator)

> **Classroom exercise.** This app produces deliberately false health claims (for example, "cigarettes are healthy") **for teaching only**. They are not health advice. Do not copy, post or share them.
> **Fact:** smoking is harmful. Tobacco damages nearly every organ in the body, and there is no safe level of tobacco use: [WHO tobacco fact sheet](https://www.who.int/news-room/fact-sheets/detail/tobacco).

This is the stage-one snapshot: the generator that Prompt A builds. Use it as the fallback when the live build is not ready after about two minutes. Detection lives in `../full-app/`.

## Start

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app opens in **offline demonstration mode**, which needs no key and makes no network calls.

Live mode needs `OPENROUTER_API_KEY`. Copy `.env.example` to `.env` and replace the placeholder. An environment variable takes precedence, and `.streamlit/secrets.toml` (copied from its `.example` file) also works. Git ignores both `secrets.toml` and `.env`. The app shows only *whether* a key was found, never the key itself.

## What it does

- **One example:** one paid call. You choose the generator role, the format (social post or short scientific-style paragraph) and the assigned claim (TRUE or FALSE). Single examples never enter the balanced dataset.
- **Balanced dataset:** at most one batch call per generator, so two calls in total.
  - Each model receives the **identical** prompt: the same fixed claims, formats and word ranges. Only the model ID differs.
  - The design is 2 generators × 2 claims × 2 formats = 8 examples.
- **Validation:** every record is checked locally (JSON structure, slot IDs, duplicates, missing slots, declines, empty text).
  - Problems are listed as *generation failures* and never enter the dataset.
  - Review flags are hints for the instructor. They never accept or reject a row on their own:
    - invented sources or numbers
    - hedged wording
    - wording that may argue against the assigned claim
    - label leaks
- **Instructor review:** live rows start as `awaiting_review`. Only `approved` rows can be scored later. The "intended label" records what the generator was *asked* to argue; it is not verified truth.
- **Offline fixtures:** eight hand-authored passages cover the same 2 × 2 × 2 design. They are labelled `FIXTURE` everywhere and cannot be mixed with live rows.
- **Export:** a JSON file wrapped in the exercise warning, the correction and the WHO link. It contains no key.

## Models and routing (`models.json`)

| Role | Exact ID | Documented size |
|---|---|---|
| economy | `mistralai/ministral-8b-2512` | 8.4B dense language model + 0.4B vision encoder |
| advanced | `mistralai/mistral-large-2512` | mixture-of-experts, 41B active / 675B total parameters |

The sizes come from the vendor's model cards; price is not a measure of size. Both IDs stay editable in the app, and an ID that is not in `models.json` is shown as "size not documented". The app never substitutes another model.

Requests carry `provider: {"order": ["mistral/eu"], "allow_fallbacks": false}` from `models.json`, which picks an endpoint of the **same** model. In rehearsal on 18 Oct 2026, the default endpoint of Mistral Large returned HTTP 429 ("rate-limited upstream"), while the EU endpoint answered. You can edit the order in the sidebar; leave it empty to use OpenRouter's default routing.

## Limits

| Setting | Value |
|---|---|
| connect / read timeout | 5 s / 20 s |
| total deadline (checked while the response streams in) | 60 s, so the worst case is about 80 s |
| output limit | 400 tokens (single), 1200 tokens (batch of 4) |
| automatic retries / fallback models | none |

The cost shown is the one OpenRouter reports; if it is not returned, it is shown as unavailable.

## Tests

```bash
python -m pytest -q tests
```

The tests cover the client (HTTP errors, refusals, empty, truncated and non-JSON responses, timeouts, sanitizing), parsing and validation, review flags, the balanced design, source separation and export. They also run Streamlit AppTest: startup without a key, the offline path, review persistence, and the explicit-call boundary with mocked HTTP. No test makes a network call. AppTest is not a visual browser check.
