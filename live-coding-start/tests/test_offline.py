"""Offline tests for the classroom misinformation generator.

Run from the project directory:

    python3 -m unittest discover -s tests -v

No test makes a real network call: every HTTP request goes to a fake session
or to a patched ``generator.requests.post``. No test reads ``.env``.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from unittest import mock

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import requests  # noqa: E402

import generator  # noqa: E402

MODELS_PATH = os.path.join(PROJECT_DIR, "models.json")
FIXTURES_PATH = os.path.join(PROJECT_DIR, "fixtures", "offline_fixtures.json")
APP_PATH = os.path.join(PROJECT_DIR, "app.py")

FAKE_KEY = "sk-or-v1-TEST-ONLY-NOT-A-REAL-KEY-0123456789"
KEY_ENV = "OPENROUTER_API_KEY"


def _env_without_key():
    """Copy of os.environ with the API key removed."""
    env = dict(os.environ)
    env.pop(KEY_ENV, None)
    return env


# ---------------------------------------------------------------------------
# Fake HTTP
# ---------------------------------------------------------------------------

class FakeResponse(object):
    def __init__(self, status_code=200, payload=None, text=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        if text is not None:
            self.text = text
        elif payload is not None:
            self.text = json.dumps(payload)
        else:
            self.text = ""
        self.headers = {"Content-Type": "application/json"}
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._json_error:
            raise requests.exceptions.JSONDecodeError("Expecting value", self.text, 0)
        return self._payload


class FakeSession(object):
    """Records every post() call; returns a fixed response or raises."""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        return self.response


def _ok_payload(content, finish_reason="stop", usage=None):
    payload = {
        "id": "gen-test",
        "model": "mistralai/ministral-8b-2512",
        "provider": "Mistral",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if usage is not None:
        payload["usage"] = usage
    return payload


def _valid_records():
    return {
        "records": [
            {"slot_id": "S1", "claim_id": "CLAIM_SUPPORTED", "format": "social_post",
             "passage": "Smoking hurts your lungs and your heart. Quitting is one of the best things you can do."},
            {"slot_id": "S2", "claim_id": "CLAIM_SUPPORTED", "format": "scientific_prose",
             "passage": "Tobacco smoke damages the airways and blood vessels, and long-term smoking is linked to lung cancer and heart disease."},
            {"slot_id": "S3", "claim_id": "CLAIM_CONTRADICTED", "format": "social_post",
             "passage": "Cigarettes are healthy! Light one up and feel great every morning."},
            {"slot_id": "S4", "claim_id": "CLAIM_CONTRADICTED", "format": "scientific_prose",
             "passage": "Regular cigarette use is described here as beneficial for overall health and as a way to strengthen the lungs."},
        ]
    }


def _call(session, **overrides):
    kwargs = dict(
        api_key=FAKE_KEY,
        model_id="mistralai/ministral-8b-2512",
        messages=generator.build_messages(generator.ASSIGNMENTS),
        max_tokens=generator.MAX_TOKENS_BATCH,
        temperature=0.7,
        provider_routing={"order": ["mistral/eu"], "allow_fallbacks": False},
        session=session,
    )
    kwargs.update(overrides)
    return generator.call_openrouter(**kwargs)


# ---------------------------------------------------------------------------
# load_models / get_api_key
# ---------------------------------------------------------------------------

class TestLoadModels(unittest.TestCase):
    def test_reads_ids_and_routing(self):
        with open(MODELS_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        result = generator.load_models(MODELS_PATH)
        self.assertTrue(result["preflight_complete"])
        self.assertEqual(result["economy_id"], raw["economy"]["id"])
        self.assertEqual(result["advanced_id"], raw["advanced"]["id"])
        self.assertEqual(
            result["provider_routing"],
            {"order": raw["provider_routing"]["order"],
             "allow_fallbacks": raw["provider_routing"]["allow_fallbacks"]},
        )
        # Only order/allow_fallbacks are forwarded, never the documentation keys.
        self.assertEqual(set(result["provider_routing"].keys()), {"order", "allow_fallbacks"})

    def test_missing_file_is_preflight_incomplete(self):
        missing = os.path.join(tempfile.gettempdir(), "does-not-exist-models-xyz.json")
        result = generator.load_models(missing)
        self.assertFalse(result["preflight_complete"])
        self.assertIsNone(result["economy_id"])
        self.assertIsNone(result["advanced_id"])
        self.assertIn("Preflight incomplete", result["message"])

    def test_missing_ids_is_preflight_incomplete(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "models.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"economy": {"display_name": "x"}}, fh)
            result = generator.load_models(path)
            self.assertFalse(result["preflight_complete"])
            self.assertIn("Preflight incomplete", result["message"])
        finally:
            shutil.rmtree(tmpdir)


class RaisingSecrets(object):
    """Behaves like st.secrets when no secrets.toml exists."""

    def __getitem__(self, key):
        raise FileNotFoundError("No secrets file found")

    def get(self, key, default=None):
        raise FileNotFoundError("No secrets file found")

    def __contains__(self, key):
        raise FileNotFoundError("No secrets file found")

    def __getattr__(self, name):
        raise FileNotFoundError("No secrets file found")


class TestGetApiKey(unittest.TestCase):
    def test_from_env_dict_is_stripped(self):
        self.assertEqual(generator.get_api_key(env={KEY_ENV: "  " + FAKE_KEY + "\n"}), FAKE_KEY)

    def test_from_secrets_mapping(self):
        with mock.patch.dict(os.environ, _env_without_key(), clear=True):
            self.assertEqual(
                generator.get_api_key(env={}, secrets={KEY_ENV: FAKE_KEY}), FAKE_KEY
            )

    def test_raising_secrets_returns_none(self):
        with mock.patch.dict(os.environ, _env_without_key(), clear=True):
            self.assertIsNone(generator.get_api_key(env={}, secrets=RaisingSecrets()))

    def test_nothing_found_returns_none(self):
        with mock.patch.dict(os.environ, _env_without_key(), clear=True):
            self.assertIsNone(generator.get_api_key(env={}, secrets=None))


# ---------------------------------------------------------------------------
# Fixtures and rows
# ---------------------------------------------------------------------------

class TestFixtures(unittest.TestCase):
    def setUp(self):
        self.rows = generator.load_fixtures(FIXTURES_PATH)

    def test_eight_balanced_rows(self):
        self.assertEqual(len(self.rows), 8)
        pairs = Counter(
            (r["generator"]["model_role"], r["label"]["slot_id"]) for r in self.rows
        )
        expected = {(role, a["slot_id"]) for role in ("economy", "advanced")
                    for a in generator.ASSIGNMENTS}
        self.assertEqual(set(pairs.keys()), expected)
        self.assertTrue(all(n == 1 for n in pairs.values()))
        # Balanced claims: each role has 2 supported and 2 contradicted.
        for role in ("economy", "advanced"):
            stances = Counter(r["label"]["stance"] for r in self.rows
                              if r["generator"]["model_role"] == role)
            self.assertEqual(stances, Counter({"supported": 2, "contradicted": 2}))

    def test_all_offline_fixture_not_awaiting_review(self):
        for r in self.rows:
            self.assertEqual(r["generator"]["source"], "offline_fixture")
            self.assertIsNone(r["generator"]["model_id"])
            self.assertNotEqual(r["review_status"], "awaiting_instructor_review")
            self.assertEqual(r["review_status"], "offline_fixture_not_a_measurement")

    def test_passage_separate_from_wrapper_correction_label(self):
        for r in self.rows:
            passage = r["passage"]
            self.assertIsInstance(passage, str)
            self.assertTrue(passage.strip())
            self.assertEqual(generator.passage_only(r), passage)
            self.assertEqual(r["correction"]["text"], generator.CORRECTION_TEXT)
            self.assertEqual(r["correction"]["url"], generator.WHO_URL)
            self.assertEqual(r["exercise_wrapper"]["warning"], generator.EXERCISE_WARNING)
            self.assertNotIn(generator.EXERCISE_WARNING, passage)
            self.assertNotIn(generator.CORRECTION_TEXT, passage)
            self.assertNotIn(generator.WHO_URL, passage)
            self.assertNotIn(r["label"]["claim_id"], passage)
            self.assertIn(r["label"]["claim_id"], generator.CLAIMS)

    def test_fixtures_pass_validation(self):
        for role in ("economy", "advanced"):
            records = [
                {"slot_id": r["label"]["slot_id"], "claim_id": r["label"]["claim_id"],
                 "format": r["label"]["format"], "passage": r["passage"]}
                for r in self.rows if r["generator"]["model_role"] == role
            ]
            accepted, rejected = generator.parse_and_validate(
                json.dumps({"records": records}), generator.ASSIGNMENTS
            )
            self.assertEqual(rejected, [], "fixture rejected for role %s" % role)
            self.assertEqual(len(accepted), 4)

    def test_unbalanced_fixture_file_raises(self):
        with open(FIXTURES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["fixtures"] = data["fixtures"][:-1]
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "fixtures.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            with self.assertRaises(ValueError):
                generator.load_fixtures(path)
        finally:
            shutil.rmtree(tmpdir)


# ---------------------------------------------------------------------------
# call_openrouter (fake HTTP only)
# ---------------------------------------------------------------------------

class TestCallOpenRouterRequest(unittest.TestCase):
    def test_request_body_and_single_post(self):
        content = json.dumps(_valid_records())
        session = FakeSession(FakeResponse(200, _ok_payload(content)))
        routing = {"order": ["mistral/eu"], "allow_fallbacks": False}
        _call(session, provider_routing=routing)

        self.assertEqual(len(session.calls), 1)
        args, kwargs = session.calls[0]
        url = args[0] if args else kwargs.get("url")
        self.assertEqual(url, generator.OPENROUTER_URL)

        body = kwargs["json"]
        self.assertEqual(body["model"], "mistralai/ministral-8b-2512")
        self.assertEqual(body["provider"], routing)
        self.assertNotIn("models", body)
        self.assertNotIn("route", body)
        self.assertEqual(body["max_tokens"], generator.MAX_TOKENS_BATCH)
        self.assertEqual(body["response_format"], generator.response_format_schema())

        timeout = kwargs.get("timeout")
        self.assertIsNotNone(timeout)
        parts = timeout if isinstance(timeout, (tuple, list)) else (timeout,)
        for p in parts:
            self.assertTrue(isinstance(p, (int, float)) and math.isfinite(p) and p > 0)

        headers = kwargs.get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer " + FAKE_KEY)

    def test_no_provider_key_when_routing_none(self):
        session = FakeSession(FakeResponse(200, _ok_payload(json.dumps(_valid_records()))))
        _call(session, provider_routing=None)
        self.assertNotIn("provider", session.calls[0][1]["json"])
        self.assertNotIn("models", session.calls[0][1]["json"])

    def test_patched_requests_post_called_once(self):
        resp = FakeResponse(200, _ok_payload(json.dumps(_valid_records())))
        with mock.patch.object(generator.requests, "post", return_value=resp) as post:
            result = _call(None)
        self.assertEqual(post.call_count, 1)
        self.assertTrue(result["ok"])


class TestCallOpenRouterResponses(unittest.TestCase):
    def test_success_parses_usage_and_cost(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
                 "cost": 0.000123}
        content = json.dumps(_valid_records())
        session = FakeSession(FakeResponse(200, _ok_payload(content, usage=usage)))
        result = _call(session)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["content"], content)
        self.assertEqual(result["finish_reason"], "stop")
        self.assertEqual(result["usage"]["total_tokens"], 150)
        self.assertAlmostEqual(result["cost_usd"], 0.000123)
        self.assertEqual(result["provider"], "Mistral")
        self.assertEqual(result["response_model"], "mistralai/ministral-8b-2512")
        self.assertEqual(result["http_status"], 200)

    def test_cost_none_when_absent(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        session = FakeSession(FakeResponse(200, _ok_payload("{}", usage=usage)))
        result = _call(session)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["cost_usd"])

    def test_cost_none_when_usage_missing(self):
        session = FakeSession(FakeResponse(200, _ok_payload("{}")))
        result = _call(session)
        self.assertIsNone(result["cost_usd"])

    def _assert_error(self, result, *needles):
        self.assertFalse(result["ok"])
        self.assertIsInstance(result["error"], str)
        self.assertTrue(result["error"].strip())
        self.assertNotIn(FAKE_KEY, result["error"])
        self.assertNotIn("Bearer", result["error"])
        low = result["error"].lower()
        self.assertTrue(any(n.lower() in low for n in needles),
                        "error %r lacks any of %r" % (result["error"], needles))

    def _error_body(self, msg):
        return {"error": {"message": msg, "code": 0}}

    def test_401_invalid_credentials(self):
        # The provider echoes the key back; it must be redacted.
        body = self._error_body("No auth credentials found for key " + FAKE_KEY)
        session = FakeSession(FakeResponse(401, body))
        result = _call(session)
        self._assert_error(result, "credential", "api key", "unauthor", "invalid")
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(len(session.calls), 1)

    def test_402_insufficient_credits(self):
        session = FakeSession(FakeResponse(402, self._error_body("Insufficient credits")))
        result = _call(session)
        self._assert_error(result, "credit")
        self.assertEqual(len(session.calls), 1)

    def test_429_rate_limited_no_retry(self):
        body = self._error_body("temporarily rate-limited upstream " + FAKE_KEY)
        session = FakeSession(FakeResponse(429, body))
        result = _call(session)
        self._assert_error(result, "rate")
        self.assertIn("retry", result["error"].lower())
        self.assertEqual(len(session.calls), 1, "429 must not trigger a retry")

    def test_500_provider_error(self):
        session = FakeSession(FakeResponse(500, self._error_body("Internal error")))
        result = _call(session)
        self._assert_error(result, "provider", "server")
        self.assertEqual(len(session.calls), 1)

    def test_timeout(self):
        session = FakeSession(exc=requests.Timeout("read timed out " + FAKE_KEY))
        result = _call(session)
        self._assert_error(result, "timed out", "timeout")
        self.assertEqual(len(session.calls), 1)

    def test_connection_error(self):
        session = FakeSession(exc=requests.ConnectionError("conn refused"))
        result = _call(session)
        self._assert_error(result, "network", "connect")

    def test_empty_content(self):
        session = FakeSession(FakeResponse(200, _ok_payload("")))
        result = _call(session)
        self._assert_error(result, "empty")

    def test_no_choices(self):
        session = FakeSession(FakeResponse(200, {"id": "x", "choices": []}))
        result = _call(session)
        self._assert_error(result, "empty")

    def test_finish_reason_length(self):
        content = json.dumps(_valid_records())[:40]
        session = FakeSession(FakeResponse(200, _ok_payload(content, finish_reason="length")))
        result = _call(session)
        self._assert_error(result, "truncat", "max_tokens")

    def test_non_json_body(self):
        session = FakeSession(FakeResponse(200, text="<html>Bad gateway</html>", json_error=True))
        result = _call(session)
        self.assertFalse(result["ok"])
        self.assertIsInstance(result["error"], str)
        self.assertNotIn(FAKE_KEY, result["error"])

    def test_non_json_error_body(self):
        session = FakeSession(FakeResponse(502, text="<html>Bad gateway</html>", json_error=True))
        result = _call(session)
        self._assert_error(result, "provider", "server", "gateway")

    def test_missing_key_makes_no_request(self):
        session = FakeSession(FakeResponse(200, _ok_payload("{}")))
        result = _call(session, api_key="")
        self._assert_error(result, "no api key")
        self.assertEqual(len(session.calls), 0)

    def test_key_never_in_any_result_field(self):
        cases = [
            FakeSession(FakeResponse(401, self._error_body(FAKE_KEY))),
            FakeSession(FakeResponse(400, self._error_body("bad request " + FAKE_KEY))),
            FakeSession(FakeResponse(429, self._error_body(FAKE_KEY))),
            FakeSession(exc=requests.Timeout(FAKE_KEY)),
        ]
        for session in cases:
            result = _call(session)
            self.assertNotIn(FAKE_KEY, json.dumps(result, default=str))


# ---------------------------------------------------------------------------
# parse_and_validate
# ---------------------------------------------------------------------------

class TestParseAndValidate(unittest.TestCase):
    def _run(self, data):
        content = data if isinstance(data, str) else json.dumps(data)
        return generator.parse_and_validate(content, generator.ASSIGNMENTS)

    def _rejected_slots(self, rejected):
        return {r.get("slot_id") for r in rejected}

    def test_accepts_valid_batch(self):
        accepted, rejected = self._run(_valid_records())
        self.assertEqual(rejected, [])
        self.assertEqual([a["slot_id"] for a in accepted], ["S1", "S2", "S3", "S4"])
        for a in accepted:
            self.assertEqual(set(a.keys()), {"slot_id", "claim_id", "format", "passage"})

    def test_accepts_code_fences(self):
        content = "```json\n" + json.dumps(_valid_records()) + "\n```"
        accepted, rejected = self._run(content)
        self.assertEqual(len(accepted), 4)
        self.assertEqual(rejected, [])

    def test_rejects_invalid_json(self):
        accepted, rejected = self._run('{"records": [ {"slot_id": "S1", ')
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("invalid json", rejected[0]["reason"].lower())

    def test_rejects_changed_claim(self):
        data = _valid_records()
        data["records"][0]["claim_id"] = "CLAIM_CONTRADICTED"
        accepted, rejected = self._run(data)
        self.assertIn("S1", self._rejected_slots(rejected))
        self.assertNotIn("S1", [a["slot_id"] for a in accepted])
        reason = [r for r in rejected if r.get("slot_id") == "S1"][0]["reason"]
        self.assertIn("claim", reason.lower())
        self.assertEqual(len(accepted), 3)

    def test_rejects_changed_format(self):
        data = _valid_records()
        data["records"][2]["format"] = "scientific_prose"
        accepted, rejected = self._run(data)
        self.assertIn("S3", self._rejected_slots(rejected))
        self.assertEqual(len(accepted), 3)

    def test_rejects_missing_slot(self):
        data = _valid_records()
        data["records"] = data["records"][:3]
        accepted, rejected = self._run(data)
        self.assertIn("S4", self._rejected_slots(rejected))
        self.assertEqual([a["slot_id"] for a in accepted], ["S1", "S2", "S3"])

    def test_rejects_refusal(self):
        data = _valid_records()
        data["records"][2]["passage"] = "I'm sorry, but I can't help create health misinformation."
        accepted, rejected = self._run(data)
        self.assertIn("S3", self._rejected_slots(rejected))
        self.assertNotIn("S3", [a["slot_id"] for a in accepted])

    def test_rejects_doi(self):
        data = _valid_records()
        data["records"][3]["passage"] = "Cigarettes are healthy, see 10.1234/abcd.5678 for details."
        accepted, rejected = self._run(data)
        self.assertIn("S4", self._rejected_slots(rejected))

    def test_rejects_percentage(self):
        data = _valid_records()
        data["records"][1]["passage"] = "Smoking raises the risk of lung disease by 25% in adults."
        accepted, rejected = self._run(data)
        self.assertIn("S2", self._rejected_slots(rejected))

    def test_rejects_over_length(self):
        data = _valid_records()
        limit = generator.FORMATS["social_post"]["max_words"]
        data["records"][0]["passage"] = " ".join(["smoke"] * (limit + 1))
        accepted, rejected = self._run(data)
        self.assertIn("S1", self._rejected_slots(rejected))

    def test_rejects_empty_passage(self):
        data = _valid_records()
        data["records"][0]["passage"] = "   "
        accepted, rejected = self._run(data)
        self.assertIn("S1", self._rejected_slots(rejected))


# ---------------------------------------------------------------------------
# comparison_rows / build_export
# ---------------------------------------------------------------------------

def _live_row(role, assignment, passage="Smoking harms health."):
    return generator.make_row(
        passage, assignment, source="live", model_role=role,
        model_id="mistralai/ministral-8b-2512", settings={"temperature": 0.7},
        batch_id="BTEST", generated_at_utc="2026-10-18T00:00:00Z",
        usage={"total_tokens": 10}, cost_usd=0.0001, provider="Mistral",
    )


class TestComparisonAndExport(unittest.TestCase):
    def setUp(self):
        self.fixture_rows = generator.load_fixtures(FIXTURES_PATH)
        self.live_rows = [_live_row(role, a) for role in ("economy", "advanced")
                          for a in generator.ASSIGNMENTS]

    def test_live_row_review_status(self):
        for r in self.live_rows:
            self.assertEqual(r["review_status"], "awaiting_instructor_review")
            self.assertEqual(r["generator"]["source"], "live")

    def test_live_only(self):
        rows, err = generator.comparison_rows(self.live_rows)
        self.assertIsNone(err)
        self.assertEqual(len(rows), 8)

    def test_rejects_mixing(self):
        rows, err = generator.comparison_rows(self.live_rows + self.fixture_rows[:1])
        self.assertEqual(rows, [])
        self.assertIsInstance(err, str)
        self.assertIn("mix", err.lower())

    def test_fixtures_only(self):
        rows, err = generator.comparison_rows(self.fixture_rows)
        self.assertEqual(rows, [])
        self.assertIsInstance(err, str)

    def test_build_export_has_context_and_no_key(self):
        models_info = generator.load_models(MODELS_PATH)
        env = _env_without_key()
        env[KEY_ENV] = FAKE_KEY
        with mock.patch.dict(os.environ, env, clear=True):
            export = generator.build_export(self.fixture_rows, models_info)
        ctx = export["exercise_context"]
        self.assertEqual(ctx["warning"], generator.EXERCISE_WARNING)
        self.assertEqual(ctx["correction"]["text"], generator.CORRECTION_TEXT)
        self.assertEqual(ctx["correction"]["url"], generator.WHO_URL)
        self.assertIn("notice", ctx)
        self.assertIn("exported_at_utc", ctx)
        self.assertEqual(len(export["rows"]), 8)
        self.assertEqual(export["models"]["economy_id"], models_info["economy_id"])
        dumped = json.dumps(export)
        self.assertNotIn(FAKE_KEY, dumped)
        self.assertNotIn("sk-or-v1", dumped)
        self.assertNotIn("Bearer", dumped)

    def test_build_export_without_models(self):
        export = generator.build_export(self.fixture_rows)
        self.assertIn("exercise_context", export)
        self.assertIsNone(export.get("models"))


# ---------------------------------------------------------------------------
# Streamlit startup (AppTest, no network)
# ---------------------------------------------------------------------------

def _collect_texts(at):
    """Gather text from rendered elements that may carry the WHO link."""
    texts = []
    for attr in ("markdown", "error", "warning", "info", "success", "caption",
                 "code", "text", "title", "header", "subheader", "json", "exception"):
        try:
            elements = getattr(at, attr)
        except Exception:
            continue
        for el in elements:
            for field in ("value", "body", "message"):
                val = getattr(el, field, None)
                if val is not None:
                    texts.append(str(val))
                    break
    try:
        for el in at.get("link_button"):
            texts.append(str(getattr(el, "proto", el)))
    except Exception:
        pass
    return texts


@unittest.skipUnless(os.path.exists(APP_PATH), "app.py not present yet")
class TestAppStartup(unittest.TestCase):
    def test_app_starts_offline_with_who_link(self):
        from streamlit.testing.v1 import AppTest

        old_cwd = os.getcwd()
        os.chdir(PROJECT_DIR)
        try:
            with mock.patch.dict(os.environ, _env_without_key(), clear=True), \
                    mock.patch.object(generator.requests, "post",
                                      side_effect=AssertionError("network call at startup")), \
                    mock.patch.object(requests.Session, "post",
                                      side_effect=AssertionError("network call at startup")):
                at = AppTest.from_file(APP_PATH, default_timeout=30)
                at.run()
        finally:
            os.chdir(old_cwd)

        self.assertEqual(len(at.exception), 0,
                         "app raised: %s" % [e.value for e in at.exception])
        texts = _collect_texts(at)
        self.assertTrue(any(generator.WHO_URL in t for t in texts),
                        "WHO URL not found in rendered output")
        joined = "\n".join(texts)
        self.assertNotIn(FAKE_KEY, joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
