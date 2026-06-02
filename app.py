"""
Physician AI — Streamlit frontend

Run with:
    streamlit run app.py

The physician selects a patient in the sidebar, then uses contextual action
buttons to trigger agentic workflows. Each step streams progress in real time
via st.status() as the agent network runs.
"""

import os
import re
import json
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

from tools.epic import EpicClient
from wiki.loader import (
    load_wiki, get_pending_updates, remove_pending_update,
    update_wiki, get_wiki_file_content, save_wiki_file_content,
    get_wiki_insight, parse_wiki_sections, generate_id
)
from wiki.guidelines import search_pubmed, save_guideline, search_guidelines, delete_guideline
from llm import AnthropicBackend, GeminiBackend
from workflows.engine import WorkflowEngine
from workflows.admission import ADMISSION_STEPS
from workflows.discharge import DISCHARGE_STEPS
from workflows.case_management import CASE_MANAGEMENT_STEPS
from context.patient_context import PatientContext
from agents.admission.action_extraction import ActionExtractionAgent
from agents.checkin import CheckInAgent

load_dotenv()

# ---------------------------------------------------------------------------
# Page config & Global CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Physician AI",
    page_icon="🏥",
    layout="wide",
)

st.markdown("""
<style>
/* ── Fonts: SF Pro on macOS, system-ui everywhere else ── */
body {
    font-family: -apple-system, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
}
button, input, textarea, select {
    font-family: inherit;
}

/* ── Background ─────────────────────────────────────── */
.stApp {
    background: linear-gradient(145deg, #cfe0f0 0%, #ddd4ee 40%, #c8e8da 100%) fixed;
    min-height: 100vh;
}
.main, .block-container {
    background: transparent !important;
}
.main .block-container {
    padding: 1.5rem 2.5rem 3rem;
    max-width: 1400px;
}

/* ── Sidebar: dark liquid glass ─────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(10, 22, 50, 0.82) !important;
    backdrop-filter: blur(40px) saturate(180%);
    -webkit-backdrop-filter: blur(40px) saturate(180%);
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] .stMarkdown { color: rgba(255,255,255,0.85) !important; }
[data-testid="stSidebar"] h1 { color: #fff !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12) !important; }
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stDownloadButton > button {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: rgba(255,255,255,0.9) !important;
    border-radius: 980px !important;
    backdrop-filter: blur(10px);
}
[data-testid="stSidebar"] .stButton > button:hover,
[data-testid="stSidebar"] .stDownloadButton > button:hover {
    background: rgba(255,255,255,0.18) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.22) !important;
    border-color: rgba(255,255,255,0.45) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"]:hover > div {
    background: rgba(255,255,255,0.3) !important;
    border-color: rgba(255,255,255,0.6) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="select"] svg {
    color: #fff !important;
    fill: #fff !important;
}

/* ── Typography ─────────────────────────────────────── */
h2 {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    color: #1C1C1E !important;
}
h3 {
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
    color: rgba(60,60,67,0.5) !important;
    margin-top: 1.75rem !important;
}
p, li { color: #1C1C1E; }

/* ── Buttons: pill-shaped liquid glass ──────────────── */
.stButton > button,
.stDownloadButton > button {
    border-radius: 980px !important;
    font-weight: 590 !important;
    font-size: 0.9rem !important;
    letter-spacing: -0.01em !important;
    transition: all 0.2s cubic-bezier(0.25,0.46,0.45,0.94) !important;
    padding: 0.45rem 1.3rem !important;
}
.stButton > button[kind="primary"] {
    background: rgba(0,122,255,0.92) !important;
    border: 1px solid rgba(0,122,255,0.5) !important;
    color: #fff !important;
    box-shadow: 0 2px 12px rgba(0,122,255,0.35), inset 0 1px 0 rgba(255,255,255,0.25) !important;
    backdrop-filter: blur(10px);
}
.stButton > button[kind="primary"]:hover {
    background: rgba(0,100,220,0.95) !important;
    box-shadow: 0 4px 20px rgba(0,122,255,0.5), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transform: translateY(-1px) scale(1.01) !important;
}
.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.45) !important;
    border: 1px solid rgba(255,255,255,0.7) !important;
    color: #007AFF !important;
    backdrop-filter: blur(16px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.8) !important;
}
.stButton > button[kind="secondary"]:hover {
    background: rgba(255,255,255,0.65) !important;
    transform: translateY(-1px) !important;
}

/* ── Expanders: glass look ──── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.58) !important;
    border: 1px solid rgba(255,255,255,0.72) !important;
    border-radius: 18px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.07), inset 0 1px 0 rgba(255,255,255,0.9) !important;
    margin-bottom: 0.5rem;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    border-radius: 18px !important;
    color: #1C1C1E !important;
}

/* ── Tabs ───────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.45) !important;
    border-radius: 12px !important;
    padding: 3px !important;
    gap: 2px !important;
    border: 1px solid rgba(255,255,255,0.65) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-weight: 500 !important;
    color: rgba(60,60,67,0.6) !important;
    padding: 0.35rem 1rem !important;
    border: none !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,255,255,0.85) !important;
    color: #007AFF !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1) !important;
}

/* ── Text areas ─────────────────────────────────────── */
.stTextArea textarea {
    background: rgba(255,255,255,0.62) !important;
    border: 1px solid rgba(255,255,255,0.78) !important;
    border-radius: 14px !important;
    font-family: "SF Mono", "Menlo", "Monaco", monospace !important;
    font-size: 0.84rem !important;
    color: #1C1C1E !important;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.05) !important;
    line-height: 1.6 !important;
}
.stTextArea textarea:focus {
    border-color: rgba(0,122,255,0.5) !important;
    box-shadow: 0 0 0 4px rgba(0,122,255,0.12), inset 0 1px 3px rgba(0,0,0,0.04) !important;
    background: rgba(255,255,255,0.82) !important;
}

/* ── File uploader ──────────────────────────────────── */
[data-testid="stFileUploadDropzone"] {
    background: rgba(255,255,255,0.42) !important;
    border: 2px dashed rgba(0,122,255,0.45) !important;
    border-radius: 20px !important;
    transition: all 0.25s cubic-bezier(0.25,0.46,0.45,0.94) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.7) !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    background: rgba(255,255,255,0.62) !important;
    border-color: rgba(0,122,255,0.7) !important;
    box-shadow: 0 0 0 5px rgba(0,122,255,0.1), inset 0 1px 0 rgba(255,255,255,0.85) !important;
}

/* ── Code blocks ────────────────────────────────────── */
[data-testid="stCodeBlock"] pre {
    background: rgba(28,28,30,0.88) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    font-family: "SF Mono", "Menlo", monospace !important;
    font-size: 0.82rem !important;
    line-height: 1.7 !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18) !important;
}

/* ── Alerts / info boxes ────────────────────────────── */
[data-testid="stAlert"] {
    background: rgba(255,255,255,0.55) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.72) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}

/* ── Dividers ───────────────────────────────────────── */
hr { border-color: rgba(60,60,67,0.12) !important; }

/* ── Sticky wiki panel ──────────────────────────────── */
div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stVerticalBlock"] {
    position: sticky; top: 2rem; align-self: flex-start; z-index: 1000;
}
div[data-testid="stHorizontalBlock"],
div[data-testid="stVerticalBlock"],
.main .block-container { overflow: visible !important; }

/* ── Patient header card ────────────────────────────── */
.patient-header-card {
    background: rgba(255,255,255,0.55);
    backdrop-filter: blur(28px) saturate(200%);
    -webkit-backdrop-filter: blur(28px) saturate(200%);
    border: 1px solid rgba(255,255,255,0.8);
    border-radius: 24px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.95);
    position: relative; overflow: hidden;
}
.patient-header-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 45%;
    background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 100%);
    border-radius: 24px 24px 0 0; pointer-events: none;
}
.patient-name {
    font-size: 1.75rem; font-weight: 700; letter-spacing: -0.03em; color: #1C1C1E;
}
.patient-meta { font-size: 1.1rem; font-weight: 400; color: rgba(60,60,67,0.5); margin-left: 0.5rem; }
.chief-complaint { color: rgba(60,60,67,0.65); font-size: 0.93rem; margin: 0.4rem 0 1rem; }
.vitals-row { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.vital-chip {
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.85);
    border-radius: 980px;
    padding: 0.28rem 0.85rem;
    font-size: 0.8rem; font-weight: 600; color: #1C1C1E;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.9);
}
.vital-chip.alert {
    background: rgba(255,59,48,0.1);
    border-color: rgba(255,59,48,0.25);
    color: #FF3B30;
}

/* ── Episode learnings card ─────────────────────────── */
.insights-card {
    background: linear-gradient(135deg, rgba(88,86,214,0.08) 0%, rgba(255,255,255,0.52) 100%);
    backdrop-filter: blur(28px) saturate(180%);
    -webkit-backdrop-filter: blur(28px) saturate(180%);
    border: 1px solid rgba(88,86,214,0.18);
    border-radius: 24px;
    padding: 1.75rem 2rem;
    box-shadow: 0 8px 32px rgba(88,86,214,0.08), inset 0 1px 0 rgba(255,255,255,0.9);
    margin-top: 0.5rem;
}
.insights-title {
    font-size: 1.05rem; font-weight: 700; color: #3634A3; letter-spacing: -0.02em;
    margin-bottom: 0.2rem;
}
.insights-sub { font-size: 0.82rem; color: rgba(60,60,67,0.55); margin-bottom: 1.1rem; }
.insights-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-top: 0.75rem;
}
.insight-row {
    display: flex; align-items: flex-start; gap: 0.55rem;
    background: rgba(255,255,255,0.5); border: 1px solid rgba(88,86,214,0.1);
    border-radius: 12px; padding: 0.55rem 0.75rem;
}
.insight-badge {
    font-size: 0.6rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    padding: 0.15rem 0.5rem; border-radius: 980px; white-space: nowrap; margin-top: 0.15rem; flex-shrink: 0;
}
.insight-badge.protocol   { background: rgba(0,122,255,0.1);   color: #0056D6; }
.insight-badge.preference { background: rgba(88,86,214,0.1);   color: #3634A3; }
.insight-header   { font-size: 0.83rem; font-weight: 600; color: #1C1C1E; line-height: 1.35; }
.insight-category { font-size: 0.71rem; color: rgba(88,86,214,0.55); margin-top: 0.1rem; }

/* ── Action cards ───────────────────────────────────── */
.action-card {
    background: rgba(255,255,255,0.55);
    backdrop-filter: blur(28px) saturate(200%);
    -webkit-backdrop-filter: blur(28px) saturate(200%);
    border: 1px solid rgba(255,255,255,0.8);
    border-radius: 24px;
    padding: 2rem 1.5rem 1.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.95);
    position: relative; overflow: hidden; height: 100%;
}
.action-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 40%;
    background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 100%);
    pointer-events: none;
}
.action-card-icon { font-size: 2.6rem; margin-bottom: 0.6rem; line-height: 1; }
.action-card-title { font-size: 1.15rem; font-weight: 700; color: #1C1C1E; letter-spacing: -0.02em; }
.action-card-sub { font-size: 0.82rem; color: rgba(60,60,67,0.55); margin: 0.3rem 0 1.25rem; }
.action-card-done { font-size: 0.82rem; color: #34C759; font-weight: 600; margin: 0.3rem 0 1.25rem; }

/* ── Wiki reference box ─────────────────────────────── */
.wiki-ref-box {
    background: rgba(255,255,255,0.55);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.75);
    border-radius: 18px;
    padding: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.9);
    margin-top: 1rem;
}
.wiki-ref-header {
    color: #007AFF; font-weight: 700; font-size: 0.95rem;
    margin-bottom: 0.5rem; border-bottom: 1px solid rgba(0,0,0,0.06); padding-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "active_citation" not in st.session_state:
    st.session_state.active_citation = None

# ---------------------------------------------------------------------------
# Workflow output cache
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("context/records")

# Every session_state key that makes up a patient's in-progress workflow / "Ready for
# Review" UI. Cleared (along with on-disk artifacts) by the sidebar reset button.
_WORKFLOW_RESET_KEYS = [
    "active_workflow", "workflow_outputs", "workflow_complete",
    "prescription_drafts", "approved_orders", "rx_sent_to_epic", "labs_sent_to_epic",
    "note_saved", "note_emailed", "show_rx_dialog", "show_labs_dialog", "show_notes_dialog",
    "episode_wiki_saved",
    "show_checkin", "checkin_result", "checkin_file_key", "checkin_sample_loaded",
    "ci_meds_sent", "ci_labs_sent", "ci_updates_saved",
    "show_ci_meds", "show_ci_labs", "show_ci_updates",
]

def _reset_workflow_state(patient_id: str) -> None:
    """Clears all in-session workflow UI state and the patient's generated artifacts so the
    "Ready for Review" section is fully dismissed on reset."""
    for _k in _WORKFLOW_RESET_KEYS:
        st.session_state.pop(_k, None)
    for _suffix in ("_workflow_cache.json", "_note.md"):
        _p = _CACHE_DIR / f"{patient_id}{_suffix}"
        if _p.exists():
            _p.unlink()

# ---------------------------------------------------------------------------
# Shared Utilities
# ---------------------------------------------------------------------------

def get_backend(provider: str):
    if provider == "Anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            st.error("ANTHROPIC_API_KEY not set in .env")
            st.stop()
        return AnthropicBackend(api_key=api_key), os.getenv("MODEL", "claude-opus-4-7")
    else:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            st.error("GEMINI_API_KEY not set in .env")
            st.stop()
        return GeminiBackend(api_key=api_key), os.getenv("MODEL", "gemini-3.1-flash-lite")

@st.cache_resource
def get_epic() -> EpicClient:
    return EpicClient()

def get_wiki_text(doctor: str = "default") -> str:
    return load_wiki(doctor) or ""

# ---------------------------------------------------------------------------
# Wiki Helpers
# ---------------------------------------------------------------------------

def get_related_updates(text: str, pending_list: list[dict]) -> list[int]:
    """Finds indices of pending updates related to the given text."""
    if not text: return []
    keywords = set(re.findall(r'\w{4,}', text.lower()))
    related_indices = []
    for i, item in enumerate(pending_list):
        content_words = set(re.findall(r'\w{4,}', (item.get('content', '') + " " + item['header']).lower()))
        if keywords & content_words:
            related_indices.append(i)
    return related_indices

# Matches a citation token, including comma-separated multi-ID lists like
# [WikiID: cdac3, 1b58ba, 274621] as well as bare/parenthesized variants. The id group is
# captured greedily as one id followed by any number of ", id" repeats so multi-ID lists
# are kept whole (a non-greedy capture with an optional closing bracket would stop at the
# first character).
_CITATION_PATTERN = re.compile(r'[\[\(]?\s*WikiID:\s*([a-zA-Z0-9]{3,}(?:\s*,\s*[a-zA-Z0-9]{3,})*)\s*[\]\)]?', re.IGNORECASE)


def _split_citation_ids(raw: str) -> list[str]:
    """Splits a captured id group (possibly comma/space separated) into clean lowercase ids."""
    return [p.strip().lower() for p in re.split(r'[,\s]+', raw) if p.strip()]


def _extract_citation_ids(text: str) -> list[str]:
    """Returns the ordered, de-duplicated wiki IDs referenced anywhere in text."""
    ids: list[str] = []
    for m in _CITATION_PATTERN.finditer(text or ""):
        for cid in _split_citation_ids(m.group(1)):
            if cid not in ids:
                ids.append(cid)
    return ids


def _citation_label(insight: dict, fallback: str = "") -> str:
    """Human-readable chip label from a get_wiki_insight() dict: 'Topic · Source'."""
    if not insight:
        return fallback or "Wiki ref"
    label = insight.get("topic") or insight.get("category") or "Wiki ref"
    source = (insight.get("attributes") or {}).get("Source")
    if source:
        label += f" · {source if len(source) <= 32 else source[:29] + '…'}"
    return label


def humanize_citations(text: str, doctor_id: str = "default") -> str:
    """Replaces raw [WikiID: xxx] tokens with readable [📚 Topic] labels for inline display."""
    if not text:
        return text
    def _repl(m):
        labels = []
        for cid in _split_citation_ids(m.group(1)):
            insight = get_wiki_insight(doctor_id, cid)
            labels.append(insight.get("topic") if insight else cid)
        return f"[📚 {'; '.join(labels)}]" if labels else m.group(0)
    return _CITATION_PATTERN.sub(_repl, text)


# Attribute keys that mark a wiki entry as clinical literature/guideline (vs. a protocol/preference).
_LITERATURE_MARKERS = ("Key Recommendation", "Source", "URL", "Decision")


def _is_literature(insight: dict) -> bool:
    """True if a resolved wiki entry looks like a guideline/literature reference."""
    return any(k in (insight.get("attributes") or {}) for k in _LITERATURE_MARKERS)


def _related_literature(insight: dict, self_id: str, doctor_id: str) -> list:
    """Resolves WikiIDs embedded in a note's text/attributes to any linked literature entries."""
    attrs = insight.get("attributes") or {}
    blob = " ".join([insight.get("rule", "")] + [str(v) for v in attrs.values()])
    related, seen = [], {(self_id or "").lower()}
    for cid in _extract_citation_ids(blob):
        if cid in seen:
            continue
        seen.add(cid)
        ref = get_wiki_insight(doctor_id, cid)
        if ref and _is_literature(ref):
            related.append((cid, ref))
    return related


def _render_related_literature(insight: dict, self_id: str, doctor_id: str):
    """Shows clinical literature/guidelines embedded within a wiki note, if any."""
    related = _related_literature(insight, self_id, doctor_id)
    if not related:
        return
    st.divider()
    st.markdown("**📖 Related literature**")
    for cid, ref in related:
        rattrs = ref.get("attributes") or {}
        st.markdown(f"- *{ref['rule']}*")
        bits = []
        if rattrs.get("Key Recommendation"): bits.append(rattrs["Key Recommendation"])
        if rattrs.get("Source"): bits.append(f"Source: {rattrs['Source']}")
        if rattrs.get("Decision"): bits.append(f"Decision: {rattrs['Decision']}")
        if bits: st.caption(" · ".join(bits))
        if rattrs.get("URL"): st.markdown(f"[View source]({rattrs['URL']})")


def _render_citation_detail(insight: dict, insight_id: str, doctor_id: str = "default"):
    """Renders the full source detail shown inside a citation popover / reference card."""
    if not insight:
        st.caption(f"Reference `{insight_id}` is not in your current wiki — it may have been edited or removed.")
        return
    attrs = insight.get("attributes") or {}
    st.markdown(f"**{insight['category']}** › {insight['topic']}")
    if attrs.get("Decision"):
        _render_decision_badge(attrs.get("Decision"))
    st.info(insight["rule"])
    if attrs.get("Key Recommendation"): st.markdown(f"**Key Recommendation:** {attrs['Key Recommendation']}")
    if attrs.get("Source"): st.caption(f"Source: {attrs['Source']}")
    if attrs.get("URL"): st.markdown(f"[View source]({attrs['URL']})")
    if attrs.get("Physician Notes"): st.markdown(f"**My Interpretation:** {attrs['Physician Notes']}")
    if attrs.get("Rationale"): st.markdown(f"**Rationale:** {attrs['Rationale']}")
    _render_related_literature(insight, insight_id, doctor_id)


def render_content_with_citations(text: str, key_suffix: str, doctor_id: str = "default", chips_only: bool = False):
    """Renders agent text with each WikiID turned into a labeled, self-describing source chip.

    Each chip names the guideline/protocol (topic · source) so the physician sees *where*
    a suggestion came from at a glance, and reveals the full rule, adopt/defer decision, and
    interpretation inline via st.popover. chips_only=True skips the body text — use it when the
    same text is shown in an adjacent editable widget.
    """
    if not text: return
    ids = _extract_citation_ids(text)
    if not chips_only:
        display_text = re.sub(r'[ \t]{2,}', ' ', _CITATION_PATTERN.sub('', text)).strip()
        st.markdown(display_text)
    if not ids:
        return
    if chips_only:
        st.caption("📚 Sources from your wiki:")
    insights = [(cid, get_wiki_insight(doctor_id, cid)) for cid in ids[:8]]
    has_popover = hasattr(st, "popover")
    cols = st.columns(min(len(insights), 4))
    for i, (cid, insight) in enumerate(insights):
        with cols[i % len(cols)]:
            label = f"📚 {_citation_label(insight, fallback=cid)}"
            if has_popover:
                with st.popover(label, use_container_width=True):
                    _render_citation_detail(insight, cid, doctor_id)
            elif st.button(label, key=f"cit_{cid}_{key_suffix}_{i}", type="secondary"):
                st.session_state.active_citation = cid
                st.rerun()

def render_wiki_reference_card(doctor_id: str = "default"):
    """Renders the cited wiki quote in the sticky panel."""
    insight_id = st.session_state.get("active_citation")
    if not insight_id: return
    insight = get_wiki_insight(doctor_id, insight_id)
    if insight:
        st.markdown(f'<div class="wiki-ref-box">', unsafe_allow_html=True)
        st.markdown(f'<div class="wiki-ref-header">📚 Wiki Reference</div>', unsafe_allow_html=True)
        st.markdown(f"**{insight['category']}** > {insight['topic']}")
        st.info(f"*{insight['rule']}*")
        _render_related_literature(insight, insight_id, doctor_id)
        if st.button("Close reference", use_container_width=True, type="primary"):
            st.session_state.active_citation = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("Reference details not found.")
        if st.button("Clear", use_container_width=True):
            st.session_state.active_citation = None
            st.rerun()

# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🏥 Physician AI")
    st.caption("Multi-agent clinical assistant")
    st.divider()
    app_mode = st.radio("Navigation", options=["Patient Workflows", "Wiki Management"], index=0)
    st.divider()
    if app_mode == "Patient Workflows":
        patient_id = st.selectbox("Patient", options=["TEST-001"], help="Select a patient to work with")
        llm_provider = st.radio("LLM Provider", options=["Anthropic", "Gemini"], index=0)
        st.divider()
        patient_ctx = PatientContext.load(patient_id)
        if patient_ctx.workflow_history:
            st.markdown("**Care Episode**")
            for rec in patient_ctx.workflow_history:
                date = rec.timestamp[:10]
                st.markdown(f"✓ {rec.workflow.replace('_', ' ').title()} — {date}")
            st.divider()
            if st.button("Reset patient context", type="secondary"):
                PatientContext.clear(patient_id)
                _reset_workflow_state(patient_id)
                st.rerun()
        st.divider()
        st.markdown("**Demo**")
        _sample_path = Path("sample_overnight_update.json")
        if _sample_path.exists():
            _sample_bytes = _sample_path.read_bytes()
            st.download_button("⬇ Download sample check-in file", data=_sample_bytes, file_name="sample_overnight_update.json", mime="application/json", use_container_width=True)
            if st.button("Use sample file →", use_container_width=True, type="secondary"):
                st.session_state["checkin_sample_loaded"] = True
                st.session_state["show_checkin"] = True
                st.rerun()
    st.divider()
    st.caption("Stanford CS323 — AI Awakening")

# ---------------------------------------------------------------------------
# Wiki Management View
# ---------------------------------------------------------------------------

DECISION_OPTIONS = ["Adopted", "Deferred", "Under review"]


def _render_decision_badge(decision: str):
    """Renders a colored badge reflecting the physician's adopt/defer decision."""
    d = (decision or "").strip().lower()
    if d == "adopted":
        st.success("✅ Adopted")
    elif d == "deferred":
        st.warning("⏸️ Deferred")
    else:
        st.info("🔎 Under review")


def render_guidelines_repository(doctor_id: str, search_query: str, col_filter):
    """
    Repository view of saved clinical guidelines & literature (guidelines.md).
    Shows each entry as a card with the physician's adopt/defer decision,
    interpretation notes, and rationale, all editable inline.
    """
    st.subheader("📚 My Clinical Guidelines & Literature")
    content = get_wiki_file_content(doctor_id, "guidelines.md")
    sections = parse_wiki_sections(content)
    if not sections:
        st.caption("No saved guidelines yet. Search PubMed or add an external source below to start your evidence library.")
        return

    categories = sorted(set(s['category'] for s in sections))
    filter_cat = col_filter.selectbox("Filter Guidelines", ["All"] + categories, key="filter_guidelines")

    def matches(s, r):
        if filter_cat != "All" and s['category'] != filter_cat:
            return False
        if not search_query:
            return True
        haystack = (s['category'] + " " + s['topic'] + " " + r['text'] + " " + " ".join(r['attributes'].values())).lower()
        return search_query in haystack

    current_cat = None
    shown = 0
    for s in sections:
        for r in s['rules']:
            if not matches(s, r):
                continue
            if s['category'] != current_cat:
                st.markdown(f"#### 📁 {s['category']}")
                current_cat = s['category']
            shown += 1
            attrs = r['attributes']
            rule_id = generate_id(s['category'], s['topic'], r['text'])
            with st.container(border=True):
                st.markdown(f"**{s['topic']}** — {r['text']}")
                _render_decision_badge(attrs.get("Decision"))
                if attrs.get("Key Recommendation"):
                    st.markdown(f"**Key Recommendation:** {attrs['Key Recommendation']}")
                if attrs.get("Source"):
                    st.caption(f"Source: {attrs['Source']}")
                if attrs.get("URL"):
                    st.markdown(f"[View source]({attrs['URL']})")
                if attrs.get("Physician Notes"):
                    st.markdown(f"**My Interpretation:** {attrs['Physician Notes']}")
                if attrs.get("Rationale"):
                    st.markdown(f"**Rationale:** {attrs['Rationale']}")

                with st.expander("✏️ Edit interpretation", expanded=False):
                    cur = (attrs.get("Decision") or "Under review").strip()
                    idx = DECISION_OPTIONS.index(cur) if cur in DECISION_OPTIONS else 2
                    new_decision = st.selectbox("Decision", DECISION_OPTIONS, index=idx, key=f"gl_dec_{rule_id}")
                    new_notes = st.text_area("Physician Notes", value=attrs.get("Physician Notes", ""), key=f"gl_notes_{rule_id}", placeholder="How I interpret / apply this for my patients...")
                    new_rat = st.text_area("Rationale", value=attrs.get("Rationale", ""), key=f"gl_rat_{rule_id}", placeholder="Why I adopt or defer this...")
                    bc1, bc2, _ = st.columns([1, 1, 4])
                    if bc1.button("💾 Save", key=f"gl_save_{rule_id}", type="primary"):
                        merged = dict(attrs)
                        merged["Decision"] = new_decision
                        merged["Physician Notes"] = new_notes
                        merged["Rationale"] = new_rat
                        save_guideline(s['category'], s['topic'], r['text'], merged, doctor_id)
                        st.success("Interpretation updated.")
                        st.rerun()
                    if bc2.button("🗑 Delete", key=f"gl_del_{rule_id}"):
                        delete_guideline(s['category'], s['topic'], r['text'], doctor_id)
                        st.rerun()

    if shown == 0:
        st.caption("No matching guidelines found.")


def render_pending_update_card(i: int, item: dict, doctor_id: str, suffix: str = "", expanded: bool = False):
    """Renders a single pending update card with Edit/Approve/Reject actions."""
    label = f"✨ [{item.get('category', 'General')}] {item.get('header', 'Miscellaneous')}"
    with st.expander(label, expanded=expanded):
        new_category = item.get('category', 'General')
        new_topic = item.get('header', 'Miscellaneous')
        default_content = item.get('content', '')
        if not default_content and "rules" in item:
            lines = []
            for r in item["rules"]:
                if isinstance(r, dict):
                    lines.append(f"- {r.get('text', '')}")
                    for k, v in r.get('attributes', {}).items():
                        lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"- {r}")
            default_content = "\n".join(lines)
        new_content = st.text_area("", value=default_content, key=f"edit_{suffix}_{i}", label_visibility="collapsed")
        col1, col2, col3 = st.columns([1, 1, 4])
        if col1.button("✅ Approve", key=f"app_{suffix}_{i}", type="primary"):
            dummy_content = f"## {new_category}\n### {new_topic}\n{new_content}"
            parsed_sections = parse_wiki_sections(dummy_content)
            if parsed_sections:
                rules = parsed_sections[0]['rules']
                update_data = [{"category": new_category, "topic": new_topic, "rules": rules}]
                if item.get('type') == 'protocol': update_wiki(doctor_id, update_data, [])
                else: update_wiki(doctor_id, [], update_data)
                remove_pending_update(doctor_id, i)
                st.success("Wiki evolved.")
                st.rerun()
        if col2.button("❌ Reject", key=f"rej_{suffix}_{i}"):
            remove_pending_update(doctor_id, i)
            st.rerun()

