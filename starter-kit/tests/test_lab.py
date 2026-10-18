"""lab.py: the facade the live-coded app uses. HTTP is faked; no test touches the network."""
import json

import pytest

import lab
from conftest import FAKE_KEY, FakeResponse, completion

CFG, _ = lab.load_models()


def gen_answer(slots, skip=()):
    return json.dumps({"examples": [{"slot_id": s["slot_id"], "status": "written",
                                     "passage": f"Passage for {s['slot_id']} about smoking."}
                                    for s in slots if s["slot_id"] not in skip]})


def det_answer(items, verdict="contradicted"):
    return json.dumps({"assessments": [{"id": it["id"], "verdict": verdict, "reason": "Packet says so.",
                                        "evidence_ref": "E1"} for it in items]})


def test_models_and_routing_from_models_json():
    ids = lab.default_model_ids(CFG)
    assert ids == {"economy": "mistralai/ministral-8b-2512", "advanced": "mistralai/mistral-large-2512"}
    assert lab.routing(CFG) == {"order": ["mistral/eu"], "allow_fallbacks": False}


def test_key_lookup_order(monkeypatch):
    monkeypatch.setattr(lab, "dotenv_values", lambda p: {})
    assert lab.get_api_key({}) == (None, None)
    assert lab.get_api_key({"OPENROUTER_API_KEY": "s"}) == ("s", "Streamlit secrets")
    monkeypatch.setattr(lab, "dotenv_values", lambda p: {"OPENROUTER_API_KEY": "d"})
    assert lab.get_api_key({"OPENROUTER_API_KEY": "s"}) == ("d", ".env file")
    monkeypatch.setenv("OPENROUTER_API_KEY", "e")
    assert lab.get_api_key({"OPENROUTER_API_KEY": "s"}) == ("e", "environment variable")


def test_missing_key_makes_no_request(post):
    out = lab.generate(None, "economy", "m", lab.balanced_slots(), CFG)
    assert post.calls == [] and out["rows"] == [] and not out["ok"]
    assert len(out["problems"]) == 4 and "No API key" in out["message"]


def test_generate_balanced_sends_routing_and_keeps_valid_rows(post):
    slots = lab.balanced_slots()
    post.push(FakeResponse(body=completion(gen_answer(slots, skip=("S4",)))))
    out = lab.generate(FAKE_KEY, "advanced", CFG["advanced"]["id"], slots, CFG)
    body = post.calls[0]["json"]
    assert len(post.calls) == 1 and body["model"] == CFG["advanced"]["id"]
    assert body["provider"]["order"] == ["mistral/eu"] and body["provider"]["allow_fallbacks"] is False
    assert "response_format" in body and "models" not in body
    assert len(out["rows"]) == 3 and [p["problem"] for p in out["problems"]] == ["missing"]
    assert all(r["review_status"] == "awaiting_review" for r in out["rows"])
    assert FAKE_KEY not in json.dumps(out)
    ds = lab.new_dataset()
    lab.store_generation(ds, "advanced", out)
    assert ds["source_type"] == "live" and len(ds["rows"]) == 3


def test_single_slot_validation():
    assert lab.single_slot("false", "social_post")[0]["label"] == "false"
    with pytest.raises(ValueError):
        lab.single_slot("maybe", "social_post")


def test_fixtures_never_mix_with_live(post):
    ds = lab.new_dataset()
    lab.load_fixtures(ds)
    assert len(ds["rows"]) == 8 and ds["source_type"] == "fixture"
    with pytest.raises(ValueError):
        lab.store_generation(ds, "economy", {"rows": [], "problems": []})


def test_offline_freeze_illustrative_and_matrix(post):
    ds = lab.new_dataset()
    lab.load_fixtures(ds)
    lab.freeze(ds)
    assert [set(i) for i in lab.detector_input(ds)] == [{"id", "text"}] * 8
    assert [r["blind_id"] for r in lab.frozen_rows(ds)] == [i["id"] for i in lab.detector_input(ds)]
    dets = lab.illustrative_detections(ds)
    m = lab.matrix(ds, dets)
    assert set(m) == {(g, d) for g in lab.ROLES for d in lab.ROLES}
    assert all(c["eligible"] == 4 for c in m.values())
    assert "correct" in lab.cell_summary(m[("economy", "economy")])
    assert lab.cell_summary(None) == "_not run_"
    assert post.calls == []


def test_detect_sends_only_blind_ids_and_passages(post):
    ds = lab.new_dataset()
    lab.load_fixtures(ds)
    lab.freeze(ds)
    items = lab.detector_input(ds)
    post.push(FakeResponse(body=completion(det_answer(items))))
    out = lab.detect(FAKE_KEY, "economy", CFG["economy"]["id"], ds, CFG)
    sent = json.dumps(post.calls[0]["json"]["messages"])
    for r in ds["rows"]:
        assert r["row_id"] not in sent and r["generator_model"] not in sent
    assert "intended_label" not in sent and "economy" not in sent and lab.CORRECTION not in sent
    assert out["ok"] and all(v["status"] == "predicted" for v in out["results"].values())
    m = lab.matrix(ds, {"economy": out})
    assert m[("economy", "economy")]["tp"] == 2 and m[("economy", "economy")]["fp"] == 2
    assert m[("economy", "advanced")] is None


def test_detect_requires_freeze():
    with pytest.raises(ValueError):
        lab.detect(FAKE_KEY, "economy", "m", lab.new_dataset(), CFG)


def test_detector_http_error_is_failure_not_prediction(post):
    ds = lab.new_dataset()
    lab.load_fixtures(ds)
    lab.freeze(ds)
    post.push(FakeResponse(status=429, body={"error": {"message": "slow down", "code": 429}}))
    out = lab.detect(FAKE_KEY, "advanced", "m", ds, CFG)
    assert not out["ok"] and "429" in out["message"]
    m = lab.matrix(ds, {"advanced": out})[("economy", "advanced")]
    assert m["failures"] == 4 and m["answered"] == 0 and lab.fmt_rate(m["answered_accuracy"]) == "N/A"


def test_assess_pasted(post):
    post.push(FakeResponse(body=completion(det_answer([{"id": "X1"}], "supported"))))
    out = lab.assess_pasted(FAKE_KEY, "economy", "m", "Smoking harms health.", CFG)
    assert out["status"] == "predicted" and out["verdict"] == "supported" and out["scored"] is False
    post.push(FakeResponse(body=completion("not json")))
    out = lab.assess_pasted(FAKE_KEY, "economy", "m", "x", CFG)
    assert out["status"] == "failure"


def test_export_has_warning_and_no_key(post):
    ds = lab.new_dataset()
    lab.load_fixtures(ds)
    data = json.loads(lab.export_json(ds, calls=[{"note": "x"}]))
    assert data["exercise_warning"] == lab.EXERCISE_WARNING and data["correction"] == lab.CORRECTION
    assert len(data["dataset"]["rows"]) == 8 and "sk-or-" not in json.dumps(data)
