"""Detection logic: strict parsing, blinding, metrics and denominators."""
import json

import pytest

import detection as det
import generation as gen
from openrouter_client import CallResult


def ans(items):
    return json.dumps({"assessments": items})


def a(i, verdict="contradicted", ref="E1", reason="Because the packet says so."):
    return {"id": i, "verdict": verdict, "reason": reason, "evidence_ref": ref}


def rows(labels):
    return [{"row_id": f"r{i}", "intended_label": lab} for i, lab in enumerate(labels)]


def res(**kw):
    return {"status": "predicted", "reason": "x", "evidence_ref": "E1", **kw}


# ------------------------------------------------------------- parsing --
def test_parse_valid():
    preds, probs = det.parse_assessments(ans([a("P1"), a("P2", "supported")]), ["P1", "P2"])
    assert probs == [] and preds["P1"]["verdict"] == "contradicted" and preds["P2"]["verdict"] == "supported"


@pytest.mark.parametrize("content", ["nope", "[]", '{"assessments": {}}', '{"x": []}', ""])
def test_malformed_json_fails_all(content):
    preds, probs = det.parse_assessments(content, ["P1", "P2"])
    assert preds == {} and {p["problem"] for p in probs} == {"invalid_json"} and len(probs) == 2


def test_missing_duplicate_unknown_keep_valid():
    items = [a("P1"), a("P2"), a("P2", "supported"), a("P9"), "junk"]
    preds, probs = det.parse_assessments(ans(items), ["P1", "P2", "P3"])
    kinds = {(p["id"], p["problem"]) for p in probs}
    assert set(preds) == {"P1"}
    assert ("P2", "duplicate_id") in kinds and ("P3", "missing") in kinds and ("P9", "unknown_id") in kinds
    assert (None, "malformed_record") in kinds


@pytest.mark.parametrize("item,problem", [
    (a("P1", verdict="false"), "invalid_verdict"),
    (a("P1", verdict="0.83"), "invalid_verdict"),
    (a("P1", reason="  "), "missing_reason"),
    (a("P1", ref="E7"), "invalid_evidence_ref"),
    (a("P1", verdict="supported", ref="none"), "invalid_evidence_ref"),
])
def test_invalid_fields_are_failures(item, problem):
    preds, probs = det.parse_assessments(ans([item]), ["P1"])
    assert preds == {} and probs == [{"id": "P1", "problem": problem}]


def test_abstention_may_cite_none():
    preds, _ = det.parse_assessments(ans([a("P1", "insufficient_evidence", "none")]), ["P1"])
    assert preds["P1"]["verdict"] == "insufficient_evidence"


# ------------------------------------------------------------- metrics --
def test_confusion_counts_and_rates():
    rs = rows(["false", "false", "true", "true"])
    results = {"r0": res(verdict="contradicted"), "r1": res(verdict="supported"),
               "r2": res(verdict="contradicted"), "r3": res(verdict="supported")}
    m = det.cell_metrics(rs, results)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 1)
    assert m["overall_success"] == {"num": 2, "den": 4, "value": 0.5}
    assert m["false_claim_recall"]["value"] == 0.5 and m["false_positive_rate"]["value"] == 0.5
    assert m["coverage"]["value"] == 1.0 and m["balanced"]


def test_abstentions_and_failures_are_unsuccessful_not_negatives():
    rs = rows(["false", "false", "true", "true"])
    results = {"r0": res(verdict="contradicted"), "r1": {"status": "failure", "failure_kind": "format"},
               "r2": res(verdict="insufficient_evidence", evidence_ref="none")}   # r3 missing entirely
    m = det.cell_metrics(rs, results)
    assert m["tn"] == 0 and m["abst_true"] == 1 and m["abstentions"] == 1
    assert m["failures"] == 2 and m["fail_format"] == 1 and m["fail_service"] == 1
    assert m["overall_success"]["num"] == 1 and m["overall_success"]["den"] == 4
    assert m["answered_accuracy"] == {"num": 1, "den": 1, "value": 1.0}
    assert m["coverage"]["value"] == 0.25
    assert m["false_positive_rate"] == {"num": 0, "den": 2, "value": 0.0}


def test_zero_denominators_are_na():
    m = det.cell_metrics(rows(["false", "false"]), {"r0": res(verdict="contradicted"), "r1": res(verdict="contradicted")})
    assert m["false_positive_rate"]["value"] is None and det.fmt_rate(m["false_positive_rate"]) == "N/A"
    assert not m["balanced"]
    empty = det.cell_metrics([], {})
    for k in ("overall_success", "coverage", "false_claim_recall", "false_positive_rate", "answered_accuracy"):
        assert det.fmt_rate(empty[k]) == "N/A"
    m2 = det.cell_metrics(rows(["true"]), {"r0": res(verdict="insufficient_evidence", evidence_ref="none")})
    assert det.fmt_rate(m2["answered_accuracy"]) == "N/A"


def test_always_contradicted_baseline():
    rs = rows(["false", "false", "true", "true"])
    m = det.cell_metrics(rs, {r["row_id"]: res(verdict="contradicted") for r in rs})
    assert m["false_claim_recall"]["value"] == 1.0
    assert m["false_positive_rate"]["value"] == 1.0
    assert m["overall_success"]["value"] == 0.5