def render_wiki_management():
    st.header("📚 Doctor's Wiki & Preferences")
    st.markdown("Grounding for all agents. Review new learnings from cases, or manually edit your clinical protocols and preferences.")
    doctor_id = "default"
    pending = get_pending_updates(doctor_id)
    if pending:
        with st.expander(f"🔔 Pending Updates ({len(pending)})", expanded=False):
            st.info("The Wiki Substrate agent extracted these new insights from recent workflows. Review and approve them to evolve your wiki.")
            for i, item in enumerate(pending):
                render_pending_update_card(i, item, doctor_id, suffix="mgmt", expanded=True)
        st.divider()

    st.subheader("🖋 Current Wiki Content")
    col_search, col_filter = st.columns([2, 1])
    search_query = col_search.text_input("🔍 Search wiki...", "").lower()
    tab_protocols, tab_prefs, tab_lit = st.tabs(["📋 Clinical Protocols", "⚙️ Doctor Preferences", "📚 Literature & Guidelines"])
    
    def render_wiki_editor(filename: str, title: str):
        content = get_wiki_file_content(doctor_id, filename)
        sections = parse_wiki_sections(content)
        categories = sorted(list(set(s['category'] for s in sections)))
        filter_cat = col_filter.selectbox(f"Filter {title}", ["All"] + categories, key=f"filter_{filename}")
        filtered = [s for s in sections if (filter_cat == "All" or s['category'] == filter_cat) and (search_query in s['category'].lower() or search_query in s['topic'].lower() or any(search_query in (r['text'] if isinstance(r, dict) else r).lower() for r in s['rules']))]
        if not filtered: st.caption("No matching topics found.")
        current_display_cat = None
        for i, s in enumerate(filtered):
            if s['category'] != current_display_cat:
                st.markdown(f"#### 📁 {s['category']}")
                current_display_cat = s['category']
            with st.expander(f"{s['topic']}", expanded=False):
                new_cat, new_topic = s['category'], s['topic']
                rule_lines = []
                for r in s['rules']:
                    if isinstance(r, dict):
                        rule_lines.append(f"- {r['text']}")
                        for k, v in r.get('attributes', {}).items(): rule_lines.append(f"  - {k}: {v}")
                    else: rule_lines.append(f"- {r}")
                body_text = "\n".join(rule_lines)
                new_body = st.text_area("", value=body_text, height=200, key=f"body_ed_{filename}_{i}", label_visibility="collapsed")
                c1, c2, _ = st.columns([1, 1, 4])
                if c1.button("💾 Save", key=f"s_{filename}_{i}"):
                    dummy_content = f"## {new_cat}\n### {new_topic}\n{new_body}"
                    parsed_new = parse_wiki_sections(dummy_content)
                    if parsed_new:
                        new_rules = parsed_new[0]['rules']
                        new_sections = []
                        for orig in sections:
                            if orig['topic'] == s['topic'] and orig['category'] == s['category']:
                                new_sections.append({"category": new_cat, "topic": new_topic, "rules": new_rules})
                            else: new_sections.append(orig)
                        new_sections.sort(key=lambda x: x['category'])
                        reconstructed = ""
                        last_cat = None
                        for ns in new_sections:
                            if ns['category'] != last_cat:
                                reconstructed += f"\n## {ns['category']}\n"
                                last_cat = ns['category']
                            reconstructed += f"### {ns['topic']}\n"
                            for r in ns['rules']:
                                if isinstance(r, dict):
                                    reconstructed += f"- {r['text']}\n"
                                    for k, v in r.get('attributes', {}).items(): reconstructed += f"  - {k}: {v}\n"
                                else: reconstructed += f"- {r}\n"
                            reconstructed += "\n"
                        save_wiki_file_content(doctor_id, filename, reconstructed)
                        st.success("Wiki updated.")
                        st.rerun()
                if c2.button("🗑 Delete", key=f"d_{filename}_{i}"):
                    new_sections = [orig for orig in sections if not (orig['topic'] == s['topic'] and orig['category'] == s['category'])]
                    new_sections.sort(key=lambda x: x['category'])
                    reconstructed = ""
                    last_cat = None
                    for ns in new_sections:
                        if ns['category'] != last_cat:
                            reconstructed += f"\n## {ns['category']}\n"
                            last_cat = ns['category']
                        reconstructed += f"### {ns['topic']}\n"
                        for r in ns['rules']:
                            if isinstance(r, dict):
                                reconstructed += f"- {r['text']}\n"
                                for k, v in r.get('attributes', {}).items(): reconstructed += f"  - {k}: {v}\n"
                            else: reconstructed += f"- {r}\n"
                        reconstructed += "\n"
                    save_wiki_file_content(doctor_id, filename, reconstructed)
                    st.rerun()

    with tab_protocols: render_wiki_editor("clinical_protocols.md", "Protocols")
    with tab_prefs: render_wiki_editor("preferences.md", "Preferences")
    with tab_lit:
        render_guidelines_repository(doctor_id, search_query, col_filter)
        st.divider()
        st.subheader("🔍 Search Clinical Literature (PubMed)")
        lit_query = st.text_input("Find guidelines or studies...", placeholder="e.g. SGLT2 inhibitors heart failure", key="lit_search_input")
        if lit_query:
            results = search_pubmed(lit_query)
            if not results: st.info("No results found on PubMed.")
            for r in results:
                with st.expander(f"📄 {r['title']}"):
                    st.markdown(f"**Source:** {r['source']} ({r['pubdate']})")
                    st.markdown(f"**Authors:** {', '.join(r['authors'])}")
                    st.markdown(f"[View on PubMed]({r['url']})")
                    st.divider()
                    st.markdown("**Add to Wiki with My Interpretation**")
                    cat_lit = st.text_input("Category", value="Clinical Guidelines", key=f"cat_{r['id']}")
                    topic_lit = st.text_input("Topic", value="General", key=f"topic_{r['id']}")
                    decision_lit = st.selectbox("Decision", DECISION_OPTIONS, key=f"dec_{r['id']}", help="Do you adopt this evidence into your practice, defer it, or are you still reviewing it?")
                    notes_lit = st.text_area("Physician Notes", placeholder="e.g., I adopt this for patients with...", key=f"notes_{r['id']}")
                    rational_lit = st.text_area("Rationale", placeholder="Why adopt/defer?", key=f"rat_{r['id']}")
                    if st.button("💾 Save to Wiki", key=f"save_lit_{r['id']}", type="primary"):
                        attrs = {"Key Recommendation": r['title'], "Decision": decision_lit, "Physician Notes": notes_lit, "Rationale": rational_lit, "Source": f"{r['source']} ({r['pubdate']})"}
                        save_guideline(cat_lit, topic_lit, r['title'], attrs, doctor_id)
                        st.success("Guideline added to wiki.")
                        st.rerun()
        st.divider()
        st.subheader("➕ Add External Source (URL or File)")
        with st.form("manual_lit_form"):
            ext_url = st.text_input("Article URL / Link")
            ext_file = st.file_uploader("Upload Article (PDF or Text)", type=["pdf", "txt", "md"])
            ext_title = st.text_input("Article Title / Name")
            ext_cat = st.text_input("Category", value="External Evidence")
            ext_topic = st.text_input("Topic", value="General")
            ext_decision = st.selectbox("Decision", DECISION_OPTIONS, help="Do you adopt this evidence into your practice, defer it, or are you still reviewing it?")
            ext_notes = st.text_area("Physician Notes")
            ext_rat = st.text_area("Rationale")
            submitted = st.form_submit_button("💾 Save External Source to Wiki")
            if submitted:
                if not ext_title: st.error("Please provide a title.")
                else:
                    attrs = {"Decision": ext_decision, "Physician Notes": ext_notes, "Rationale": ext_rat}
                    if ext_url: attrs["URL"] = ext_url
                    if ext_file: attrs["File"] = ext_file.name
                    save_guideline(ext_cat, ext_topic, ext_title, attrs, doctor_id)
                    st.success("External source added to wiki.")
                    st.rerun()

