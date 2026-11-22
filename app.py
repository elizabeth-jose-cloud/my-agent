"""Weekly Status Report Agent: turns rough team updates into a clean report."""
import os

import pandas as pd
import streamlit as st

from agent import run, to_markdown
from demo import SECTIONS
from prompts import SYSTEM_PROMPT

st.set_page_config(page_title="Weekly Status Report Agent", page_icon="📊", layout="wide")


def setting(name: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets first, then from the environment."""
    try:
        value = st.secrets.get(name, "")
    except Exception:  # no secrets file: perfectly normal in demo mode
        value = ""
    return str(value or os.getenv(name, default)).strip()


API_KEY = setting("AI_API_KEY")
BASE_URL = setting("AI_BASE_URL", "https://api.openai.com/v1")
MODEL = setting("AI_MODEL", "gpt-4o-mini")

SECTION_ICON = {
    "Highlights": "🌟",
    "Progress": "✅",
    "Risks": "⚠️",
    "Blockers": "⛔",
    "Next week": "📅",
}

SAMPLE_FILE = "sample_updates.txt"


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def load_sample():
    st.session_state.updates = read_file(SAMPLE_FILE)


if "updates" not in st.session_state:
    st.session_state.updates = ""

st.title("Weekly Status Report Agent")
st.caption("Turn rough team updates into a clean, structured weekly report.")

if API_KEY:
    st.success(f"Using AI model ({MODEL}).")
else:
    st.info("Demo mode: running with rule-based heuristics. Add your AI key to use a real model.")

left_col, right_col = st.columns([1, 1.25], gap="large")

with left_col:
    st.subheader("Team updates")
    st.button("Load sample updates", on_click=load_sample, width="stretch", icon=":material/description:")
    updates = st.text_area(
        "Rough notes for the week",
        key="updates",
        height=330,
        placeholder="Paste stand-up notes, Jira lines, or emails, one per line...",
    )
    go = st.button("Write my report", type="primary", width="stretch")

with right_col:
    if go:
        if not updates.strip():
            st.warning("Please paste some notes first, or press 'Load sample updates'.")
        else:
            with st.spinner("The agent is reading the notes, writing the report, and checking its work..."):
                try:
                    result, steps = run(updates, SYSTEM_PROMPT, API_KEY, BASE_URL, MODEL)
                except Exception as err:
                    st.error(f"The AI model could not answer. Check your key and model name, then try again. Details: {err}")
                    st.stop()
            st.session_state.result, st.session_state.steps = result, steps

    result = st.session_state.get("result")
    steps = st.session_state.get("steps", [])

    if not result:
        with st.container(border=True):
            st.markdown("#### How it works")
            st.markdown(
                "1. Paste your team's rough notes, or press **Load sample updates**.\n"
                "2. Click **Write my report**.\n"
                "3. The agent categorizes every note, checks its own work, and generates your status report."
            )
    else:
        status = result.get("status", "Amber")
        reason = result.get("status_reason", "")
        if status == "Green":
            st.success(f"**Overall status: Green** — {reason}", icon=":material/check_circle:")
        elif status == "Red":
            st.error(f"**Overall status: Red** — {reason}", icon=":material/error:")
        else:
            st.warning(f"**Overall status: Amber** — {reason}", icon=":material/warning:")

        if result.get("headline") or result.get("summary"):
            with st.container(border=True):
                if result.get("headline"):
                    st.markdown(f"**What matters most this week:** {result['headline']}")
                if result.get("summary"):
                    st.markdown(f"**Summary:** {result['summary']}")

        items = result.get("items", [])
        count = lambda s: len([i for i in items if i.get("section") == s])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Highlights", count("Highlights"))
        m2.metric("Risks", count("Risks"))
        m3.metric("Blockers", count("Blockers"))
        m4.metric("Questions", len(result.get("questions", [])))

        tab_report, tab_register, tab_actions, tab_email, tab_questions, tab_steps = st.tabs(
            ["Report", "Risks and blockers", "Actions and decisions", "Email to sponsor", "Questions for the team", "Agent steps"]
        )

        with tab_report:
            for s in SECTIONS:
                with st.container(border=True):
                    st.markdown(f"**{SECTION_ICON.get(s, '')} {s}**")
                    rows = [i for i in items if i.get("section") == s]
                    if not rows:
                        st.caption("Nothing to report.")
                    else:
                        for item in rows:
                            meta = []
                            if item.get("owner"):
                                meta.append(f"Owner: {item['owner']}")
                            if item.get("due"):
                                meta.append(f"Due: {item['due']}")
                            meta_str = f" *({', '.join(meta)})*" if meta else ""
                            st.markdown(f"- {item.get('text', '')}{meta_str}")

        with tab_register:
            reg = [i for i in items if i.get("section") in ("Risks", "Blockers")]
            if reg:
                df = pd.DataFrame([
                    {
                        "Type": i.get("section", "")[:-1],
                        "Impact": i.get("impact") or "Not known",
                        "Owner": i.get("owner") or "Not known",
                        "Due": i.get("due") or "Not known",
                        "Item": i.get("text", ""),
                    }
                    for i in reg
                ])
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info("No risks or blockers recorded this week.")

        with tab_actions:
            st.markdown("##### Top actions this week")
            actions = result.get("actions", [])
            if actions:
                for n, a in enumerate(actions, 1):
                    with st.container(border=True):
                        st.markdown(f"**{n}. {a.get('action', '')}**")
                        st.caption(f"Owner: {a.get('owner') or 'Not known'}  •  Why: {a.get('why', '')}")
            else:
                st.caption("No actions needed.")

            st.markdown("##### Decisions needed")
            decisions = result.get("decisions", []) or ["None this week."]
            for dcs in decisions:
                st.markdown(f"- {dcs}")

        with tab_email:
            st.text_area(
                "Ready to copy and send",
                value=result.get("email", "") or "Not enough information.",
                height=220,
            )

        with tab_questions:
            questions = result.get("questions", []) or ["No information is missing."]
            for q in questions:
                st.markdown(f"- {q}")

        with tab_steps:
            for n, s in enumerate(steps, 1):
                with st.container(border=True):
                    icon = "✅" if s["ok"] else "⚠️"
                    st.markdown(f"**{n}. {s['name']}** {icon}")
                    st.caption(s["detail"])

        st.download_button(
            label="Download the report",
            data=to_markdown(result),
            file_name="weekly-status-report.md",
            mime="text/markdown",
            width="stretch",
        )
        st.caption("Check the report before you send it. The agent only uses what is in the notes.")

st.divider()
st.markdown(
    '<div style="text-align: center; color: #6b7280; font-size: 0.85rem;">'
    "Built by Elizabeth Jose at Zero to Live, Future Proof India"
    "</div>",
    unsafe_allow_html=True,
)
