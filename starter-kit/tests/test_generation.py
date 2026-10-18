"""Generation logic: identical requests, strict validation, no silent mixing."""
import json

import pytest

import generation as gen
from conftest import FAKE_KEY
from openrouter_client import CallResult


def ok_result(content, model="vendor/m"):
    return CallResult(ok=True, model_requested=model, started_at_utc="2026-10-18T00:00:00+00:00",
                      elapsed_s=1.0, settings={}, messages=[], content=content)


def batch(items):
    return json.dumps({"examples": items})


def good_items():
    return [{"slot_id": s["slot_id"], "status": "written",
             "passage": f"Passage for {s['slot_id']} about smoking and health in plain words here."}
            for s in gen.BALANCED_SLOTS]


def test_design_is_balanced():
    cells = {(s["label"], s["format"]) for s in gen.BALANCED_SLOTS}
    assert len(gen.BALANCED_SLOTS) == 4 and len(cells) == 4


def test_both_models_get_identical_messages():
    a = gen.build_messages(gen.BALANCED_SLOTS, structured=True)
    b = gen.build_messages(gen.BALANCED_SLOTS, structured=True)
    assert a == b
    user = a[1]["content"]
    for c in gen.CLAIMS.values():
        assert c["text"] in user


def test_messages_have_no_wrapper_or_correction():
    text = json.dumps(gen.build_messages(gen.BALANCED_SLOTS, structured=True))
    assert gen.CORRECTION not in text and gen.EXERCISE_WARNING not in text


def test_parse_valid_batch():
    acc, probs = gen.parse_generation(batch(good_items()), gen.BALANCED_SLOTS)
    assert set(acc) == {"S1", "S2", "S3", "S4"} and probs == []


def test_parse_strips_single_code_fence_only():
    acc, _ = gen.parse_generation("```json\n" + batch(good_items()) + "\n```", gen.BALANCED_SLOTS)
    assert len(acc) == 4


@pytest.mark.parametrize("content", ["not json", "[]", '{"examples": "x"}', '{"other": []}'])
def test_parse_invalid_json_fails_every_slot(content):
    acc, probs = gen.parse_generation(content, gen.BALANCED_SLOTS)
    assert acc == {} and {p["problem"] for p in probs} == {"invalid_json"} and len(probs) == 4


def test_parse_partial_problems_keep_valid_rows():
    items = good_items()
    items[0]["status"] = "declined"; items[0]["passage"] = ""
    items[1]["passage"] = "   "
    items.append(dict(items[2]))                 # duplicate S3
    items.append({"slot_id": "S9", "status": "written", "passage": "x"})
    del items[3]                                 # S4 missing (index 3 after edits is the S4 record)
    acc, probs = gen.parse_generation(batch(items), gen.BALANCED_SLOTS)
    kinds = {p["slot_id"]: p["problem"] for p in probs}
    assert acc == {}
    assert kinds["S1"] == "declined" and kinds["S2"] == "empty" and kinds["S3"] == "duplicate_id"
    assert kinds["S4"] == "missing"
    assert "unknown_id" in kinds.values()


def test_parse_missing_and_bad_fields():
    items = good_items()[:2] + [{"slot_id": "S3", "status": "maybe", "passage": "x"}]
    acc, probs = gen.parse_generation(batch(items), gen.BALANCED_SLOTS)
    kinds = {p["slot_id"]: p["problem"] for p in probs}
    assert set(acc) == {"S1", "S2"} and kinds == {"S3": "invalid_fields", "S4": "missing"}


def test_rows_from_generation_await_review_and_keep_labels_separate():
    rows, probs = gen.rows_from_generation(ok_result(batch(good_items())), role="economy",
                                           slots=gen.BALANCED_SLOTS, run_id="c01")
    assert len(rows) == 4 and probs == []
    for r in rows:
        assert r["review_status"] == "awaiting_review" and r["source_type"] == "live"
        assert r["intended_label"] in ("true", "false") and r["intended_label"] not in r["passage"]
        assert r["correction"] == gen.CORRECTION and r["exercise_label"] == gen.EXERCISE_WARNING
    assert len({r["row_id"] for r in rows}) == 4


def test_failed_call_becomes_generation_failures():
    res = CallResult(ok=False, model_requested="vendor/m", started_at_utc="t", elapsed_s=0, settings={},
                     messages=[], status="credits", message="no credits")
    rows, probs = gen.rows_from_generation(res, role="advanced", slots=gen.BALANCED_SLOTS, run_id="c02")
    assert rows == [] and len(probs) == 4 and probs[0]["problem"] == "call_failed:credits"