# ---------------------------------------------------------------------------
# Patient Workflows View
# ---------------------------------------------------------------------------

def render_patient_workflows():
    epic, wiki = get_epic(), get_wiki_text()
    try: patient_data = epic.get_patient(patient_id)
    except Exception as e: st.error(f"Could not load patient data: {e}"); st.stop()
    vitals = patient_data.get("vitals", {})
    o2 = vitals.get("o2_saturation", "?")
    o2_class = "vital-chip alert" if isinstance(o2, (int, float)) and o2 < 95 else "vital-chip"
    st.markdown(f"""
<div class="patient-header-card">
  <div class="patient-name">{patient_data.get('name', patient_id)}<span class="patient-meta">{patient_data.get('age', '?')} {patient_data.get('sex', '')}</span></div>
  <div class="chief-complaint">{patient_data.get('chief_complaint', 'Not documented')}</div>
  <div class="vitals-row">
    <div class="{o2_class}">O₂ {o2}%</div>
    <div class="vital-chip">HR {vitals.get('heart_rate', '?')}</div>
    <div class="vital-chip">BP {vitals.get('blood_pressure', '?')}</div>
    <div class="vital-chip">RR {vitals.get('respiratory_rate', '?')}</div>
    <div class="vital-chip">Temp {vitals.get('temperature_celsius', '?')}°C</div>
    <div class="vital-chip">Wt {vitals.get('weight_kg', '?')} kg</div>
  </div>
</div>
""", unsafe_allow_html=True)
    with st.expander("📂 Patient Chart", expanded=True):
        tab_overview, tab_labs, tab_meds, tab_ed, tab_history = st.tabs(["Overview", "Labs", "Medications & Allergies", "ED & Handoff Notes", "Prior Hospitalizations"])
        with tab_overview:
            ov_col1, ov_col2 = st.columns(2)
            with ov_col1:
                st.markdown("**Past Medical History**")
                for item in patient_data.get("pmh", []): st.markdown(f"- {item}")
            with ov_col2:
                st.markdown("**Baseline Functional Status**")
                st.markdown(patient_data.get("baseline_functional_status", "Not documented"))
            st.markdown("**Vitals on Arrival**")
            v, vcol1, vcol2, vcol3, vcol4, vcol5, vcol6 = patient_data.get("vitals", {}), *st.columns(6)
            vcol1.metric("Heart Rate", f"{v.get('heart_rate', '?')} bpm")
            vcol2.metric("Blood Pressure", v.get("blood_pressure", "?"))
            vcol3.metric("Resp Rate", f"{v.get('respiratory_rate', '?')}/min")
            vcol4.metric("O₂ Sat", f"{v.get('o2_saturation', '?')}%")
            vcol5.metric("Temp", f"{v.get('temperature_celsius', '?')} °C")
            vcol6.metric("Weight", f"{v.get('weight_kg', '?')} kg")
        with tab_labs:
            labs = patient_data.get("labs", {})
            if labs:
                rows = [{"Test": k.replace("_", " ").title(), "Value": v} for k, v in labs.items()]
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else: st.caption("No labs on file.")
        with tab_meds:
            med_col1, med_col2 = st.columns(2)
            with med_col1:
                st.markdown("**Current Medications**")
                for med in patient_data.get("current_medications", []): st.markdown(f"- {med}")
            with med_col2:
                st.markdown("**Allergies**")
                for a in patient_data.get("allergies", []): st.markdown(f"- **{a.get('drug', '?')}** — {a.get('reaction', '?')}")
        with tab_ed:
            st.markdown("**ED Physician Assessment**")
            st.markdown(patient_data.get("ed_assessment", "No ED note on file."))
            st.divider()
            st.markdown("**Overnight Handoff Notes**")
            st.markdown(patient_data.get("handoff_notes", "No handoff notes on file."))
        with tab_history:
            for hosp in patient_data.get("prior_hospitalizations", []):
                label = f"{hosp.get('date', '?')} — {hosp.get('reason', '?')}  ({hosp.get('length_of_stay_days', '?')} days)"
                with st.expander(label):
                    st.markdown(f"**Treatment:** {hosp.get('treatment', '—')}")
                    st.markdown(f"**Discharge weight:** {hosp.get('discharge_weight_kg', '?')} kg")
                    st.markdown(f"**Update follows:** {hosp.get('transitional_issues', '—')}")
    patient_ctx = PatientContext.load(patient_id)
    if patient_ctx.workflow_history:
        with st.expander("🕓 Patient History", expanded=False):
            for rec in reversed(patient_ctx.workflow_history):
                date, time = rec.timestamp[:10], rec.timestamp[11:16]
                col_label, col_body = st.columns([1, 4])
                col_label.markdown(f"**{rec.workflow.replace('_', ' ').title()}**\n\n<small>{date} {time} UTC</small>", unsafe_allow_html=True)
                with col_body:
                    st.markdown(rec.summary)
                    if rec.key_findings: st.markdown("**Key findings:** " + " · ".join(rec.key_findings))
                    for issue in rec.open_issues: st.markdown(f"⚠️ {issue}")
                    for res in rec.resolved_issues: st.markdown(f"✅ {res}")
                st.divider()
    st.divider()
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    def run_wf(label: str, workflow_name: str, steps: list, session_fn):
        backend, model = get_backend(llm_provider)
        engine = WorkflowEngine(backend=backend, model=model, wiki=wiki)
        try: session = session_fn()
        except Exception as e: st.error(f"Error loading session: {e}"); return
        ctx = PatientContext.load(patient_id)
        st.session_state["active_workflow"], st.session_state["workflow_outputs"], st.session_state["workflow_complete"] = label, {}, False
        for _k in ("prescription_drafts", "approved_orders", "rx_sent_to_epic", "labs_sent_to_epic", "note_saved", "note_emailed", "show_rx_dialog", "show_labs_dialog", "show_notes_dialog", "episode_wiki_saved"): st.session_state.pop(_k, None)
        with st.status(f"Running {label}...", expanded=True) as status:
            for step_name, output, state in engine.run_steps(steps, session, patient_context=ctx, workflow_name=workflow_name):
                st.write(f"✓ {step_name.replace('_', ' ').title()}")
                if output: st.session_state["workflow_outputs"][step_name] = output.content
            status.update(label=f"{label} complete", state="complete")
        st.session_state["workflow_complete"] = True
        st.rerun()

    if btn_col1.button("🏥 Admit Patient", use_container_width=True): run_wf("Admission", "admission", ADMISSION_STEPS, lambda: epic.build_admission_session(patient_id))
    if btn_col2.button("📋 Review Updates", use_container_width=True):
        st.session_state["show_checkin"] = not st.session_state.get("show_checkin", False)
        if not st.session_state["show_checkin"]:
            for _k in ("checkin_result", "checkin_file_key", "checkin_sample_loaded", "ci_meds_sent", "ci_labs_sent", "ci_updates_saved", "show_ci_meds", "show_ci_labs", "show_ci_updates"): st.session_state.pop(_k, None)
        st.rerun()
    if btn_col3.button("🚪 Discharge Patient", use_container_width=True): run_wf("Discharge", "discharge", DISCHARGE_STEPS, lambda: epic.get_discharge_session(patient_id))
    # "Ready for Review" is shown only once the physician has actually started (and finished)
    # a workflow this session — workflow_complete is set solely by run_wf, never auto-restored.
    if st.session_state.get("workflow_complete"):
        outputs, label, pending_all = st.session_state["workflow_outputs"], st.session_state.get("active_workflow"), get_pending_updates("default")
        st.divider()
        if label == "Admission": render_admission_results(outputs, patient_data.get("name", patient_id), patient_id, pending_all)
        elif label == "Discharge": render_discharge_results(outputs, pending_all, patient_data.get("name", patient_id))
    if st.session_state.get("show_checkin"): st.divider(); render_checkin_inline(patient_id, patient_data, llm_provider, wiki)

