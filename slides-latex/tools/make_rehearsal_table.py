"""Write data/rehearsal_table.tex and data/rehearsal_calls.tex from the app's recorded_run.json.

Usage: python tools/make_rehearsal_table.py ../fallback/full-app/recorded_run.json
The slides then contain exactly the recorded values (no hand transcription).
"""
import json
import sys
from pathlib import Path

here = Path(__file__).resolve().parents[1]
rec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ds, dets = rec["dataset"], rec["detections"]
by_id = {r["row_id"]: r for r in ds["rows"]}


def esc(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        s = s.replace(a, b)
    return (s.replace("’", "'").replace("‘", "'").replace("“", "``").replace("”", "''")
             .replace("—", "---").replace("–", "--"))


def excerpt(text: str, n: int = 7) -> str:
    words = text.split()
    return esc(" ".join(words[:n])) + (r"\,\dots" if len(words) > n else "")


def verdict(role: str, rid: str) -> str:
    x = dets[role]["results"][rid]
    if x["status"] != "predicted":
        return "failure"
    short = {"contradicted": "contradicted", "supported": "supported", "insufficient_evidence": "insufficient"}
    return f"{short[x['verdict']]} [{x['evidence_ref']}]"


lines = [r"\begin{tabular}{@{}r l l l l p{0.30\textwidth} l l@{}}", r"\toprule",
         r"\# & blind ID & generator & intended & format & passage (first words) & economy det. & advanced det.\\",
         r"\midrule"]
for n, rid in enumerate(ds["frozen_order"], 1):
    r = by_id[rid]
    lines.append(f"{n} & \\texttt{{{ds['blind_ids'][rid]}}} & {r['generator_role']} & {r['intended_label']} & "
                 f"{'social' if r['format'] == 'social_post' else 'science'} & {excerpt(r['passage'])} & "
                 f"{verdict('economy', rid)} & {verdict('advanced', rid)}\\\\")
lines.append(r"\midrule")
for r in ds["rows"]:
    if r["review_status"] == "excluded":
        lines.append(f"-- & excluded & {r['generator_role']} & {r['intended_label']} & "
                     f"{'social' if r['format'] == 'social_post' else 'science'} & {excerpt(r['passage'])} & "
                     r"\multicolumn{2}{l}{not scored: " + esc(r["review_note"].split(":")[0]) + r"}\\")
lines += [r"\bottomrule", r"\end{tabular}"]
(here / "data" / "rehearsal_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

calls = [r"\begin{tabular}{@{}l l l r r r@{}}", r"\toprule",
         r"call & role & model & seconds & tokens in/out & cost (US\$, reported)\\", r"\midrule"]
for c in rec["calls"]:
    u = c["usage"] or {}
    cost = f"{c['cost_usd']:.6f}" if isinstance(c["cost_usd"], (int, float)) else "unavailable"
    kind = "generate" if c["kind"].startswith("generate") else "detect"
    calls.append(f"{kind} & {c['role']} & \\texttt{{{esc(c['model_requested'])}}} & {c['elapsed_s']:.1f} & "
                 f"{u.get('prompt_tokens', '--')}/{u.get('completion_tokens', '--')} & {cost}\\\\")
calls += [r"\bottomrule", r"\end{tabular}"]
(here / "data" / "rehearsal_calls.tex").write_text("\n".join(calls) + "\n", encoding="utf-8")

# 2 x 2 matrix from the metrics the app computed at recording time.
met = rec["metrics_at_recording"]


def pct(r):
    return "N/A" if r["value"] is None else f"{r['num']}/{r['den']}"


def cell(m):
    note = "" if m["balanced"] else r"\\\textit{imbalanced cell}"
    return (r"\begin{tabular}[t]{@{}l@{}}"
            f"\\textbf{{\\large {m['correct']}/{m['eligible']}}} correct of eligible \\textperiodcentered{{}} "
            f"coverage {pct(m['coverage'])}\\\\"
            f"abstentions {m['abstentions']} \\textperiodcentered{{}} failures {m['failures']}\\\\"
            f"recall {pct(m['false_claim_recall'])} \\textperiodcentered{{}} false positives {m['fp']} of {m['n_true']} true{note}"
            r"\end{tabular}")


rows = [r"\begin{tabular}{@{}l|l|l@{}}",
        r" & \textbf{Economy detector} & \textbf{Advanced detector}\\",
        r"\hline"]
for g in ("economy", "advanced"):
    rows.append(f"\\begin{{tabular}}[t]{{@{{}}l@{{}}}}\\textbf{{{g.capitalize()}}}\\\\\\textbf{{generator}}\\end{{tabular}} & "
                + cell(met[f"{g}_generator__economy_detector"]) + " & "
                + cell(met[f"{g}_generator__advanced_detector"]) + r"\\[1mm]\hline")
rows.append(r"\end{tabular}")
(here / "data" / "rehearsal_matrix.tex").write_text("\n".join(rows) + "\n", encoding="utf-8")
print("wrote data/rehearsal_table.tex, data/rehearsal_calls.tex and data/rehearsal_matrix.tex")
