"""Offline smoke test for app.py (no network, no key, no cost). Run: python smoke_test.py

It starts the app with Streamlit's AppTest, then clicks every enabled button once
(including those in other tabs), rerunning after each click. It fails if:
  - the app raises an exception at any point,
  - the exercise warning, the correction or the WHO link is missing,
  - any HTTP request is attempted (with no key and offline mode, none should be),
  - the offline fixtures cannot be loaded from a button,
  - one of the required buttons (REQUIRED_BUTTONS) is missing or relabelled.
It prints what it clicked. It does not check layout, wording or live calls.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import logging
import requests
from streamlit.testing.v1 import AppTest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)
os.environ.pop("OPENROUTER_API_KEY", None)

import lab  # noqa: E402

ATTEMPTS: list[str] = []


class BlockedRequest(requests.exceptions.ConnectionError):
    pass


def _blocked(url, *a, **k):
    ATTEMPTS.append(str(url))
    raise BlockedRequest("network blocked by smoke_test.py")


requests.post = _blocked
requests.get = _blocked
lab.get_api_key = lambda secrets=None: (None, None)   # ignore any real .env or secrets

# Buttons every version of the app must show (Prompt A layout in CLAUDE.md), with these exact labels.
REQUIRED_BUTTONS = ("Generate balanced set (2 paid calls)", "Load the 8 offline fixtures (hand-authored)",
                    "Clear dataset")
REQUIRED_DETECT_BUTTONS = ("Run both detectors (2 paid calls)", "Retry economy detector only (1 paid call)",
                           "Retry advanced detector only (1 paid call)")
REQUIRED_DETECT_PREFIXES = ("Check pasted passage (",)
DESTRUCTIVE = re.compile(r"clear|reset|unfreeze|delete|discard", re.I)
TEXT_KINDS = ("markdown", "caption", "info", "warning", "error", "success", "text", "title",
              "header", "subheader", "code", "exception")


def page_text(at: AppTest) -> str:
    parts = []
    for kind in TEXT_KINDS:
        try:
            parts += [str(getattr(e, "value", "") or getattr(e, "body", "")) for e in getattr(at, kind)]
        except Exception:
            pass
    for kind in ("dataframe", "table"):
        try:
            parts += [e.value.to_string() for e in getattr(at, kind)]
        except Exception:
            pass
    return "\n".join(parts)


def fail(msg: str, at: AppTest | None = None) -> None:
    print(f"SMOKE TEST FAILED: {msg}")
    if at is not None and at.exception:
        for e in at.exception:
            print("  exception:", getattr(e, "message", e))
            for line in (getattr(e, "stack_trace", None) or [])[-8:]:
                print("   ", line)
    sys.exit(1)


def quiet() -> None:
    """Silence Streamlit's own log lines (AppTest resets their level on every run)."""
    for name in list(logging.root.manager.loggerDict):
        if name.startswith("streamlit"):
            logging.getLogger(name).disabled = True


def run(at: AppTest) -> None:
    quiet()
    at.run()


def button_id(b) -> str:
    return f"{b.key or ''}|{b.label}"


def main() -> None:
    if not (HERE / "app.py").exists():
        fail("app.py not found")
    t0 = time.monotonic()
    quiet()
    at = AppTest.from_file(str(HERE / "app.py"), default_timeout=30)
    run(at)
    if at.exception:
        fail("exception on startup", at)
    text = page_text(at)
    for needle, what in ((lab.WHO_URL, "WHO link"), ("Classroom exercise", "exercise warning"),
                         ("smoking is harmful", "correction")):
        if needle.lower() not in text.lower():
            fail(f"{what} not shown on the start page (looked for {needle!r})")

    labels = {b.label for b in at.button}
    missing = [x for x in REQUIRED_BUTTONS if x not in labels]
    if "Detect & compare" in {t.label for t in at.tabs}:       # after Prompt B
        missing += [x for x in REQUIRED_DETECT_BUTTONS if x not in labels]
        missing += [x + "..." for x in REQUIRED_DETECT_PREFIXES if not any(l.startswith(x) for l in labels)]
    if missing:
        fail(f"button(s) missing or relabelled: {missing} (use the exact labels from CLAUDE.md)")

    clicked: list[str] = []
    seen: set[str] = set()

    def click_round(destructive: bool) -> None:
        for _ in range(40):
            candidates = [b for b in at.button if not b.disabled and button_id(b) not in seen
                          and bool(DESTRUCTIVE.search(b.label or "")) == destructive]
            if not candidates:
                return
            b = candidates[0]
            seen.add(button_id(b))
            b.click()
            run(at)
            clicked.append(b.label)
            if at.exception:
                fail(f"exception after clicking {b.label!r}", at)
            if ATTEMPTS:
                fail(f"HTTP request attempted after clicking {b.label!r} (offline, no key): {ATTEMPTS[0]}")

    click_round(destructive=False)
    dets = at.session_state["detections"] if "detections" in at.session_state else None
    if dets and "correct" not in page_text(at):
        fail("detector results exist but no matrix cell (lab.cell_summary) is shown")
    rows = at.session_state["dataset"]["rows"] if "dataset" in at.session_state else None
    click_round(destructive=True)       # clear/reset/unfreeze last, so they do not hide other buttons

    if not any("fixture" in c.lower() for c in clicked):
        fail("no button mentioning 'fixture' was clicked; offline fixtures must load from a button")
    note = (f"{len(rows)} row(s) in session_state['dataset'] before clear/reset buttons" if rows is not None
            else "no session_state['dataset']")
    note += ", matrix shown" if dets else ""
    print(f"SMOKE TEST PASSED in {time.monotonic() - t0:.1f} s: startup ok, warning/correction/WHO link shown, "
          f"{len(clicked)} button(s) clicked without errors, 0 network requests, {note}.")
    for c in clicked:
        print("  clicked:", c)


if __name__ == "__main__":
    main()