# ---------------------------------------------------------------------------
# Check-in UI
# ---------------------------------------------------------------------------

_TREND_ICON = {"worsening": "▲", "improving": "▼", "stable": "→", "new": "★"}
_URGENCY_ICON = {"now": "🔴", "today": "🟡", "routine": "⚪"}

@st.dialog("💊 Medication Changes", width="large")
def _dialog_ci_meds(med_actions: list):
    selected = []
    for i, action in enumerate(med_actions):
        st.markdown(f"{_URGENCY_ICON.get(action.get('urgency', 'routine'), '⚪')} **{action.get('title', '?')}**")
        if action.get("detail"):
            st.caption(humanize_citations(action["detail"]))
            render_content_with_citations(action["detail"], f"ci_med_{i}", chips_only=True)
        edited = st.text_input("Order text", value=action.get("title", ""), key=f"ci_med_edit_{i}", label_visibility="collapsed")
        if st.checkbox("Include in order", value=True, key=f"ci_med_chk_{i}"): selected.append({**action, "title": edited})
        st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["ci_meds_sent"], st.session_state["show_ci_meds"] = True, False
        st.rerun()

@st.dialog("🧪 Lab Orders", width="large")
def _dialog_ci_labs(lab_actions: list):
    if not lab_actions: st.info("No lab orders."); return
    selected = []
    for i, action in enumerate(lab_actions):
        if st.checkbox(f"{_URGENCY_ICON.get(action.get('urgency', 'routine'), '⚪')} **{action.get('title', '?')}**", value=True, key=f"ci_lab_chk_{i}"): selected.append(action)
        if action.get("detail"):
            st.caption(f"  {humanize_citations(action['detail'])}")
            render_content_with_citations(action["detail"], f"ci_lab_{i}", chips_only=True)
    st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["ci_labs_sent"], st.session_state["show_ci_labs"] = True, False
        st.rerun()

