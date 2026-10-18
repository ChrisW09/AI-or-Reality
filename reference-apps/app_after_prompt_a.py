"""Classroom generator: clearly labelled TRUE/FALSE tobacco claims, built on the tested starter kit.

Run with:  .venv/bin/python -m streamlit run app.py
Every model call sits behind an explicit button; everything lives in st.session_state.
"""
import streamlit as st

import lab

st.set_page_config(page_title="Classroom claim generator", layout="wide")
ss = st.session_state
ss.setdefault("dataset", lab.new_dataset())
ss.setdefault("calls", [])
ss.setdefault("messages", [])

cfg, cfg_problem = lab.load_models()
defaults = lab.default_model_ids(cfg)
for role in lab.ROLES:
    ss.setdefault(f"model_{role}", defaults[role])
key, key_source = lab.get_api_key(st.secrets)


def say(kind: str, text: str) -> None:
    ss.messages.append((kind, text))


def log_call(res: dict) -> None:
    if res.get("call"):
        ss.calls.append(res["call"])


def clear_dataset() -> None:
    ss.dataset = lab.new_dataset()
    ss.messages = [("info", "Dataset cleared.")]


def card(row: dict) -> None:
    with st.container(border=True):
        fmt = lab.FORMATS[row["format"]]["label"]
        st.markdown(f"**{row['row_id']}** · {fmt} · intended label: **{lab.LABEL_NAMES[row['intended_label']]}**")
        if row["source_type"] == "fixture":
            st.caption("FIXTURE: hand-authored for the offline demonstration, NOT model output")
        else:
            st.caption(f"{row['generator_role']} generator · `{row['generator_model']}` · {row['provenance']}")
        st.code(row["passage"], language=None, wrap_lines=True)
        if row["flags"]:
            st.warning("Hints: " + "; ".join(row["flags"]))


# ------------------------------------------------------------------ header --
st.title("Classroom generator: TRUE vs FALSE tobacco claims")
st.warning(lab.EXERCISE_WARNING)
st.info(f"{lab.CORRECTION}  \nSource: [WHO tobacco fact sheet]({lab.WHO_URL})")

# ----------------------------------------------------------------- sidebar --
with st.sidebar:
    st.header("Settings")
    offline = st.toggle("Offline mode (no network calls)", value=True, key="offline")
    if key:
        st.success(f"OpenRouter key found ({key_source})")
    else:
        st.warning("No OpenRouter key found. Live buttons are disabled.")
    if cfg_problem:
        st.error(cfg_problem)
    st.subheader("Generator models")
    for role in lab.ROLES:
        st.text_input(f"{role} model ID", key=f"model_{role}")
        st.caption(f"Exact ID: `{ss[f'model_{role}'].strip()}` · {lab.documented_size(cfg, ss[f'model_{role}'].strip())}")
    st.subheader("Provider routing")
    st.caption("Same model, chosen endpoint; sent with every request.")
    st.json(lab.routing(cfg) or {"routing": "OpenRouter default"})

live = (not offline) and bool(key)
ds = ss.dataset
why_not_live = "offline mode is on." if offline else "no API key found."

# ---------------------------------------------------------------- generate --
st.header("Generate a balanced set")
st.caption("One batch call per generator; both models get the same 4 assignments "
           "(TRUE/FALSE claim x social post/scientific paragraph).")
if not live:
    st.caption("Live generation is disabled: " + why_not_live)
if st.button("Generate balanced set (2 paid calls)", disabled=not live):
    for role in lab.ROLES:
        try:
            res = lab.generate(key, role, ss[f"model_{role}"], lab.balanced_slots(), cfg)
            log_call(res)
            lab.store_generation(ds, role, res)
            say("success" if res["ok"] else "error", res["message"])
        except ValueError as e:
            say("error", str(e))
            break

st.header("Offline fixtures")
o1, o2 = st.columns(2)
if o1.button("Load the 8 offline fixtures (hand-authored)"):
    try:
        lab.load_fixtures(ds)
        say("info", "Loaded 8 hand-authored fixtures. They are NOT model output and never count as measurements.")
    except ValueError as e:
        say("error", str(e))
o2.button("Clear dataset", on_click=clear_dataset)

for kind, text in ss.messages[-6:]:
    getattr(st, kind)(text)

# -------------------------------------------------------------------- rows --
st.header(f"Dataset ({len(ds['rows'])} rows)")
if ds["source_type"]:
    st.caption(f"Source: {ds['source_type']} · {ds.get('provenance') or ''}")
for row in ds["rows"]:
    card(row)

st.header("Generation failures")
if ds["problems"]:
    st.dataframe(ds["problems"], width="stretch")
else:
    st.caption("None.")

st.header("Calls: time and cost")
if ss.calls:
    st.dataframe([{"kind": c.get("kind"), "role": c.get("role"), "model": c.get("model_requested"),
                   "status": c.get("status"), "message": c.get("message"), "elapsed_s": c.get("elapsed_s"),
                   "cost": lab.cost_text(c.get("cost_usd")), "started_utc": c.get("started_at_utc")}
                  for c in ss.calls], width="stretch")
else:
    st.caption("No calls yet.")

st.download_button("Download JSON (everything, with exercise warning, no key)",
                   lab.export_json(ds, [], ss.calls), file_name="classroom_export.json",
                   mime="application/json")