def test_review_flags():
    f = gen.review_flags("A 2023 study by researchers at a university shows smoking is great.", "false", "social_post")
    assert any("number" in x for x in f) and any("source" in x for x in f)
    assert gen.review_flags("This is a classroom exercise example of fake news about smoking cigarettes "
                            "being good for everyone who tries it today.", "false", "social_post")
    assert any("argue against" in x for x in gen.review_flags(
        "Smoking is harmful and you should quit now, it damages every organ in your body friend.", "false", "social_post"))


def test_fixtures_cover_design_and_are_clean():
    rows = gen.fixture_rows(gen.load_fixtures())
    assert len(rows) == 8
    cells = {(r["generator_role"], r["intended_label"], r["format"]) for r in rows}
    assert len(cells) == 8
    for r in rows:
        assert r["source_type"] == "fixture" and "FIXTURE" in r["generator_model"]
        assert r["flags"] == [], (r["row_id"], r["flags"])


def test_sources_never_mix():
    ds = gen.new_dataset()
    gen.add_rows(ds, gen.fixture_rows(gen.load_fixtures()), "fixture")
    with pytest.raises(gen.MixedSourceError):
        gen.replace_generator_rows(ds, "economy", [], [])
    with pytest.raises(gen.MixedSourceError):
        gen.add_rows(ds, [], "live")


def test_balance_status_detects_missing_and_review():
    ds = gen.new_dataset()
    rows, _ = gen.rows_from_generation(ok_result(batch(good_items())), role="economy",
                                       slots=gen.BALANCED_SLOTS, run_id="c01")
    gen.replace_generator_rows(ds, "economy", rows, [])
    ok, msg = gen.balance_status(ds)
    assert not ok and "Incomplete" in msg          # nothing approved, advanced missing
    for r in rows:
        gen.set_review(ds, r["row_id"], "approved")
    rows2, _ = gen.rows_from_generation(ok_result(batch(good_items())), role="advanced",
                                        slots=gen.BALANCED_SLOTS, run_id="c02")
    gen.replace_generator_rows(ds, "advanced", rows2, [])
    for r in rows2:
        gen.set_review(ds, r["row_id"], "approved")
    assert gen.balance_status(ds)[0]
    gen.set_review(ds, rows2[0]["row_id"], "excluded", "changed claim")
    assert not gen.balance_status(ds)[0]


def test_models_config_missing(tmp_path):
    cfg, problem = gen.load_models_config(tmp_path / "models.json")
    assert cfg == {} and "preflight incomplete" in problem


def test_models_config_exact_ids():
    cfg, problem = gen.load_models_config()
    assert problem is None
    assert cfg["economy"]["id"] == "mistralai/ministral-8b-2512"
    assert cfg["advanced"]["id"] == "mistralai/mistral-large-2512"


def test_export_has_context_and_no_secret(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    ds = gen.new_dataset()
    gen.add_rows(ds, gen.fixture_rows(gen.load_fixtures()), "fixture")
    out = gen.export_bundle({"dataset": ds, "singles": [], "calls": []}, "test")
    data = json.loads(out)
    assert data["exercise_warning"] == gen.EXERCISE_WARNING and data["correction_source"] == gen.WHO_URL
    assert FAKE_KEY not in out and "sk-or" not in out


def test_review_flags_catch_vague_research_and_hedging():
    f = gen.review_flags("Recent research suggests that cigarette smoking may confer protective benefits.",
                         "false", "scientific_prose")
    assert any("source" in x for x in f) and any("hedged" in x for x in f)


def test_provider_routing_from_models_json():
    cfg, _ = gen.load_models_config()
    assert gen.provider_routing(cfg) == {"order": ["mistral/eu"], "allow_fallbacks": False}
    assert gen.provider_routing({}) == {}


def test_review_flags_catch_reversed_true_claim():
    # Real rehearsal output (economy model, 2026-10-18): asked for the TRUE claim, argued the false one.
    text = ("Another day, another warning about smoking. But let's be real, it's not the cigarettes that are "
            "dangerous. My uncle smoked for decades and lived to 85. The real villains are stress and poor diet.")
    f = gen.review_flags(text, "true", "social_post")
    assert any("argue against the assigned TRUE claim" in x for x in f) and any("number" in x for x in f)