@st.dialog("📋 Clinical Updates", width="large")
def _dialog_ci_updates(changes: list, note_actions: list, patient_id: str):
    if changes:
        st.markdown("**What changed:**")
        for c in changes: st.markdown(f"{_TREND_ICON.get(c.get('trend', ''), '•')} **{c.get('finding', '')}** — {humanize_citations(c.get('significance', ''))}")
        st.divider()
    note_lines = [f"- {c.get('finding', '')}: {c.get('significance', '')}" for c in changes] + [f"- {a.get('title', '')}: {a.get('detail', '')}" for a in note_actions]
    note_blob = "\n".join(note_lines)
    edited = st.text_area("Patient file update", value=humanize_citations(note_blob), height=300)
    render_content_with_citations(note_blob, "ci_updates", chips_only=True)
    c1, c2 = st.columns(2)
    if c1.button("Save to Patient File", type="primary", use_container_width=True):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        existing = (_CACHE_DIR / f"{patient_id}_note.md").read_text() if (_CACHE_DIR / f"{patient_id}_note.md").exists() else ""
        (_CACHE_DIR / f"{patient_id}_note.md").write_text(existing + f"\n\n---\n{edited}")
        st.session_state["ci_updates_saved"], st.session_state["show_ci_updates"] = True, False
        st.rerun()
    if c2.button("Email to Patient", use_container_width=True):
        st.session_state["ci_updates_saved"], st.session_state["show_ci_updates"] = True, False
        st.rerun()

