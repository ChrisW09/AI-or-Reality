"""Minimal OpenRouter chat-completions client for the classroom app.

One function, `chat_completion`, makes exactly one HTTP request. It never
retries, never substitutes another model and never raises for API problems:
every outcome comes back as a `CallResult` with a sanitized message.

Timeouts: `requests` applies its read timeout to each socket read, not to the
whole response. We therefore stream the body and also check a total deadline
between chunks. Worst case, a call ends after TOTAL_DEADLINE_S plus one
READ_TIMEOUT_S of silence.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
CONNECT_TIMEOUT_S = 5
READ_TIMEOUT_S = 20
TOTAL_DEADLINE_S = 60
APP_TITLE = "Classroom misinformation lab"

# Failure categories shown to the instructor. "ok" is the only success.
ERROR_LABELS = {
    "missing_key": "No API key found (OPENROUTER_API_KEY). Use offline mode or add the key.",
    "auth": "Invalid or disabled API key (HTTP 401).",
    "credits": "Insufficient credits on the OpenRouter account or key (HTTP 402).",
    "forbidden": "Request blocked (HTTP 403): key budget, permission, moderation or guardrail.",
    "refused": "The model or a content filter declined the request.",
    "rate_limit": "Rate limited (HTTP 429). Wait, then use the explicit retry button.",
    "timeout": "No complete answer within the time limit.",
    "provider": "Model provider error or no provider available (HTTP 5xx or error body).",
    "bad_request": "The request was rejected as invalid (HTTP 400/404/413/422).",
    "network": "Network error: OpenRouter could not be reached.",
    "invalid_response": "OpenRouter returned a response that is not valid JSON.",
    "empty": "The model returned no text.",
    "truncated": "The answer hit the output limit and is incomplete.",
    "http_error": "Unexpected HTTP status.",
}

_KEY_PATTERN = re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sanitize(text: Any, secret: str | None = None, limit: int = 300) -> str:
    """Remove anything that looks like a key and shorten the message."""
    s = str(text) if text is not None else ""
    if secret:
        s = s.replace(secret, "[redacted]")
    s = _KEY_PATTERN.sub("[redacted]", s)
    s = " ".join(s.split())
    return s[:limit]


@dataclass
class CallResult:
    ok: bool
    model_requested: str
    started_at_utc: str
    elapsed_s: float
    settings: dict
    messages: list
    status: str = "ok"            # "ok" or a key of ERROR_LABELS
    message: str = ""             # sanitized, human-readable
    http_status: int | None = None
    content: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    model_returned: str | None = None
    provider: str | None = None
    generation_id: str | None = None
    usage: dict | None = None
    cost_usd: float | None = None
    extra: dict = field(default_factory=dict)

    def to_record(self) -> dict:
        return asdict(self)


class _TotalDeadline(Exception):
    pass


def _classify_http(status: int, error_type: str | None) -> str:
    if error_type in ("refusal", "content_policy_violation"):
        return "refused"
    if error_type == "rate_limit_exceeded":
        return "rate_limit"
    if error_type == "payment_required":
        return "credits"
    if error_type == "authentication":
        return "auth"
    if error_type == "timeout":
        return "timeout"
    if status == 401:
        return "auth"
    if status == 402:
        return "credits"
    if status == 403:
        return "forbidden"
    if status == 408:
        return "timeout"
    if status == 429:
        return "rate_limit"
    if status in (400, 404, 413, 422):
        return "bad_request"
    if status >= 500:
        return "provider"
    return "http_error"


def _read_body(resp: requests.Response, deadline: float) -> bytes:
    chunks = []
    for chunk in resp.iter_content(chunk_size=8192):
        if chunk:
            chunks.append(chunk)
        if time.monotonic() > deadline:
            raise _TotalDeadline()
    return b"".join(chunks)


def chat_completion(
    api_key: str | None,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float | None = None,
    seed: int | None = None,
    response_format: dict | None = None,
    provider: dict | None = None,
    total_deadline_s: float = TOTAL_DEADLINE_S,
) -> CallResult:
    """Make exactly one chat-completions request. Never raises for API errors.

    `provider` is OpenRouter provider routing for the SAME model (for example an
    endpoint order with allow_fallbacks=False). It never names another model.
    """
    routing = dict(provider or {})
    if response_format:
        # Only route to endpoints that honour response_format.
        routing["require_parameters"] = True
    settings = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "seed": seed,
        "structured_output": bool(response_format),
        "provider_routing": routing or "OpenRouter default",
        "connect_timeout_s": CONNECT_TIMEOUT_S,
        "read_timeout_s": READ_TIMEOUT_S,
        "total_deadline_s": total_deadline_s,
        "retries": 0,
        "model_fallbacks": "none",
    }
    started = now_utc()
    t0 = time.monotonic()

    def result(**kw) -> CallResult:
        return CallResult(model_requested=model, started_at_utc=started,
                          elapsed_s=round(time.monotonic() - t0, 2),
                          settings=settings, messages=messages, **kw)

    if not api_key:
        return result(ok=False, status="missing_key", message=ERROR_LABELS["missing_key"])
    if not model or not model.strip():
        return result(ok=False, status="bad_request", message="No model ID entered.")

    body: dict[str, Any] = {"model": model.strip(), "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if response_format:
        body["response_format"] = response_format
    if routing:
        body["provider"] = routing

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "X-OpenRouter-Title": APP_TITLE}
    deadline = time.monotonic() + total_deadline_s
    try:
        resp = requests.post(API_URL, headers=headers, json=body, stream=True,
                             timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
        try:
            raw = _read_body(resp, deadline)
        finally:
            resp.close()
    except _TotalDeadline:
        return result(ok=False, status="timeout",
                      message=f"Stopped waiting after {total_deadline_s:.0f} s (total deadline).")
    except requests.exceptions.Timeout:
        return result(ok=False, status="timeout",
                      message=f"No data for {READ_TIMEOUT_S} s or no connection within {CONNECT_TIMEOUT_S} s.")
    except requests.exceptions.RequestException as exc:
        return result(ok=False, status="network",
                      message=sanitize(f"{ERROR_LABELS['network']} ({type(exc).__name__})", api_key))

    status_code = resp.status_code
    try:
        data = json.loads(raw.decode("utf-8", errors="replace") or "null")
    except ValueError:
        data = None

    if not isinstance(data, dict):
        kind = "invalid_response" if status_code == 200 else _classify_http(status_code, None)
        return result(ok=False, status=kind, http_status=status_code,
                      message=ERROR_LABELS[kind])

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    cost = usage.get("cost") if usage else None
    common = dict(http_status=status_code, model_returned=data.get("model"),
                  provider=data.get("provider"), generation_id=data.get("id"), usage=usage,
                  cost_usd=float(cost) if isinstance(cost, (int, float)) else None)

    err = data.get("error") if isinstance(data.get("error"), dict) else None
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    if status_code != 200 or (err and not choices):
        meta = (err or {}).get("metadata") or {}
        error_type = meta.get("error_type") if isinstance(meta, dict) else None
        kind = _classify_http(status_code if status_code != 200 else 502, error_type)
        detail = sanitize((err or {}).get("message", ""), api_key)
        return result(ok=False, status=kind, message=f"{ERROR_LABELS[kind]} {detail}".strip(), **common)

    if not choices or not isinstance(choices[0], dict):
        return result(ok=False, status="invalid_response", message="Response has no choices.", **common)

    choice = choices[0]
    msg = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = msg.get("content") if isinstance(msg.get("content"), str) else None
    finish = choice.get("finish_reason")
    native = choice.get("native_finish_reason")
    common.update(content=content, finish_reason=finish, native_finish_reason=native)

    if finish == "error":
        cerr = choice.get("error") if isinstance(choice.get("error"), dict) else {}
        meta = cerr.get("metadata") or {}
        kind = _classify_http(int(cerr.get("code") or 502), meta.get("error_type") if isinstance(meta, dict) else None)
        return result(ok=False, status=kind,
                      message=f"{ERROR_LABELS[kind]} {sanitize(cerr.get('message', ''), api_key)}".strip(), **common)
    if msg.get("refusal") or finish == "content_filter":
        return result(ok=False, status="refused",
                      message=f"{ERROR_LABELS['refused']} {sanitize(msg.get('refusal') or '', api_key)}".strip(),
                      **common)
    if not content or not content.strip():
        return result(ok=False, status="empty", message=ERROR_LABELS["empty"], **common)
    if finish == "length":
        return result(ok=False, status="truncated", message=ERROR_LABELS["truncated"], **common)
    return result(ok=True, status="ok", message="OK", **common)


def list_models(api_key: str | None = None) -> tuple[dict | None, str]:
    """GET the public model list (free). Returns ({id: supported_parameters}, message)."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        resp = requests.get(MODELS_URL, headers=headers, timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
        data = resp.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        return None, sanitize(f"Model list unavailable ({type(exc).__name__}).", api_key)
    if resp.status_code != 200 or not isinstance(data, dict):
        return None, f"Model list unavailable (HTTP {resp.status_code})."
    models = {m.get("id"): m.get("supported_parameters", []) for m in data.get("data", [])
              if isinstance(m, dict)}
    return models, f"{len(models)} models listed at {now_utc()}."
