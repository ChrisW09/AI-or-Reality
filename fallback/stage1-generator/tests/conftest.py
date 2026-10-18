"""Shared test helpers. No test makes a real network call."""
import json
import sys
from pathlib import Path

import dotenv
import pytest
import requests

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import openrouter_client  # noqa: E402

FAKE_KEY = "sk-or-v1-TESTONLY0000000000000000000000000000000000000000000000000000"


class FakeResponse:
    def __init__(self, status=200, body=None, raw=None, chunks=None):
        self.status_code = status
        if raw is None:
            raw = json.dumps(body).encode() if body is not None else b""
        self._chunks = chunks if chunks is not None else [raw]

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def close(self):
        pass


def completion(content, finish="stop", model="m", cost=0.0001, **extra):
    body = {"id": "gen-test", "model": model, "provider": "TestProvider",
            "choices": [{"index": 0, "finish_reason": finish, "native_finish_reason": finish,
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost": cost}}
    body.update(extra)
    return body


class PostRecorder:
    """Replaces requests.post; returns queued responses and records every call."""

    def __init__(self):
        self.queue = []
        self.calls = []

    def push(self, resp):
        self.queue.append(resp)
        return self

    def __call__(self, url, headers=None, json=None, stream=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "stream": stream, "timeout": timeout})
        if not self.queue:
            raise AssertionError("Unexpected network call")
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Real network access attempted in a test")
    monkeypatch.setattr(requests, "post", forbidden)
    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(dotenv, "dotenv_values", lambda path: {})   # ignore a real .env next to app.py


@pytest.fixture
def post(monkeypatch):
    rec = PostRecorder()
    monkeypatch.setattr(openrouter_client.requests, "post", rec)
    return rec