def _run_checkin_agent(patient_id: str, llm_provider: str, wiki: str, delta_data: dict):
    backend, model = get_backend(llm_provider)
    agent, ctx = CheckInAgent(backend=backend, model=model), PatientContext.load(patient_id)
    with st.spinner("Analyzing overnight changes..."): output = agent.run({"patient_id": patient_id, "delta_data": delta_data}, wiki=ctx.to_prompt_str() + ("\n\n" + wiki if wiki else ""))
    st.session_state["checkin_result"] = CheckInAgent.parse_result(output.content)
    st.rerun()

def render_checkin_inline(patient_id: str, patient_data: dict, llm_provider: str, wiki: str):
    st.markdown("### Review Updates")
    result = st.session_state.get("checkin_result")
    if not result:
        uploaded = st.file_uploader("Overnight update JSON", type=["json"], label_visibility="collapsed", key="ci_uploader")
        if st.session_state.get("checkin_sample_loaded") and not st.session_state.get("checkin_file_key"):
            _sample_path = Path("sample_overnight_update.json")
            if _sample_path.exists():
                st.session_state["checkin_file_key"] = "sample"
                st.session_state.pop("checkin_sample_loaded", None)
                _run_checkin_agent(patient_id, llm_provider, wiki, json.loads(_sample_path.read_text()))
                return
        if uploaded:
            file_key = f"{uploaded.name}_{uploaded.size}"
            if st.session_state.get("checkin_file_key") != file_key:
                st.session_state["checkin_file_key"] = file_key
                try: _run_checkin_agent(patient_id, llm_provider, wiki, json.loads(uploaded.read()))
                except Exception: st.error("Invalid JSON file.")
        return
    all_actions, changes = result.get("actions", []), result.get("changes", [])
    med_actions = [a for a in all_actions if a.get("type") in ("medication_change", "medication_order")]
    lab_actions = [a for a in all_actions if a.get("type") == "lab_order"]
    note_actions = [a for a in all_actions if a.get("type") == "note_item"]
    update_actions = note_actions + [a for a in all_actions if a.get("type") not in ("medication_change", "medication_order", "lab_order", "note_item")]
    ci_meds_done, ci_labs_done, ci_updates_done = st.session_state.get("ci_meds_sent", False), st.session_state.get("ci_labs_sent", False), st.session_state.get("ci_updates_saved", False)
    meds_sub = "✓ Sent to Epic" if ci_meds_done else (f"{len(med_actions)} change(s)" if med_actions else "No changes")
    labs_sub = "✓ Sent to Epic" if ci_labs_done else (f"{len(lab_actions)} order(s)" if lab_actions else "No orders")
    updates_sub = "✓ Saved" if ci_updates_done else (f"{len(changes)} finding(s), {len(update_actions)} note item(s)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">💊</div><div class="action-card-title">Med Changes</div><div class="action-card-{"done" if ci_meds_done else "sub"}">{meds_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not ci_meds_done else "Review Again", key="ci_open_meds", type="primary" if not ci_meds_done else "secondary", use_container_width=True, disabled=not med_actions): _open_exclusive_dialog("show_ci_meds", _CHECKIN_DIALOGS)
    with c2:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">🧪</div><div class="action-card-title">Labs</div><div class="action-card-{"done" if ci_labs_done else "sub"}">{labs_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not ci_labs_done else "Review Again", key="ci_open_labs", type="primary" if not ci_labs_done else "secondary", use_container_width=True, disabled=not lab_actions): _open_exclusive_dialog("show_ci_labs", _CHECKIN_DIALOGS)
    with c3:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">📋</div><div class="action-card-title">Clinical Updates</div><div class="action-card-{"done" if ci_updates_done else "sub"}">{updates_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Save →" if not ci_updates_done else "Review Again", key="ci_open_updates", type="primary" if not ci_updates_done else "secondary", use_container_width=True): _open_exclusive_dialog("show_ci_updates", _CHECKIN_DIALOGS)
    _active_ci_dialog = next((k for k in _CHECKIN_DIALOGS if st.session_state.get(k)), None)
    if _active_ci_dialog == "show_ci_meds": _dialog_ci_meds(med_actions)
    elif _active_ci_dialog == "show_ci_labs": _dialog_ci_labs(lab_actions)
    elif _active_ci_dialog == "show_ci_updates": _dialog_ci_updates(changes, update_actions, patient_id)
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("Upload new file", type="secondary", key="ci_reset"):
        for _k in ("checkin_result", "checkin_file_key", "ci_meds_sent", "ci_labs_sent", "ci_updates_saved", "show_ci_meds", "show_ci_labs", "show_ci_updates"): st.session_state.pop(_k, None)
        st.rerun()

