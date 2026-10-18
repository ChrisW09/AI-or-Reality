"""Copy the exact prompt text from ../prompts/*.md into prompts/*.txt for the slides.

The Markdown files are the single source of truth; run this after editing them.
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parents[1]
src = here.parent / "prompts"
for name in ("01-build-generator", "02-add-detection"):
    md = (src / f"{name}.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```text\n(.*?)```", md, re.S)
    if len(blocks) != 1:
        sys.exit(f"{name}.md: expected exactly one ```text block, found {len(blocks)}")
    text = blocks[0]
    bad = sorted({c for c in text if ord(c) > 126 or (ord(c) < 32 and c != "\n")})
    if bad:
        sys.exit(f"{name}: non-ASCII characters {bad!r} would need listings literate rules")
    (here / "prompts" / f"{name}.txt").write_text(text, encoding="utf-8")
    print(f"{name}.txt: {len(text.splitlines())} lines, longest {max(map(len, text.splitlines()))} chars")
