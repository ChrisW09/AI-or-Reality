"""Streamlit AppTest: startup, offline path, explicit-call boundary, persistence.

AppTest drives the script without a browser; it is not a visual check.
"""
import json

from streamlit.testing.v1 import AppTest

import generation as gen
from conftest import APP_DIR, FAKE_KEY, FakeResponse, completion


def make_app():
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def batch_body(model):
    items = [{"slot_id": s["slot_id"], "status": "written",
              "passage": f"Live-style passage for {s['slot_id']}: smoking and health, written plainly for review."}
             for s in gen.BALANCED_SLOTS]
    return completion(json.dumps({"examples": items}), model=model)


def all_text(at):
    parts = [e.value for e in at.markdown] + [e.value for e in at.caption] + [e.value for e in at.error]
    parts += [e.value for e in at.warning] + [e.value for e in at.info] + [e.value for e in at.success]
    return "\n".join(str(p) for p in parts)


def test_starts_without_credentials_and_shows_wrapper(post):
    at = make_app()
    assert at.title[0].value == "Classroom misinformation lab"
    assert gen.EXERCISE_WARNING in at.error[0].value and gen.WHO_URL in at.error[0].value
    assert at.toggle(key="offline").value is True
    assert at.text_input(key="gen_model_economy").value == "mistralai/ministral-8b-2512"
    assert at.text_input(key="gen_model_advanced").value == "mistralai/mistral-large-2512"
    assert "No OpenRouter key found" in all_text(at)
    assert post.calls == []


def test_offline_fixtures_review_and_persistence(post):
    at = make_app()
    at.button(key="btn_load_fixtures").click().run()
    ds = at.session_state["dataset"]
    assert ds["source_type"] == "fixture" and len(ds["rows"]) == 8
    assert "FIXTURE" in all_text(at)
    # a review change persists and does not call anything
    rid = ds["rows"][0]["row_id"]
    key = f"rev_0_{rid}"
    at.radio(key=key).set_value("excluded").run()
    assert at.session_state["dataset"]["rows"][0]["review_status"] == "excluded"
    at.text_input(key="gen_model_economy").set_value("vendor/other").run()
    assert at.session_state["dataset"]["rows"][0]["review_status"] == "excluded"
    assert len(at.session_state["dataset"]["rows"]) == 8
    assert post.calls == []


def test_offline_single_example_is_a_labelled_fixture(post):
    at = make_app()
    at.button(key="btn_single").click().run()
    assert len(at.session_state["singles"]) == 1
    assert at.session_state["singles"][0]["source_type"] == "fixture"
    assert post.calls == []


def test_live_balanced_set_is_two_calls_then_no_more(post, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    post.push(FakeResponse(200, batch_body("mistralai/ministral-8b-2512")))
    post.push(FakeResponse(200, batch_body("mistralai/mistral-large-2512")))
    at = make_app()
    at.toggle(key="offline").set_value(False).run()
    assert post.calls == []                      # switching mode calls nothing
    at.button(key="btn_gen_both").click().run()
    assert not at.exception
    assert [c["json"]["model"] for c in post.calls] == ["mistralai/ministral-8b-2512", "mistralai/mistral-large-2512"]
    a, b = (c["json"] for c in post.calls)
    assert a["messages"] == b["messages"] and a["max_tokens"] == b["max_tokens"] and a["temperature"] == b["temperature"]
    assert a["provider"] == b["provider"] == {"order": ["mistral/eu"], "allow_fallbacks": False,
                                              "require_parameters": True}
    ds = at.session_state["dataset"]
    assert len(ds["rows"]) == 8 and all(r["review_status"] == "awaiting_review" for r in ds["rows"])
    assert len(at.session_state["calls"]) == 2
    # reruns from unrelated widgets do not repeat calls
    at.text_input(key="gen_model_advanced").set_value("vendor/changed").run()
    at.radio(key="single_role").set_value("advanced").run()
    at.run()
    assert len(post.calls) == 2 and len(at.session_state["dataset"]["rows"]) == 8
    # the key is never stored or rendered
    assert FAKE_KEY not in json.dumps(at.session_state["dataset"]) + json.dumps(at.session_state["calls"], default=str)
    assert FAKE_KEY not in all_text(at)


def test_live_failure_is_reported_and_other_generator_kept(post, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    post.push(FakeResponse(200, batch_body("mistralai/ministral-8b-2512")))
    post.push(FakeResponse(402, {"error": {"code": 402, "message": "Insufficient credits"}}))
    at = make_app()
    at.toggle(key="offline").set_value(False).run()
    at.button(key="btn_gen_both").click().run()
    ds = at.session_state["dataset"]
    assert len(ds["rows"]) == 4 and {r["generator_role"] for r in ds["rows"]} == {"economy"}
    assert len(ds["problems"]) == 4 and ds["problems"][0]["problem"] == "call_failed:credits"
    assert "Insufficient credits" in all_text(at) or "credits" in all_text(at)
    assert len(post.calls) == 2


def test_live_mode_without_key_disables_paid_buttons(post):
    at = make_app()
    at.toggle(key="offline").set_value(False).run()
    assert at.button(key="btn_gen_both").disabled
    assert "Live mode needs OPENROUTER_API_KEY" in all_text(at)
    assert post.calls == []


def test_key_from_dotenv_file_enables_live_mode(post, monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv, "dotenv_values",
                        lambda path: {"OPENROUTER_API_KEY": FAKE_KEY} if path == APP_DIR / ".env" else {})
    at = make_app()
    at.toggle(key="offline").set_value(False).run()
    assert not at.button(key="btn_gen_both").disabled
    assert "OpenRouter key found (.env file)" in all_text(at)
    assert FAKE_KEY not in all_text(at)
    assert post.calls == []


def test_fixtures_and_live_rows_cannot_mix(post, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    at = make_app()
    at.button(key="btn_load_fixtures").click().run()
    at.toggle(key="offline").set_value(False).run()
    assert at.button(key="btn_gen_both").disabled
    assert post.calls == []


def test_review_note_persists_without_calls(post):
    at = make_app()
    at.button(key="btn_load_fixtures").click().run()
    rid = at.session_state["dataset"]["rows"][1]["row_id"]
    at.radio(key=f"rev_0_{rid}").set_value("excluded").run()
    at.text_input(key=f"note_rev_0_{rid}").set_value("changed the assigned claim").run()
    row = at.session_state["dataset"]["rows"][1]
    assert row["review_status"] == "excluded" and row["review_note"] == "changed the assigned claim"
    at.run()
    assert at.session_state["dataset"]["rows"][1]["review_note"] == "changed the assigned claim"
    assert post.calls == []
