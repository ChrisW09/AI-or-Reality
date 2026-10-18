# Classroom misinformation lab: full app (generate + detect & compare)

> **Classroom exercise.** This app produces deliberately false health claims (for example, "cigarettes are healthy") **for teaching only**. They are not health advice. Do not copy, post or share them.
> **Fact:** smoking is harmful. Tobacco damages nearly every organ in the body, and there is no safe level of tobacco use: [WHO tobacco fact sheet](https://www.who.int/news-room/fact-sheets/detail/tobacco).

This is the tested fallback for the whole lecture: the generator from Prompt A plus the Detect & compare tab from Prompt B. Keep it outside the live-coding folder.

## Start

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py          # opens http://localhost:8501
```

The app starts in **offline demonstration mode**: no key needed, no network calls. Live mode needs `OPENROUTER_API_KEY`. Copy `.env.example` to `.env` and replace the placeholder; Git ignores `.env`. An environment variable takes precedence, and `.streamlit/secrets.toml` (copied from its `.example` file) also works. The app shows only whether a key was found, never the key itself.

## The two tabs

**Generate**
- **One example:** one paid call. Single examples are for exploration only and never enter the dataset.
- **Balanced dataset:** 2 generators × {TRUE, FALSE} claim × {social post, scientific-style paragraph}, one example per cell, so **8 rows from 2 calls**.
  - Both models receive the identical prompt, with the same fixed claims and word ranges.
- **Generation failures** are listed separately: refusals, missing, duplicate or invalid records, failed calls.
- **Instructor review:** every live row starts as `awaiting_review` and is set to `approved` or `excluded`, with a note. Review flags are hints only:
  - invented sources or numbers
  - hedged wording
  - wording that argues against the assigned claim
  - label leaks
- **Optional extension:** 3 rows per cell, so 24 rows, still one call per model. It is for preparation, not the lecture.

**Detect & compare**
1. **Freeze** the approved rows (at most 8 in the live design). Freezing fixes a dataset hash, a deterministic shuffled order and blind IDs before any verdict exists.
2. **Run both detectors:** one batch call each, so two calls.
   - Each detector receives only the blind IDs, the passages, the same evidence packet (four WHO statements, retrieved 18 Oct 2026) and the same fixed instructions.
   - It answers `supported`, `contradicted` or `insufficient_evidence`, with a reason and an evidence reference.
3. **Results:** the 2 × 2 generator × detector matrix, every example (labels and generators hidden until you reveal them), and the detector call details.
4. **Pasted passage:** a verdict only. It has no label and is never scored.

What the detectors never receive: intended labels, generator identity, row IDs, review metadata, generation prompts, the correction, the exercise wrapper. Passages are marked as untrusted data, and the tests check this.

## Metrics (per generator × detector cell)

| Term | Definition |
|---|---|
| Positive class | a FALSE claim. `contradicted` is a positive prediction, `supported` a negative one |
| Correct / eligible = overall success | abstentions and failures count as unsuccessful |
| Coverage | answered / eligible |
| Abstention | `insufficient_evidence`. Never counted as a true negative, never counted as correct |
| Failures | service (the call failed) or format (malformed, missing, duplicate or unknown item) |
| False-claim recall | false items predicted `contradicted` / all eligible false items |
| False-positive rate | true items predicted `contradicted` / all eligible true items |
| Answered-only accuracy | correct / answered |
| N/A | the denominator is zero |

With 4 items per cell, one answer moves accuracy by 25 points; with 2 items per label, recall and FPR move by 50 points. **A small demonstration cannot establish an effect of model size.** A familiar tobacco claim may be easy to reject regardless of the prose.

## Result types (always labelled in the app and the export)

| Label | Passages | Verdicts |
|---|---|---|
| MEASURED | live generations from this session, reviewed and frozen | live detectors |
| FIXTURE CONTROL | hand-authored fixtures | live detectors. This tests the detectors; it is not a generator comparison |
| ILLUSTRATIVE | hand-authored fixtures | hand-authored verdicts (offline). Nothing measured |
| RECORDED | real outputs from the rehearsal on 18 Oct 2026 (`recorded_run.json`) | replayed, not measured again |

Fixture, recorded and live rows can never be mixed in one dataset.

## Models, routing and limits

The IDs come from `models.json` and stay editable separately for generators and detectors:

| Role | ID | Documented size |
|---|---|---|
| economy | `mistralai/ministral-8b-2512` | 8.4B + 0.4B vision |
| advanced | `mistralai/mistral-large-2512` | MoE, 41B active / 675B total |

- Routing: `provider: {"order": ["mistral/eu"], "allow_fallbacks": false}`. This picks an endpoint of the same model; the default endpoint was rate-limited in rehearsal.
- Timeouts: 5 s connect, 20 s read, and a 60 s total deadline checked while the response streams in.
- Output limits: 1200 tokens for a generation batch and 1400 for a detector batch of 8.
- No retries, no fallback models, no JSON-repair calls. Every paid action is an explicit button, and the retry buttons make exactly one call.
- The cost shown is the one OpenRouter reports, or "unavailable" when none is returned.

## Tests

```bash
python -m pytest -q tests      # 91 tests, about 3 s, no network
```

- `test_client.py`: HTTP errors (400 to 503), 200 responses with an error body, refusals, empty, truncated and non-JSON responses, read timeouts, the total deadline, key redaction and routing.
- `test_generation.py`: identical prompts, parsing (invalid JSON, missing, duplicate and unknown IDs, declines), review flags, fixtures, source separation and export.
- `test_detection.py`: verdict parsing, the confusion counts, abstentions and failures, N/A denominators, the always-contradicted baseline, 25/50-point sensitivity, freezing and blind IDs, and a metadata-leak check.
- `test_app.py` and `test_app_detect.py`: Streamlit AppTest flows with mocked HTTP:
  - startup without a key, and the offline illustrative path
  - live generate → review → freeze → detect, with exactly 4 calls and no repeats on reruns
  - one detector failing while the other's results are kept, plus the explicit retry
  - malformed detector output, pasted passages, and the fixture-control label

AppTest is not a visual check. See `docs/validation-report.md` in the lecture package for the browser and live tests.