# ---------------------------------------------------------------------------
# Dialog management
# ---------------------------------------------------------------------------

# Streamlit allows only ONE @st.dialog open per script run. Each group below is
# mutually exclusive; opening one clears its siblings so two flags can never be set
# at once (dismissing a dialog does not auto-reset its flag).
_ADMISSION_DIALOGS = ["show_rx_dialog", "show_labs_dialog", "show_notes_dialog"]
_CHECKIN_DIALOGS = ["show_ci_meds", "show_ci_labs", "show_ci_updates"]

# Agent reasoning outputs surfaced (in workflow order) in the durable admission review.
_ADMISSION_AGENT_NOTES = [
    ("chart_review", "📊 Chart Review"),
    ("lab_interpretation", "🧬 Lab Interpretation"),
    ("ed_note_synthesis", "🚑 ED Note Synthesis"),
    ("consultant_routing", "👥 Consultant Routing"),
    ("safety_check", "⚠️ Safety Check"),
    ("wiki_drift_check", "📚 Wiki Alignment"),
]


def _open_exclusive_dialog(active: str, group: list):
    """Opens one dialog in a group and closes the others."""
    for k in group:
        st.session_state[k] = (k == active)


# ---------------------------------------------------------------------------
# Prescription UI
# ---------------------------------------------------------------------------

def _render_rx_card(idx: int, rx: dict):
    pa_req, pa_pct = rx.get("pa_required", False), rx.get("pa_likelihood_pct")
    badge = (f"🔴 PA Required (~{pa_pct}% approval)" if pa_pct else "🔴 PA Required") if pa_req else "🟢 No PA Required"
    with st.expander(f"**{rx.get('drug_name', '?')}** {rx.get('dose', '')} — {badge}", expanded=True):
        c1, c2, c3 = st.columns(3)
        drug_name = c1.text_input("Drug name", value=rx.get("drug_name", ""), key=f"rx_drug_{idx}")
        dose, route_opts = c2.text_input("Dose", value=rx.get("dose", ""), key=f"rx_dose_{idx}"), ["PO", "IV", "SQ", "inhaled", "topical"]
        route = c3.selectbox("Route", route_opts, index=route_opts.index(rx.get("route", "PO")) if rx.get("route", "PO") in route_opts else 0, key=f"rx_route_{idx}")
        c4, c5, c6 = st.columns(3)
        freq, qty, ref = c4.text_input("Frequency", value=rx.get("frequency", ""), key=f"rx_freq_{idx}"), c5.text_input("Quantity", value=rx.get("quantity", ""), key=f"rx_qty_{idx}"), c6.text_input("Refills", value=rx.get("refills", "0"), key=f"rx_ref_{idx}")
        ind = st.text_input("Indication", value=rx.get("indication", ""), key=f"rx_ind_{idx}")
        st.text_area("Agent notes / monitoring", value=humanize_citations(rx.get("agent_notes", "")), height=80, key=f"rx_notes_{idx}")
        if rx.get("drug_info_summary"): st.caption(f"ℹ️ **Drug info:** {humanize_citations(rx['drug_info_summary'])}")
        if rx.get("pa_notes"): (st.warning if pa_req else st.caption)(f"**PA:** {humanize_citations(rx['pa_notes'])}")
        if rx.get("alternatives"): st.caption("**Alternatives:** " + " · ".join(rx["alternatives"]))
        _rx_cite_text = " ".join([rx.get("agent_notes", ""), rx.get("drug_info_summary", ""), rx.get("pa_notes", "")])
        render_content_with_citations(_rx_cite_text, f"rx_{idx}", chips_only=True)
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("✓ Approve", key=f"approve_{idx}", type="primary"):
            st.session_state["approved_orders"].append({"_idx": idx, "drug_name": drug_name, "dose": dose, "route": route, "frequency": freq, "quantity": qty, "refills": ref, "indication": ind, "status": "pending_pharmacy"})
            st.rerun()
        if b2.button("✗ Discard", key=f"discard_{idx}"): st.session_state["approved_orders"].append({"_idx": idx, "status": "discarded"}); st.rerun()

# ---------------------------------------------------------------------------
# Admission action dialogs
# ---------------------------------------------------------------------------

@st.dialog("💊 Prescriptions", width="large")
def _dialog_prescriptions():
    drafts, approved_idxs = st.session_state.get("prescription_drafts", []), {o["_idx"] for o in st.session_state.get("approved_orders", [])}
    pending = [i for i in range(len(drafts)) if i not in approved_idxs]
    if not drafts: st.info("No prescription drafts."); return
    if pending: st.caption(f"{len(pending)} order(s) pending · Edit any field, then approve.")
    else: st.success("All orders reviewed.")
    for idx in pending: _render_rx_card(idx, drafts[idx])
    pharmacy_orders = [o for o in st.session_state.get("approved_orders", []) if o.get("status") == "pending_pharmacy"]
    if pharmacy_orders:
        st.divider(); st.markdown(f"**{len(pharmacy_orders)} order(s) approved — ready to send**")
        for o in pharmacy_orders: st.markdown(f"- {o['drug_name']} {o['dose']} {o['route']} {o['frequency']}")
        if st.button("Send All to Epic", type="primary", use_container_width=True):
            st.session_state["rx_sent_to_epic"], st.session_state["show_rx_dialog"] = True, False
            st.rerun()
    if st.button("🔄 Re-draft", type="secondary"): st.session_state["prescription_drafts"], st.session_state["approved_orders"], st.session_state["show_rx_dialog"] = [], [], False; st.rerun()

