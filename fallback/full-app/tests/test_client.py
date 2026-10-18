"""OpenRouter client: one request, finite timeouts, sanitized failures."""
import json

import pytest
import requests

import openrouter_client as orc
from conftest import FAKE_KEY, FakeResponse, completion

MSGS = [{"role": "user", "content": "hi"}]


def call(**kw):
    return orc.chat_completion(FAKE_KEY, "vendor/model-a", MSGS, max_tokens=50, temperature=0.2, seed=1, **kw)


def test_missing_key_makes_no_request(post):
    res = orc.chat_completion(None, "vendor/model-a", MSGS, max_tokens=10)
    assert not res.ok and res.status == "missing_key" and post.calls == []


def test_success_records_usage_cost_and_exact_request(post):
    post.push(FakeResponse(200, completion('{"x": 1}', model="vendor/model-a")))
    res = call(response_format={"type": "json_schema", "json_schema": {"name": "n", "schema": {}}})
    assert res.ok and res.content == '{"x": 1}' and res.cost_usd == pytest.approx(0.0001)
    assert res.provider == "TestProvider" and res.usage["completion_tokens"] == 50
    (sent,) = post.calls
    assert sent["url"] == orc.API_URL
    assert sent["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert sent["json"]["model"] == "vendor/model-a" and "models" not in sent["json"]
    assert sent["json"]["provider"] == {"require_parameters": True}
    assert sent["timeout"] == (orc.CONNECT_TIMEOUT_S, orc.READ_TIMEOUT_S)
    assert FAKE_KEY not in json.dumps(res.to_record())


def test_cost_missing_is_none(post):
    body = completion("hello")
    del body["usage"]["cost"]
    post.push(FakeResponse(200, body))
    res = call()
    assert res.ok and res.cost_usd is None


@pytest.mark.parametrize("status,kind", [(400, "bad_request"), (401, "auth"), (402, "credits"),
                                         (403, "forbidden"), (408, "timeout"), (429, "rate_limit"),
                                         (502, "provider"), (503, "provider")])
def test_http_errors_are_classified(post, status, kind):
    post.push(FakeResponse(status, {"error": {"code": status, "message": f"boom {FAKE_KEY}"}}))
    res = call()
    assert not res.ok and res.status == kind
    assert FAKE_KEY not in res.message and "[redacted]" in res.message
    assert len(post.calls) == 1  # no hidden retry


def test_refusal_error_type(post):
    post.push(FakeResponse(403, {"error": {"code": 403, "message": "no",
                                           "metadata": {"error_type": "refusal"}}}))
    assert call().status == "refused"


def test_200_with_error_body_is_failure(post):
    post.push(FakeResponse(200, {"id": "g", "error": {"code": 502, "message": "provider died"}}))
    res = call()
    assert not res.ok and res.status == "provider"


def test_choice_finish_error(post):
    body = completion("partial", finish="error")
    body["choices"][0]["error"] = {"code": 429, "message": "slow down", "metadata": {"error_type": "rate_limit_exceeded"}}
    post.push(FakeResponse(200, body))
    assert call().status == "rate_limit"


def test_message_refusal_field(post):
    body = completion(None, finish="content_filter")
    body["choices"][0]["message"]["refusal"] = "I can't help with that."
    post.push(FakeResponse(200, body))
    res = call()
    assert res.status == "refused" and "can't help" in res.message


@pytest.mark.parametrize("content,finish,kind", [("", "stop", "empty"), ("   ", "stop", "empty"),
                                                 ('{"examples": [', "length", "truncated")])
def test_empty_and_truncated(post, content, finish, kind):
    post.push(FakeResponse(200, completion(content, finish=finish)))
    assert call().status == kind


def test_non_json_body(post):
    post.push(FakeResponse(200, raw=b"<html>gateway</html>"))
    assert call().status == "invalid_response"


def test_read_timeout_and_network_error(post):
    post.push(requests.exceptions.ReadTimeout("slow"))
    assert call().status == "timeout"
    post.push(requests.exceptions.ConnectionError(f"dns failed {FAKE_KEY}"))
    res = call()
    assert res.status == "network" and FAKE_KEY not in res.message


def test_total_deadline_stops_slow_body(post):
    def slow_chunks():
        import time
        for _ in range(50):
            time.sleep(0.05)
            yield b" "
    post.push(FakeResponse(200, chunks=slow_chunks()))
    res = call(total_deadline_s=0.2)
    assert res.status == "timeout" and res.elapsed_s < 2


def test_sanitize_removes_keys():
    assert "sk-or" not in orc.sanitize("token sk-or-v1-abcdefabcdefabcdef leaked")


def test_provider_routing_is_same_model_and_explicit(post):
    post.push(FakeResponse(200, completion("ok")))
    call(response_format={"type": "json_schema", "json_schema": {"name": "n", "schema": {}}},
         provider={"order": ["mistral/eu"], "allow_fallbacks": False})
    sent = post.calls[0]["json"]
    assert sent["provider"] == {"order": ["mistral/eu"], "allow_fallbacks": False, "require_parameters": True}
    assert sent["model"] == "vendor/model-a" and "models" not in sent