def test_one_item_moves_rates_by_25_and_50_points():
    rs = rows(["false", "false", "true", "true"])
    base = {r["row_id"]: res(verdict="contradicted" if r["intended_label"] == "false" else "supported") for r in rs}
    flipped = dict(base, r0=res(verdict="supported"))
    m0, m1 = det.cell_metrics(rs, base), det.cell_metrics(rs, flipped)
    assert m0["overall_success"]["value"] - m1["overall_success"]["value"] == pytest.approx(0.25)
    assert m0["false_claim_recall"]["value"] - m1["false_claim_recall"]["value"] == pytest.approx(0.5)


def test_is_correct():
    assert det.is_correct({"intended_label": "false"}, res(verdict="contradicted")) is True
    assert det.is_correct({"intended_label": "true"}, res(verdict="contradicted")) is False
    assert det.is_correct({"intended_label": "true"}, res(verdict="insufficient_evidence")) is None
    assert det.is_correct({"intended_label": "true"}, None) is None


# --------------------------------------------------- freezing & blinding --
def fixture_dataset():
    ds = gen.new_dataset()
    gen.add_rows(ds, gen.fixture_rows(gen.load_fixtures()), "fixture")
    return ds


def test_freeze_is_deterministic_and_blind():
    d1, d2 = fixture_dataset(), fixture_dataset()
    det.freeze(d1)
    det.freeze(d2)
    assert d1["frozen_order"] == d2["frozen_order"] and d1["blind_ids"] == d2["blind_ids"]
    assert d1["frozen_order"] != [r["row_id"] for r in d1["rows"]]      # shuffled, not row order
    for rid, b in d1["blind_ids"].items():
        assert rid not in b and "false" not in b.lower() and "true" not in b.lower()
    assert len(set(d1["blind_ids"].values())) == 8
    with pytest.raises(ValueError):
        gen.set_review(d1, d1["rows"][0]["row_id"], "excluded")      # frozen = locked


def test_freeze_requires_approved_rows_and_respects_cap():
    ds = fixture_dataset()
    for r in ds["rows"]:
        r["review_status"] = "awaiting_review"
    with pytest.raises(ValueError):
        det.freeze(ds)
    ds2 = fixture_dataset()
    with pytest.raises(ValueError):
        det.freeze(ds2, cap=7)
    ds3 = fixture_dataset()
    ds3["rows"][0]["review_status"] = "excluded"
    det.freeze(ds3)
    assert len(ds3["frozen_order"]) == 7 and ds3["rows"][0]["row_id"] not in ds3["frozen_order"]


def test_detector_messages_contain_no_metadata():
    ds = fixture_dataset()
    for r in ds["rows"]:
        r["generator_model"] = f"vendor/secret-model-{r['row_id']}"
    det.freeze(ds)
    items = det.frozen_items(ds)
    assert all(set(it) == {"id", "text"} for it in items)
    msgs = det.build_messages(items, structured=True)
    hits = det.leak_check(msgs, ds, [gen.CORRECTION, gen.EXERCISE_WARNING, gen.SYSTEM_PROMPT[:60],
                                     gen.WHO_URL, "FIXTURE", "intended"])
    assert hits == []
    text = json.dumps(msgs)
    for c in gen.CLAIMS.values():
        assert c["text"] not in text
    for e in det.EVIDENCE_PACKET["items"]:
        assert e["text"] in text


def test_leak_check_catches_injected_metadata():
    ds = fixture_dataset()
    det.freeze(ds)
    msgs = det.build_messages(det.frozen_items(ds), structured=True)
    msgs[1]["content"] += f"\n(generated by economy, row {ds['rows'][0]['row_id']})"
    assert det.leak_check(msgs, ds, []) != []


def test_build_messages_rejects_extra_fields():
    with pytest.raises(ValueError):
        det.build_messages([{"id": "P1", "text": "x", "intended_label": "false"}], structured=True)


def test_both_detectors_get_identical_input():
    ds = fixture_dataset()
    det.freeze(ds)
    assert det.build_messages(det.frozen_items(ds), True) == det.build_messages(det.frozen_items(ds), True)


def test_results_from_failed_call_are_service_failures():
    ds = fixture_dataset()
    det.freeze(ds)
    failed = CallResult(ok=False, model_requested="m", started_at_utc="t", elapsed_s=0, settings={}, messages=[],
                        status="rate_limit", message="slow down")
    out, _ = det.results_from_call(failed, ds)
    assert len(out) == 8 and all(v["status"] == "failure" and v["failure_kind"] == "service" for v in out.values())


def test_results_from_partial_call_keep_valid_rows():
    ds = fixture_dataset()
    det.freeze(ds)
    ids = [ds["blind_ids"][rid] for rid in ds["frozen_order"]]
    content = ans([a(i) for i in ids[:5]] + [{"id": ids[5], "verdict": "maybe", "reason": "x", "evidence_ref": "E1"}])
    ok = CallResult(ok=True, model_requested="m", started_at_utc="t", elapsed_s=0, settings={}, messages=[],
                    content=content)
    out, probs = det.results_from_call(ok, ds)
    assert sum(v["status"] == "predicted" for v in out.values()) == 5
    assert sum(v.get("failure_kind") == "format" for v in out.values()) == 3


def test_illustrative_fixture_verdicts_are_labelled_and_reference_fixtures():
    fx = gen.load_fixtures()
    assert "ILLUSTRATIVE" in fx["illustrative_verdicts_note"]
    ids = {e["row_id"] for e in fx["examples"]}
    for role in gen.ROLES:
        for v in fx["illustrative_verdicts"][role]:
            assert v["row_id"] in ids and v["verdict"] in det.VERDICTS


def test_extension_slots():
    assert len(gen.balanced_slots(1)) == 4 and len(gen.balanced_slots(3)) == 12
    assert len({s["slot_id"] for s in gen.balanced_slots(3)}) == 12