@st.dialog("🧪 Lab Orders", width="large")
def _dialog_labs(lab_actions: list):
    if not lab_actions: st.info("No lab orders extracted."); return
    st.caption("Select orders to send."); st.divider(); selected, icon_map = [], {"now": "🔴", "today": "🟡", "routine": "⚪"}
    for i, a in enumerate(lab_actions):
        if st.checkbox(f"{icon_map.get(a.get('urgency', 'routine'), '⚪')} **{a.get('title', '?')}**", value=True, key=f"lab_chk_{i}"): selected.append(a)
        if a.get("detail"):
            st.caption(f"  {humanize_citations(a['detail'])}")
            render_content_with_citations(a["detail"], f"lab_{i}", chips_only=True)
    st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["labs_sent_to_epic"], st.session_state["show_labs_dialog"] = True, False
        st.rerun()

@st.dialog("📋 Admission Note", width="large")
def _dialog_notes(note_text: str, patient_id: str):
    edited = st.text_area("", value=humanize_citations(note_text), height=450, label_visibility="collapsed", key="dialog_note_ta")
    render_content_with_citations(note_text, "adm_note", chips_only=True)
    c1, c2 = st.columns(2)
    if c1.button("Save to Patient File", type="primary", use_container_width=True):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True); (_CACHE_DIR / f"{patient_id}_note.md").write_text(edited)
        st.session_state["note_saved"], st.session_state["show_notes_dialog"] = True, False
        st.rerun()
    if c2.button("Email to Patient", use_container_width=True):
        st.session_state["note_emailed"], st.session_state["show_notes_dialog"] = True, False
        st.rerun()

# ---------------------------------------------------------------------------
# Results Rendering
# ---------------------------------------------------------------------------

def render_admission_results(outputs: dict, patient_name: str, patient_id: str, pending_all: list):
    from agents.admission.prescription import PrescriptionDraftAgent as _PxAgent
    if "prescription_draft" in outputs and not st.session_state.get("prescription_drafts"):
        rxs = _PxAgent.parse_prescriptions(outputs["prescription_draft"])
        if rxs:
            st.session_state["prescription_drafts"] = rxs
            if "approved_orders" not in st.session_state:
                st.session_state["approved_orders"] = []
    rxs, approved_idxs = st.session_state.get("prescription_drafts", []), {o["_idx"] for o in st.session_state.get("approved_orders", [])}
    rx_pending = len([i for i in range(len(rxs)) if i not in approved_idxs])
    lab_actions = [a for a in ActionExtractionAgent.parse_actions(outputs.get("action_extraction", "")) if a.get("type") == "lab_order"]
    note_text = outputs.get("note_draft", "")
    st.markdown("### Ready for Review"); c1, c2, c3 = st.columns(3)
    rx_done, labs_done, note_done = st.session_state.get("rx_sent_to_epic", False), st.session_state.get("labs_sent_to_epic", False), st.session_state.get("note_saved", False) or st.session_state.get("note_emailed", False)
    rx_sub, lab_sub, note_sub = "✓ Sent to Epic" if rx_done else (f"{rx_pending} medication(s)" if rx_pending else "All approved"), "✓ Sent to Epic" if labs_done else (f"{len(lab_actions)} lab order(s)" if lab_actions else "No orders"), "✓ Saved" if note_done else "Admission note ready"
    with c1:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">💊</div><div class="action-card-title">Prescriptions</div><div class="action-card-{"done" if rx_done else "sub"}">{rx_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not rx_done else "Review Again", key="open_rx", use_container_width=True, type="primary" if not rx_done else "secondary", disabled=not rxs): _open_exclusive_dialog("show_rx_dialog", _ADMISSION_DIALOGS)
    with c2:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">🧪</div><div class="action-card-title">Labs</div><div class="action-card-{"done" if labs_done else "sub"}">{lab_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not labs_done else "Review Again", key="open_labs", use_container_width=True, type="primary" if not labs_done else "secondary", disabled=not lab_actions): _open_exclusive_dialog("show_labs_dialog", _ADMISSION_DIALOGS)
    with c3:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">📋</div><div class="action-card-title">Admission Note</div><div class="action-card-{"done" if note_done else "sub"}">{note_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Sign →" if not note_done else "Review Again", key="open_note", use_container_width=True, type="primary" if not note_done else "secondary", disabled=not note_text): _open_exclusive_dialog("show_notes_dialog", _ADMISSION_DIALOGS)
    _active_dialog = next((k for k in _ADMISSION_DIALOGS if st.session_state.get(k)), None)
    if _active_dialog == "show_rx_dialog": _dialog_prescriptions()
    elif _active_dialog == "show_labs_dialog": _dialog_labs(lab_actions)
    elif _active_dialog == "show_notes_dialog": _dialog_notes(note_text, patient_id)

    # Durable record of every agent's reasoning so the physician can review the full
    # analysis after completion (the live run trace is gone once the workflow reruns).
    st.divider()
    st.markdown("### 🔍 Agent Notes & Analysis")
    st.caption("Review each agent's reasoning and recommendations. Source chips link to the guideline or protocol behind each suggestion.")
    for step_name, title in _ADMISSION_AGENT_NOTES:
        if outputs.get(step_name):
            with st.expander(title, expanded=False):
                render_content_with_citations(outputs[step_name], f"adm_{step_name}")

def _render_episode_learnings(pending_all: list, patient_name: str, doctor_id: str = "default"):
    if not pending_all: return
    if not st.session_state.get("episode_wiki_saved"):
        protocols = [{"category": p["category"], "topic": p["header"], "rules": p["rules"] if "rules" in p else p["content"].split("\n")} for p in pending_all if p.get("type") == "protocol"]
        preferences = [{"category": p["category"], "topic": p["header"], "rules": p["rules"] if "rules" in p else p["content"].split("\n")} for p in pending_all if p.get("type") != "protocol"]
        update_wiki(doctor_id, protocols, preferences)
        for idx in range(len(pending_all) - 1, -1, -1): remove_pending_update(doctor_id, idx)
        st.session_state["episode_wiki_saved"] = True
    chips_html = "".join([f'<div class="insight-row"><span class="insight-badge {"protocol" if item.get("type")=="protocol" else "preference"}">{"Protocol" if item.get("type")=="protocol" else "Preference"}</span><div><div class="insight-header">{item.get("header", "")}</div><div class="insight-category">{item.get("category", "")}</div></div></div>' for item in pending_all])
    st.markdown(f'<div class="insights-card"><div class="insights-title">✦ Wiki updated from {patient_name}\'s episode</div><div class="insights-sub">{len(pending_all)} insight(s) added automatically.</div><div class="insights-grid">{chips_html}</div></div>', unsafe_allow_html=True)

def render_discharge_results(outputs: dict, pending_all: list, patient_name: str = ""):
    if "discharge_summary" in outputs:
        st.markdown("### Discharge Summary"); st.text_area("", value=humanize_citations(outputs["discharge_summary"]), height=300, key="dc_summary_ta", label_visibility="collapsed")
        render_content_with_citations(outputs["discharge_summary"], "dc_summary", chips_only=True); st.divider()
    if "patient_instructions" in outputs:
        st.markdown("### Patient Instructions"); st.text_area("", value=humanize_citations(outputs["patient_instructions"]), height=250, key="dc_instructions_ta", label_visibility="collapsed")
        render_content_with_citations(outputs["patient_instructions"], "dc_instructions", chips_only=True); st.divider()
    if "discharge_checklist" in outputs: st.markdown("### Sign-off Checklist"); render_content_with_citations(outputs["discharge_checklist"], "dc_checklist"); st.divider()
    if "safety_check" in outputs:
        with st.expander("Safety Check", expanded=False): render_content_with_citations(outputs["safety_check"], "dc_safety")
    if pending_all: st.divider(); _render_episode_learnings(pending_all, patient_name or "this patient")

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

if app_mode == "Patient Workflows" and st.session_state.get("active_citation"):
    col_main, col_right = st.columns([3, 1])
else:
    col_main, col_right = st.container(), None

with col_main:
    if app_mode == "Patient Workflows": render_patient_workflows()
    else: render_wiki_management()

if col_right:
    with col_right: render_wiki_reference_card("default")
