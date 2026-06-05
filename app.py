"""
Cardio — Streamlit frontend

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
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

from tools.epic import EpicClient
from wiki.loader import (
    load_wiki, get_pending_updates, remove_pending_update,
    update_wiki, get_wiki_file_content, save_wiki_file_content,
    get_wiki_insight, parse_wiki_sections, generate_id, ADDED_KEY
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
    page_title="Cardio",
    page_icon="🫀",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap');

/* ── Body: San Francisco (Apple system font) ── */
body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
button, input, textarea, select {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
}

/* ── Display headings: Cormorant ── */
h1, h2, .patient-name, .action-card-title,
.insights-title, .kanban-header,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2 {
    font-family: "Cormorant", Georgia, "Times New Roman", serif !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
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
    padding: 0.75rem 2.5rem 2rem;
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
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.10) !important; }

/* ── Sidebar nav items: flat, icon-style ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.6) !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0 !important;
    padding: 0.5rem 0.85rem !important;
    transition: background 0.15s, color 0.15s !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.08) !important;
    color: rgba(255,255,255,0.95) !important;
    transform: none !important;
}
/* Sidebar download button (e.g. "Sample check-in file"): glass pill instead of
   Streamlit's default light button, which otherwise reads as a white box. */
[data-testid="stSidebar"] .stDownloadButton > button {
    background: rgba(255,255,255,0.10) !important;
    border: 1px solid rgba(255,255,255,0.22) !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.9) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    box-shadow: none !important;
    transition: background 0.15s, color 0.15s !important;
}
[data-testid="stSidebar"] .stDownloadButton > button:hover {
    background: rgba(255,255,255,0.18) !important;
    border-color: rgba(255,255,255,0.35) !important;
    color: #FFFFFF !important;
    transform: none !important;
}
/* Selected nav item */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(255,255,255,0.13) !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-left: 2.5px solid rgba(255,255,255,0.7) !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: rgba(255,255,255,0.18) !important;
    transform: none !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.14) !important;
    border-color: rgba(255,255,255,0.30) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"]:hover > div {
    background: rgba(255,255,255,0.22) !important;
    border-color: rgba(255,255,255,0.45) !important;
}
/* Selected value text + dropdown arrow: keep legible on the dark glass */
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="select"] svg {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}

/* ── Typography ─────────────────────────────────────── */
h2 {
    font-size: 2rem !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em !important;
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
.stButton > button {
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
    margin-bottom: 0.35rem;
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
    margin-bottom: 0.6rem;
}
.patient-header-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 45%;
    background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 100%);
    border-radius: 24px 24px 0 0; pointer-events: none;
}
.patient-name {
    font-family: "Cormorant", Georgia, serif;
    font-size: 2.1rem; font-weight: 500; letter-spacing: -0.01em; color: #1C1C1E;
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

/* ── Kanban dashboard ────────────────────────────────── */
.kanban-col {
    background: rgba(255,255,255,0.28);
    border: 1px solid rgba(255,255,255,0.55);
    border-radius: 22px;
    padding: 1rem 0.85rem 0.5rem;
    min-height: 200px;
}
.kanban-header {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: rgba(60,60,67,0.45);
    display: flex; align-items: center; gap: 0.45rem;
    margin-bottom: 0.8rem;
}
.kanban-count {
    background: rgba(60,60,67,0.1); border-radius: 980px;
    padding: 0.08rem 0.45rem; font-size: 0.65rem; font-weight: 700; color: rgba(60,60,67,0.55);
}
.pt-card {
    background: rgba(255,255,255,0.72);
    border: 1px solid rgba(255,255,255,0.9);
    border-radius: 16px; padding: 0.85rem 1rem 0.6rem;
    margin-bottom: 0.55rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.95);
}
.pt-name { font-size: 0.93rem; font-weight: 700; color: #1C1C1E; letter-spacing: -0.01em; }
.pt-meta { font-size: 0.73rem; color: rgba(60,60,67,0.45); margin-left: 0.3rem; }
.pt-complaint {
    font-size: 0.76rem; color: rgba(60,60,67,0.58); margin: 0.2rem 0 0.55rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.pt-vitals { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-bottom: 0.55rem; }
.pt-chip {
    background: rgba(60,60,67,0.07); border-radius: 980px;
    font-size: 0.67rem; font-weight: 600; padding: 0.1rem 0.45rem; color: #3C3C43;
}
.pt-chip.alert { background: rgba(255,59,48,0.1); color: #C0392B; }
.pt-date { font-size: 0.68rem; color: rgba(60,60,67,0.38); margin-bottom: 0.4rem; }
.kanban-empty { font-size: 0.78rem; color: rgba(60,60,67,0.3); text-align: center; padding: 1.5rem 0; }

/* ── Settings gear popover trigger (borderless icon) ──── */
.st-key-settingsgear [data-testid="stPopover"] > button,
.st-key-settingsgear [data-testid="stPopover"] > div > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0.1rem 0.3rem !important;
    color: rgba(60,60,67,0.55) !important;
}
.st-key-settingsgear [data-testid="stPopover"] button:hover {
    background: transparent !important;
    color: #3C3C43 !important;
}
/* The emoji glyph size is driven by the label element's font-size, not the
   button's — bump it 20% there. */
.st-key-settingsgear [data-testid="stPopover"] button p,
.st-key-settingsgear [data-testid="stPopover"] button div,
.st-key-settingsgear [data-testid="stPopover"] button span {
    font-size: 1.12em !important;
}

/* ── Wiki citation chips: small, unobtrusive pill tags ─── */
[class*="st-key-wikicite"] [data-testid="stPopover"] button {
    background: rgba(0,122,255,0.07) !important;
    border: 1px solid rgba(0,122,255,0.18) !important;
    border-radius: 980px !important;
    color: #0056D6 !important;
    font-weight: 500 !important;
    font-size: 0.72rem !important;
    line-height: 1.25 !important;
    padding: 0.12rem 0.6rem !important;
    min-height: 0 !important;
    box-shadow: none !important;
}
[class*="st-key-wikicite"] [data-testid="stPopover"] button:hover {
    background: rgba(0,122,255,0.14) !important;
    border-color: rgba(0,122,255,0.32) !important;
    color: #0056D6 !important;
    transform: none !important;
}
[class*="st-key-wikicite"] [data-testid="stPopover"] button p {
    font-size: 0.72rem !important;
}
[class*="st-key-wikicite"] .stCaption,
[class*="st-key-wikicite"] [data-testid="stCaptionContainer"] {
    margin-bottom: 0.1rem !important;
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

def _save_workflow_cache(patient_id: str, label: str, workflow_name: str, outputs: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{patient_id}_workflow_cache.json"
    path.write_text(json.dumps({"label": label, "workflow_name": workflow_name, "outputs": outputs}, indent=2))

def _load_workflow_cache(patient_id: str) -> tuple:
    path = _CACHE_DIR / f"{patient_id}_workflow_cache.json"
    if not path.exists():
        return None, None, {}
    try:
        data = json.loads(path.read_text())
        return data.get("label"), data.get("workflow_name"), data.get("outputs", {})
    except Exception:
        return None, None, {}

# ---------------------------------------------------------------------------
# Action state persistence — survives page refreshes
# ---------------------------------------------------------------------------

_ACTION_STATE_KEYS = [
    # Admission card done-states
    "rx_sent_to_epic", "labs_sent_to_epic", "note_saved", "note_emailed",
    # Discharge card done-states
    "dc_summary_done", "dc_instructions_done", "dc_checklist_done", "dc_safety_done",
    # Check-in card done-states
    "ci_meds_sent", "ci_labs_sent", "ci_updates_saved",
    # Prescription draft state (so cards render correctly after refresh)
    "prescription_drafts", "approved_orders",
    # Check-in result (so panel shows results after refresh)
    "checkin_result",
]


def _save_action_states(patient_id: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    states = {k: st.session_state[k] for k in _ACTION_STATE_KEYS if k in st.session_state}
    path = _CACHE_DIR / f"{patient_id}_action_states.json"
    path.write_text(json.dumps(states, indent=2))


def _load_action_states(patient_id: str) -> None:
    path = _CACHE_DIR / f"{patient_id}_action_states.json"
    if not path.exists():
        return
    try:
        states = json.loads(path.read_text())
        for k, v in states.items():
            if k in _ACTION_STATE_KEYS and k not in st.session_state:
                st.session_state[k] = v
    except Exception:
        pass


def _clear_action_states(patient_id: str) -> None:
    """Called when a new workflow run starts — resets both disk and session."""
    for k in _ACTION_STATE_KEYS:
        st.session_state.pop(k, None)
    path = _CACHE_DIR / f"{patient_id}_action_states.json"
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Patient registry — dynamic list that survives across sessions
# ---------------------------------------------------------------------------

_REGISTRY_PATH = _CACHE_DIR / "patients_registry.json"
_FIXTURES_DIR  = Path("tests/fixtures")

_DEFAULT_REGISTRY = [
    {"id": "TEST-001", "name": "John Smith",       "dx": "CHF exacerbation"},
    {"id": "TEST-002", "name": "Maria Chen",        "dx": "DKA / new T2DM"},
    {"id": "TEST-003", "name": "James Washington",  "dx": "COPD exacerbation"},
    {"id": "TEST-004", "name": "Sarah O'Brien",     "dx": "NSTEMI"},
]


def _load_patient_registry() -> list[dict]:
    if not _REGISTRY_PATH.exists():
        return _DEFAULT_REGISTRY.copy()
    try:
        return json.loads(_REGISTRY_PATH.read_text())
    except Exception:
        return _DEFAULT_REGISTRY.copy()


def _save_patient_registry(registry: list[dict]) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def _next_patient_id(registry: list[dict]) -> str:
    nums = [int(p["id"].split("-")[1]) for p in registry if p["id"].startswith("PT-")]
    return f"PT-{(max(nums, default=0) + 1):03d}"


def _convert_intake(intake: dict, patient_id: str) -> dict:
    """Maps the simple intake JSON format to the full patient fixture schema."""
    return {
        "patient_id": patient_id,
        "name":       intake.get("name", "Unknown"),
        "age":        intake.get("age", 0),
        "sex":        intake.get("sex", ""),
        "insurance":  intake.get("insurance", ""),
        "chief_complaint": intake.get("chief_complaint", ""),
        "vitals":     intake.get("vitals", {}),
        "labs":       intake.get("labs", {}),
        "pmh":        intake.get("past_medical_history", []),
        "current_medications": intake.get("current_medications", []),
        "allergies":  intake.get("allergies", []),
        "baseline_functional_status": intake.get("baseline_functional_status", "Not documented"),
        "ed_assessment":  intake.get("ed_assessment", ""),
        "handoff_notes":  intake.get("handoff_notes", ""),
        "imaging":    intake.get("imaging", []),
        "prior_hospitalizations": intake.get("prior_hospitalizations", []),
    }


def _register_patient(intake: dict, patient_id: str) -> None:
    """Saves fixture file + adds patient to registry."""
    fixture = _convert_intake(intake, patient_id)
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (_FIXTURES_DIR / f"patient_{patient_id}.json").write_text(json.dumps(fixture, indent=2))
    registry = _load_patient_registry()
    dx = intake.get("chief_complaint", "")[:40] + ("…" if len(intake.get("chief_complaint","")) > 40 else "")
    registry.append({"id": patient_id, "name": intake.get("name", "Unknown"), "dx": dx})
    _save_patient_registry(registry)


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

def get_epic() -> EpicClient:
    return EpicClient(
        base_url=os.getenv("EPIC_BASE_URL", ""),
        access_token=os.getenv("EPIC_ACCESS_TOKEN", ""),
    )

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


def _strip_citations(text: str) -> str:
    """Removes raw [WikiID: xxx] tokens entirely, leaving clean prose.

    Used for editable / Epic-bound text (notes, discharge summaries, patient instructions)
    where citations belong in a separate Sources section, not inline."""
    if not text:
        return text
    return re.sub(r'[ \t]{2,}', ' ', _CITATION_PATTERN.sub('', text)).strip()


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


def _format_added(date_str: str) -> str:
    """Formats an Added date with a relative age so the physician sees how old a reference is."""
    try:
        d = date.fromisoformat(date_str.strip())
    except Exception:
        return f"🗓 Added {date_str}"
    days = (date.today() - d).days
    if days <= 0:
        age = "today"
    elif days < 31:
        age = f"{days} day{'s' if days != 1 else ''} ago"
    elif days < 365:
        months = days // 30
        age = f"{months} mo ago"
    else:
        years = days // 365
        age = f"{years} yr ago"
    return f"🗓 Added {d.isoformat()} · {age}"


def _render_decision_badge(decision: str):
    """Renders a colored badge reflecting the physician's adopt/defer decision."""
    d = (decision or "").strip().lower()
    if d == "adopted":
        st.success("✅ Adopted")
    elif d == "deferred":
        st.warning("⏸️ Deferred")
    else:
        st.info("🔍 Under review")


def _render_related_literature(insight: dict, self_id: str, doctor_id: str):
    """Shows clinical literature/guidelines embedded within a wiki note, if any."""
    related = _related_literature(insight, self_id, doctor_id)
    if not related:
        return
    st.divider()
    st.markdown("**📚 Related literature**")
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
    # Always surface recency so the physician knows how current this guidance is.
    st.caption(_format_added(attrs[ADDED_KEY]) if attrs.get(ADDED_KEY) else "🗓 Date not recorded")
    _render_related_literature(insight, insight_id, doctor_id)


def render_citation_chips(text: str, key_suffix: str, doctor_id: str = "default", caption: str = "📚 Sources from your wiki:"):
    """Renders only the small wiki source chips for any WikiIDs found in `text`.

    Use this to place citations under a section (or at the bottom of a dialog) without
    repeating the body text. Each chip names the guideline/protocol (topic · source) and
    reveals the full rule, adopt/defer decision, the date it was added to the wiki, and the
    physician's interpretation inline via st.popover. Pass caption="" to omit the header."""
    if not text: return
    ids = _extract_citation_ids(text)
    if not ids:
        return
    # Keyed container so the compact citation-chip CSS (.st-key-wikicite…) applies here only.
    with st.container(key=f"wikicite_{key_suffix}"):
        if caption:
            st.caption(caption)
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


def render_content_with_citations(text: str, key_suffix: str, doctor_id: str = "default", chips_only: bool = False):
    """Renders agent text with WikiID tokens stripped, then the small source chips beneath it.

    chips_only=True skips the body text — use it when the same text is shown in an adjacent
    editable widget. The chips themselves are delegated to render_citation_chips()."""
    if not text: return
    if not chips_only:
        st.markdown(_strip_citations(text))
    render_citation_chips(text, key_suffix, doctor_id)


def render_wiki_reference_card(doctor_id: str = "default"):
    """Renders the cited wiki quote in the sticky panel (fallback when popovers unavailable)."""
    insight_id = st.session_state.get("active_citation")
    if not insight_id: return
    insight = get_wiki_insight(doctor_id, insight_id)
    if insight:
        st.markdown(f'<div class="wiki-ref-box">', unsafe_allow_html=True)
        st.markdown(f'<div class="wiki-ref-header">📚 Wiki Reference</div>', unsafe_allow_html=True)
        _render_citation_detail(insight, insight_id, doctor_id)
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

# ---------------------------------------------------------------------------
# Navigation state (replaces st.radio so dashboard can set it programmatically)
# ---------------------------------------------------------------------------
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "Dashboard"
# Let dashboard "Open →" buttons drive navigation
if st.session_state.get("_nav_request"):
    st.session_state["app_mode"] = st.session_state.pop("_nav_request")

app_mode = st.session_state["app_mode"]

with st.sidebar:
    st.markdown("""
<div style="padding:0.75rem 0.85rem 1rem; font-size:2.2rem; font-weight:500;
     letter-spacing:-0.01em; color:#fff;
     font-family:'Cormorant',Georgia,serif;">Cardio</div>
""", unsafe_allow_html=True)

    # ── Main nav ──────────────────────────────────────────────────────────────
    _nav_items = [
        ("📊", "Dashboard"),
        ("👤", "Patient Workflows"),
        ("📖", "Wiki Management"),
    ]
    for icon, label in _nav_items:
        active = app_mode == label
        if st.button(f"{icon}   {label}", key=f"nav_{label}",
                     use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state["app_mode"] = label
            st.rerun()

    st.divider()

    # ── Patient Workflows controls ────────────────────────────────────────────
    if app_mode == "Patient Workflows":
        _registry = _load_patient_registry()
        _id_to_name = {p["id"]: p["name"] for p in _registry}
        patient_id = st.selectbox(
            "Patient",
            options=[p["id"] for p in _registry],
            format_func=lambda pid: _id_to_name.get(pid, pid),
            key="patient_selectbox",
        )

        if st.session_state.get("_active_patient_id") != patient_id:
            for _k in _ACTION_STATE_KEYS + ["workflow_complete", "workflow_outputs",
                                             "active_workflow", "open_dialog",
                                             "episode_wiki_saved", "show_checkin"]:
                st.session_state.pop(_k, None)
            st.session_state["_active_patient_id"] = patient_id

        patient_ctx = PatientContext.load(patient_id)
        if patient_ctx.workflow_history:
            st.divider()
            for rec in patient_ctx.workflow_history:
                st.markdown(f"<span style='font-size:0.75rem;color:rgba(255,255,255,0.5)'>✓ {rec.workflow.replace('_',' ').title()} · {rec.timestamp[:10]}</span>", unsafe_allow_html=True)
            if st.button("Reset context", use_container_width=True):
                PatientContext.clear(patient_id)
                _clear_action_states(patient_id)
                # Also drop the in-session keys that drive the "Ready for Review" section,
                # otherwise it keeps rendering from stale session state after the rerun.
                for _k in ["workflow_complete", "workflow_outputs", "active_workflow",
                           "open_dialog", "episode_wiki_saved", "show_checkin"]:
                    st.session_state.pop(_k, None)
                wf_cache = _CACHE_DIR / f"{patient_id}_workflow_cache.json"
                if wf_cache.exists(): wf_cache.unlink()
                st.rerun()

        _sample_path = Path("sample_overnight_update.json")
        if _sample_path.exists():
            st.divider()
            st.download_button("⬇ Sample check-in file", data=_sample_path.read_bytes(),
                               file_name="sample_overnight_update.json", mime="application/json",
                               use_container_width=True)
            if st.button("Use sample →", use_container_width=True):
                st.session_state["checkin_sample_loaded"] = True
                st.session_state["show_checkin"] = True
                st.rerun()

    # ── Recent Patients ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("<span style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
                "letter-spacing:0.09em;color:rgba(255,255,255,0.35);padding:0 0.85rem'>"
                "Recent Patients</span>", unsafe_allow_html=True)
    for _pt in _load_patient_registry():
        _pid, _name, _dx = _pt["id"], _pt["name"], _pt.get("dx", "")
        _ctx = PatientContext.load(_pid)
        _opacity = "1" if _ctx.workflow_history else "0.35"
        st.markdown(
            f"<div style='padding:0 0.85rem 0.05rem;opacity:{_opacity}'>"
            f"<span style='font-size:0.8rem;font-weight:600;color:rgba(255,255,255,0.85)'>{_name}</span><br>"
            f"<span style='font-size:0.7rem;color:rgba(255,255,255,0.4)'>{_dx}</span>"
            f"</div>", unsafe_allow_html=True
        )
        if st.button("→", key=f"recent_{_pid}", use_container_width=True):
            st.session_state["patient_selectbox"] = _pid
            st.session_state["app_mode"] = "Patient Workflows"
            st.rerun()


# ---------------------------------------------------------------------------
# Wiki Management View
# ---------------------------------------------------------------------------

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

def render_saved_guidelines(doctor_id: str = "default"):
    """Lists every saved guideline / external source from guidelines.md as a card, so a
    physician can see what they added (and remove it) right where they add new sources."""
    sections = parse_wiki_sections(get_wiki_file_content(doctor_id, "guidelines.md"))
    if not sections or not any(s["rules"] for s in sections):
        st.caption("No saved literature or external sources yet. Add one below.")
        return
    current_cat = None
    for s in sections:
        for r in s["rules"]:
            attrs = r.get("attributes", {})
            rid = generate_id(s["category"], s["topic"], r["text"])
            if s["category"] != current_cat:
                st.markdown(f"#### 📁 {s['category']}")
                current_cat = s["category"]
            with st.container(border=True):
                st.markdown(f"**{s['topic']}** — {r['text']}")
                if attrs.get("Decision"): _render_decision_badge(attrs["Decision"])
                if attrs.get("Key Recommendation"): st.markdown(f"**Key Recommendation:** {attrs['Key Recommendation']}")
                if attrs.get("Source"): st.caption(f"Source: {attrs['Source']}")
                if attrs.get("URL"): st.markdown(f"[View source]({attrs['URL']})")
                if attrs.get("File"): st.caption(f"📎 {attrs['File']}")
                if attrs.get("Physician Notes"): st.markdown(f"**My Interpretation:** {attrs['Physician Notes']}")
                if attrs.get("Rationale"): st.markdown(f"**Rationale:** {attrs['Rationale']}")
                st.caption(_format_added(attrs[ADDED_KEY]) if attrs.get(ADDED_KEY) else "🗓 Date not recorded")

                with st.expander("✏️ Edit", expanded=False):
                    with st.form(key=f"ed_gl_form_{rid}"):
                        ec1, ec2 = st.columns(2)
                        e_cat = ec1.text_input("Category", value=s["category"], key=f"ed_cat_{rid}")
                        e_topic = ec2.text_input("Topic", value=s["topic"], key=f"ed_topic_{rid}")
                        e_text = st.text_input("Title / Source", value=r["text"], key=f"ed_text_{rid}")
                        e_keyrec = st.text_input("Key Recommendation", value=attrs.get("Key Recommendation", ""), key=f"ed_keyrec_{rid}")
                        e_src = st.text_input("Source", value=attrs.get("Source", ""), key=f"ed_src_{rid}")
                        e_url = st.text_input("URL", value=attrs.get("URL", ""), key=f"ed_url_{rid}")
                        _dec_opts = ["Not set", "Adopted", "Deferred", "Under review"]
                        _cur_dec = (attrs.get("Decision") or "").strip()
                        _dec_idx = next((i for i, o in enumerate(_dec_opts) if o.lower() == _cur_dec.lower()), 0)
                        e_dec = st.selectbox("Decision", _dec_opts, index=_dec_idx, key=f"ed_dec_{rid}")
                        e_notes = st.text_area("My Interpretation (Physician Notes)", value=attrs.get("Physician Notes", ""), key=f"ed_notes_{rid}")
                        e_rat = st.text_area("Rationale", value=attrs.get("Rationale", ""), key=f"ed_rat_{rid}")
                        if st.form_submit_button("💾 Save changes", type="primary"):
                            if not e_text.strip():
                                st.error("Title / Source cannot be empty.")
                            else:
                                merged = {}
                                if e_keyrec.strip(): merged["Key Recommendation"] = e_keyrec.strip()
                                if e_src.strip(): merged["Source"] = e_src.strip()
                                if e_url.strip(): merged["URL"] = e_url.strip()
                                if e_dec != "Not set": merged["Decision"] = e_dec
                                if e_notes.strip(): merged["Physician Notes"] = e_notes.strip()
                                if e_rat.strip(): merged["Rationale"] = e_rat.strip()
                                if attrs.get("File"): merged["File"] = attrs["File"]
                                # Preserve the original added date through the edit.
                                if attrs.get(ADDED_KEY): merged[ADDED_KEY] = attrs[ADDED_KEY]
                                # Delete-then-save so cleared fields are dropped and any
                                # category/topic/title change moves the entry cleanly.
                                delete_guideline(s["category"], s["topic"], r["text"], doctor_id)
                                save_guideline(e_cat.strip() or s["category"], e_topic.strip() or s["topic"],
                                               e_text.strip(), merged, doctor_id)
                                st.success("Guideline updated.")
                                st.rerun()
                if st.button("🗑 Delete", key=f"del_gl_{rid}"):
                    delete_guideline(s["category"], s["topic"], r["text"], doctor_id)
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
        # Group topics under their category so each outer category is a single collapsible
        # panel that starts closed. (Streamlit forbids nesting expanders, so the topics
        # inside are bordered containers rather than their own expanders.)
        cats_in_order, cat_map = [], {}
        for i, s in enumerate(filtered):
            if s['category'] not in cat_map:
                cat_map[s['category']] = []
                cats_in_order.append(s['category'])
            cat_map[s['category']].append((i, s))
        for cat in cats_in_order:
            members = cat_map[cat]
            # Auto-open while searching so matches aren't hidden; otherwise start closed.
            with st.expander(f"📁 {cat}  ·  {len(members)} topic(s)", expanded=bool(search_query)):
                for i, s in members:
                    with st.container(border=True):
                        st.markdown(f"**{s['topic']}**")
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
        st.subheader("📚 My Saved Literature & External Sources")
        render_saved_guidelines(doctor_id)
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
                    notes_lit = st.text_area("Physician Notes", placeholder="e.g., I adopt this for patients with...", key=f"notes_{r['id']}")
                    rational_lit = st.text_area("Rationale", placeholder="Why adopt/defer?", key=f"rat_{r['id']}")
                    if st.button("💾 Save to Wiki", key=f"save_lit_{r['id']}", type="primary"):
                        attrs = {"Key Recommendation": r['title'], "Physician Notes": notes_lit, "Rationale": rational_lit, "Source": f"{r['source']} ({r['pubdate']})"}
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
            ext_notes = st.text_area("Physician Notes")
            ext_rat = st.text_area("Rationale")
            submitted = st.form_submit_button("💾 Save External Source to Wiki")
            if submitted:
                if not ext_title: st.error("Please provide a title.")
                else:
                    attrs = {"Physician Notes": ext_notes, "Rationale": ext_rat}
                    if ext_url: attrs["URL"] = ext_url
                    if ext_file: attrs["File"] = ext_file.name
                    save_guideline(ext_cat, ext_topic, ext_title, attrs, doctor_id)
                    st.success("External source added to wiki.")
                    st.rerun()

# ---------------------------------------------------------------------------
# Dashboard (Kanban)
# ---------------------------------------------------------------------------

@st.dialog("Add New Patient", width="large")
def _dialog_add_patient():
    st.caption("Upload a patient intake JSON to add them to your panel.")

    # Sample download
    _sample = Path("sample_patient_intake.json")
    if _sample.exists():
        c1, c2 = st.columns(2)
        c1.download_button(
            "⬇ Download intake template",
            data=_sample.read_bytes(),
            file_name="sample_patient_intake.json",
            mime="application/json",
            use_container_width=True,
        )
        if c2.button("Use sample (Robert Johnson)", use_container_width=True):
            st.session_state["_intake_data"] = json.loads(_sample.read_text())

    st.divider()

    # File uploader
    uploaded = st.file_uploader("Upload intake JSON", type=["json"], key="add_pt_uploader",
                                label_visibility="collapsed")
    if uploaded and "intake_file_key" not in st.session_state:
        try:
            st.session_state["_intake_data"] = json.loads(uploaded.read())
            st.session_state["intake_file_key"] = f"{uploaded.name}_{uploaded.size}"
        except json.JSONDecodeError:
            st.error("Invalid JSON — check the file and try again.")
            return

    intake = st.session_state.get("_intake_data")
    if not intake:
        st.markdown("""
**Expected fields:**
```
name · age · sex · insurance · chief_complaint
vitals  (heart_rate, blood_pressure, respiratory_rate, o2_saturation, temperature_celsius, weight_kg)
labs  (sodium, potassium, creatinine, glucose, troponin_i, wbc, ...)
past_medical_history  [ list of strings ]
current_medications   [ list of strings ]
allergies  [ {drug, reaction} ]
ed_assessment · handoff_notes
```
Download the template above for the full schema with an example patient.
""")
        return

    # Preview
    st.markdown("#### Preview")
    vitals = intake.get("vitals", {})
    o2 = vitals.get("o2_saturation", "?")
    o2_style = "color:#C0392B;font-weight:700" if isinstance(o2, (int,float)) and o2 < 94 else ""

    st.markdown(f"**{intake.get('name','?')}**, {intake.get('age','?')}{intake.get('sex','')} · {intake.get('insurance','')}")
    st.markdown(f"*{intake.get('chief_complaint','')}*")

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("O₂ Sat",   f"{o2}%")
    v2.metric("HR",        f"{vitals.get('heart_rate','?')} bpm")
    v3.metric("BP",        vitals.get("blood_pressure", "?"))
    v4.metric("Weight",    f"{vitals.get('weight_kg','?')} kg")

    pmh = intake.get("past_medical_history", [])
    if pmh:
        st.markdown("**PMH:** " + " · ".join(pmh))

    st.divider()
    col_add, col_cancel = st.columns(2)
    if col_add.button("Add to panel", type="primary", use_container_width=True):
        registry = _load_patient_registry()
        new_id = _next_patient_id(registry)
        _register_patient(intake, new_id)
        # Clear intake state
        for k in ("_intake_data", "intake_file_key"):
            st.session_state.pop(k, None)
        st.session_state.pop("open_dialog", None)
        st.toast(f"✓ {intake.get('name','Patient')} added as {new_id}")
        st.rerun()
    if col_cancel.button("Cancel", use_container_width=True):
        for k in ("_intake_data", "intake_file_key"):
            st.session_state.pop(k, None)
        st.session_state.pop("open_dialog", None)
        st.rerun()


def render_dashboard():
    epic = get_epic()
    registry = _load_patient_registry()

    hdr_col, btn_col = st.columns([5, 1])
    hdr_col.markdown("## My Patients")
    if btn_col.button("＋ Add Patient", type="primary", use_container_width=True):
        st.session_state["open_dialog"] = "add_patient"

    if st.session_state.get("open_dialog") == "add_patient":
        _dialog_add_patient()

    # Bucket patients by care stage
    pending, admitted, discharged = [], [], []
    for reg_entry in registry:
        pid = reg_entry["id"]
        try:
            data = epic.get_patient(pid)
            ctx = PatientContext.load(pid)
            workflows = {r.workflow for r in ctx.workflow_history}
            card_entry = (pid, data, ctx)
            if "discharge" in workflows:
                discharged.append(card_entry)
            elif "admission" in workflows:
                admitted.append(card_entry)
            else:
                pending.append(card_entry)
        except Exception:
            pass

    def _card(pid: str, data: dict, ctx, col_key: str):
        vitals = data.get("vitals", {})
        o2 = vitals.get("o2_saturation", "?")
        o2_cls = "pt-chip alert" if isinstance(o2, (int, float)) and o2 < 94 else "pt-chip"
        adm_rec = next((r for r in ctx.workflow_history if r.workflow == "admission"), None)
        date_html = f'<div class="pt-date">Admitted {adm_rec.timestamp[:10]}</div>' if adm_rec else ""
        chkd = _CACHE_DIR / f"{pid}_action_states.json"
        checkin_done = False
        if chkd.exists():
            try:
                states = json.loads(chkd.read_text())
                checkin_done = any(states.get(k) for k in ("ci_meds_sent", "ci_labs_sent", "ci_updates_saved"))
            except Exception:
                pass
        badge = ('<span style="font-size:0.65rem;font-weight:700;background:rgba(52,199,89,0.12);'
                 'color:#1A7A35;border-radius:980px;padding:0.1rem 0.45rem;margin-left:0.4rem;">'
                 'Check-in done</span>') if (adm_rec and checkin_done) else ""
        st.markdown(f"""
<div class="pt-card">
  <div><span class="pt-name">{data.get('name', pid)}</span>
       <span class="pt-meta">{data.get('age','?')}{data.get('sex','')}</span>{badge}</div>
  <div class="pt-complaint">{data.get('chief_complaint', '—')}</div>
  <div class="pt-vitals">
    <span class="{o2_cls}">O₂ {o2}%</span>
    <span class="pt-chip">HR {vitals.get('heart_rate','?')}</span>
    <span class="pt-chip">BP {vitals.get('blood_pressure','?')}</span>
  </div>
  {date_html}
</div>""", unsafe_allow_html=True)
        if st.button("Open →", key=f"dash_{pid}_{col_key}", use_container_width=True, type="secondary"):
            st.session_state["patient_selectbox"] = pid
            st.session_state["_nav_request"] = "Patient Workflows"
            st.rerun()

    # ── Two tabs ──────────────────────────────────────────────────────────────
    tab_current, tab_past = st.tabs([
        f"🏥  Current Patients  ({len(pending) + len(admitted)})",
        f"📁  Past Patients  ({len(discharged)})",
    ])

    with tab_current:
        if not pending and not admitted:
            st.markdown('<div class="kanban-empty">No active patients</div>', unsafe_allow_html=True)
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f'<div class="kanban-header">Pending Admission <span class="kanban-count">{len(pending)}</span></div>', unsafe_allow_html=True)
                if pending:
                    for pid, data, ctx in pending:
                        _card(pid, data, ctx, "p")
                else:
                    st.markdown('<div class="kanban-empty">—</div>', unsafe_allow_html=True)
            with col_b:
                st.markdown(f'<div class="kanban-header">Admitted — Rounding <span class="kanban-count">{len(admitted)}</span></div>', unsafe_allow_html=True)
                if admitted:
                    for pid, data, ctx in admitted:
                        _card(pid, data, ctx, "a")
                else:
                    st.markdown('<div class="kanban-empty">—</div>', unsafe_allow_html=True)

    with tab_past:
        if not discharged:
            st.markdown('<div class="kanban-empty">No discharged patients</div>', unsafe_allow_html=True)
        else:
            cols = st.columns(min(len(discharged), 3))
            for i, (pid, data, ctx) in enumerate(discharged):
                with cols[i % 3]:
                    _card(pid, data, ctx, "d")


# ---------------------------------------------------------------------------
# Patient Workflows View
# ---------------------------------------------------------------------------

@st.dialog("Already done", width="small")
def _already_done_dialog(title: str, message: str):
    st.markdown(f"**{title}**")
    st.markdown(message)
    if st.button("OK", type="primary", use_container_width=True):
        st.session_state.pop("open_dialog", None)
        st.rerun()


def render_patient_workflows(patient_id: str):
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
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    def run_wf(label: str, workflow_name: str, steps: list, session_fn):
        backend, model = get_backend(llm_provider)
        engine = WorkflowEngine(backend=backend, model=model, wiki=wiki)
        try: session = session_fn()
        except Exception as e: st.error(f"Error loading session: {e}"); return
        ctx = PatientContext.load(patient_id)
        st.session_state["active_workflow"], st.session_state["workflow_outputs"], st.session_state["workflow_complete"] = label, {}, False
        st.session_state.pop("open_dialog", None)
        st.session_state.pop("episode_wiki_saved", None)
        _clear_action_states(patient_id)
        with st.status(f"Running {label}...", expanded=True) as status:
            for step_name, output, state in engine.run_steps(steps, session, patient_context=ctx, workflow_name=workflow_name):
                st.write(f"✓ {step_name.replace('_', ' ').title()}")
                if output: st.session_state["workflow_outputs"][step_name] = output.content
            status.update(label=f"{label} complete", state="complete")
        st.session_state["workflow_complete"] = True
        _save_workflow_cache(patient_id, label, workflow_name, st.session_state["workflow_outputs"])
        st.rerun()

    # Check what's already been done for this patient
    _ctx = PatientContext.load(patient_id)
    _done_workflows = {r.workflow for r in _ctx.workflow_history}
    _admitted   = "admission"  in _done_workflows
    _discharged = "discharge"  in _done_workflows

    if btn_col1.button("🏥 Admit Patient", use_container_width=True):
        if _admitted:
            st.session_state["open_dialog"] = "already_admitted"
        else:
            run_wf("Admission", "admission", ADMISSION_STEPS, lambda: epic.build_admission_session(patient_id))

    if btn_col2.button("📋 Review Updates", use_container_width=True):
        st.session_state["show_checkin"] = not st.session_state.get("show_checkin", False)
        if not st.session_state["show_checkin"]:
            for _k in ("checkin_result", "checkin_file_key", "checkin_sample_loaded", "ci_meds_sent", "ci_labs_sent", "ci_updates_saved", "open_dialog"): st.session_state.pop(_k, None)
        st.rerun()

    if btn_col3.button("🚪 Discharge Patient", use_container_width=True):
        if _discharged:
            st.session_state["open_dialog"] = "already_discharged"
        else:
            run_wf("Discharge", "discharge", DISCHARGE_STEPS, lambda: epic.get_discharge_session(patient_id))

    # One-time workflow guard dialogs
    _od = st.session_state.get("open_dialog")
    if _od == "already_admitted":
        _rec = next(r for r in _ctx.workflow_history if r.workflow == "admission")
        _already_done_dialog("Patient already admitted", f"This patient was admitted on **{_rec.timestamp[:10]}**. The admission workflow can only be run once per episode.\n\nTo start a new episode, reset the patient context from the sidebar.")
    elif _od == "already_discharged":
        _rec = next(r for r in _ctx.workflow_history if r.workflow == "discharge")
        _already_done_dialog("Patient already discharged", f"This patient was discharged on **{_rec.timestamp[:10]}**. The discharge workflow can only be run once per episode.\n\nTo start a new episode, reset the patient context from the sidebar.")
    # Restore workflow outputs + action states from disk after a page refresh
    if not st.session_state.get("workflow_complete"):
        cached_label, cached_wf, cached_outputs = _load_workflow_cache(patient_id)
        if cached_outputs:
            st.session_state["workflow_complete"] = True
            st.session_state["active_workflow"] = cached_label
            st.session_state["workflow_outputs"] = cached_outputs
        _load_action_states(patient_id)

    if st.session_state.get("workflow_complete"):
        outputs, label, pending_all = st.session_state["workflow_outputs"], st.session_state.get("active_workflow"), get_pending_updates("default")
        st.divider()
        if label == "Admission": render_admission_results(outputs, patient_data.get("name", patient_id), patient_id, pending_all)
        elif label == "Discharge": render_discharge_results(outputs, pending_all, patient_data.get("name", patient_id))

    if st.session_state.get("show_checkin"): st.divider(); render_checkin_inline(patient_id, patient_data, llm_provider, wiki)

    # Persist action states to disk on every render so refreshes see current state
    _save_action_states(patient_id)

# ---------------------------------------------------------------------------
# Check-in UI
# ---------------------------------------------------------------------------

_TREND_ICON = {"worsening": "▲", "improving": "▼", "stable": "→", "new": "★"}
_URGENCY_ICON = {"now": "🔴", "today": "🟡", "routine": "⚪"}

@st.dialog("💊 Medication Changes", width="large")
def _dialog_ci_meds(med_actions: list):
    selected = []
    for i, action in enumerate(med_actions):
        st.markdown(f"{_URGENCY_ICON.get(action.get('urgency', 'routine'), '⚪')} **{_strip_citations(action.get('title', '?'))}**")
        if action.get("detail"):
            st.caption(_strip_citations(action["detail"]))
        # Citation sits directly under the order it supports, not in the editable field below.
        render_citation_chips(f"{action.get('title', '')} {action.get('detail', '')}", f"ci_med_{i}", caption="")
        edited = st.text_input("Order text", value=_strip_citations(action.get("title", "")), key=f"ci_med_edit_{i}", label_visibility="collapsed")
        if st.checkbox("Include in order", value=True, key=f"ci_med_chk_{i}"): selected.append({**action, "title": edited})
        st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["ci_meds_sent"] = True; st.session_state.pop("open_dialog", None)
        st.rerun()

@st.dialog("🧪 Lab Orders", width="large")
def _dialog_ci_labs(lab_actions: list):
    if not lab_actions: st.info("No lab orders."); return
    selected = []
    for i, action in enumerate(lab_actions):
        if st.checkbox(f"{_URGENCY_ICON.get(action.get('urgency', 'routine'), '⚪')} **{_strip_citations(action.get('title', '?'))}**", value=True, key=f"ci_lab_chk_{i}"): selected.append(action)
        if action.get("detail"):
            st.caption(f"  {_strip_citations(action['detail'])}")
        # Citation sits directly under the lab order it supports.
        render_citation_chips(f"{action.get('title', '')} {action.get('detail', '')}", f"ci_lab_{i}", caption="")
    st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["ci_labs_sent"] = True; st.session_state.pop("open_dialog", None)
        st.rerun()

@st.dialog("📋 Clinical Updates", width="large")
def _dialog_ci_updates(changes: list, note_actions: list, patient_id: str):
    if changes:
        st.markdown("**What changed:**")
        for i, c in enumerate(changes):
            st.markdown(f"{_TREND_ICON.get(c.get('trend', ''), '•')} **{c.get('finding', '')}** — {_strip_citations(c.get('significance', ''))}")
            # Citation sits right under the finding it supports.
            render_citation_chips(c.get("significance", ""), f"ci_chg_{i}", caption="")
        st.divider()
    note_lines = [f"- {c.get('finding', '')}: {c.get('significance', '')}" for c in changes] + [f"- {a.get('title', '')}: {a.get('detail', '')}" for a in note_actions]
    note_blob = "\n".join(note_lines)
    edited = st.text_area("Patient file update", value=_strip_citations(note_blob), height=300)
    c1, c2 = st.columns(2)
    if c1.button("Save to Patient File", type="primary", use_container_width=True):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        existing = (_CACHE_DIR / f"{patient_id}_note.md").read_text() if (_CACHE_DIR / f"{patient_id}_note.md").exists() else ""
        (_CACHE_DIR / f"{patient_id}_note.md").write_text(existing + f"\n\n---\n{edited}")
        st.session_state["ci_updates_saved"] = True; st.session_state.pop("open_dialog", None)
        st.rerun()
    if c2.button("Email to Patient", use_container_width=True):
        st.session_state["ci_updates_saved"] = True; st.session_state.pop("open_dialog", None)
        st.rerun()
    # Note-item citations have no discrete row above, so surface them at the bottom.
    render_citation_chips(" ".join(a.get("detail", "") for a in note_actions), "ci_updates")

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
        if st.button("Review & Send →" if not ci_meds_done else "Review Again", key="ci_open_meds", type="primary" if not ci_meds_done else "secondary", use_container_width=True, disabled=not med_actions): st.session_state["open_dialog"] = "ci_meds"
    with c2:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">🧪</div><div class="action-card-title">Labs</div><div class="action-card-{"done" if ci_labs_done else "sub"}">{labs_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not ci_labs_done else "Review Again", key="ci_open_labs", type="primary" if not ci_labs_done else "secondary", use_container_width=True, disabled=not lab_actions): st.session_state["open_dialog"] = "ci_labs"
    with c3:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">📋</div><div class="action-card-title">Clinical Updates</div><div class="action-card-{"done" if ci_updates_done else "sub"}">{updates_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Save →" if not ci_updates_done else "Review Again", key="ci_open_updates", type="primary" if not ci_updates_done else "secondary", use_container_width=True): st.session_state["open_dialog"] = "ci_updates"
    _od = st.session_state.get("open_dialog")
    if _od == "ci_meds": _dialog_ci_meds(med_actions)
    elif _od == "ci_labs": _dialog_ci_labs(lab_actions)
    elif _od == "ci_updates": _dialog_ci_updates(changes, update_actions, patient_id)
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("Upload new file", type="secondary", key="ci_reset"):
        for _k in ("checkin_result", "checkin_file_key", "ci_meds_sent", "ci_labs_sent", "ci_updates_saved", "open_dialog"): st.session_state.pop(_k, None)
        st.rerun()

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
        st.text_area("Agent notes / monitoring", value=_strip_citations(rx.get("agent_notes", "")), height=80, key=f"rx_notes_{idx}")
        if rx.get("drug_info_summary"): st.caption(f"ℹ️ **Drug info:** {_strip_citations(rx['drug_info_summary'])}")
        if rx.get("pa_notes"): (st.warning if pa_req else st.caption)(f"**PA:** {_strip_citations(rx['pa_notes'])}")
        if rx.get("alternatives"): st.caption("**Alternatives:** " + " · ".join(rx["alternatives"]))
        # Citation sits within this drug's card, not in the editable notes field above.
        _rx_cite_text = " ".join([rx.get("agent_notes", ""), rx.get("drug_info_summary", ""), rx.get("pa_notes", "")])
        render_citation_chips(_rx_cite_text, f"rx_{idx}", caption="")
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
            st.session_state["rx_sent_to_epic"] = True
            st.session_state.pop("open_dialog", None)
            st.rerun()
    if st.button("🔄 Re-draft", type="secondary"):
        st.session_state["prescription_drafts"] = []
        st.session_state["approved_orders"] = []
        st.session_state.pop("open_dialog", None)
        st.rerun()

@st.dialog("🧪 Lab Orders", width="large")
def _dialog_labs(lab_actions: list):
    if not lab_actions: st.info("No lab orders extracted."); return
    st.caption("Select orders to send."); st.divider(); selected, icon_map = [], {"now": "🔴", "today": "🟡", "routine": "⚪"}
    for i, a in enumerate(lab_actions):
        if st.checkbox(f"{icon_map.get(a.get('urgency', 'routine'), '⚪')} **{_strip_citations(a.get('title', '?'))}**", value=True, key=f"lab_chk_{i}"): selected.append(a)
        if a.get("detail"):
            st.caption(f"  {_strip_citations(a['detail'])}")
        # Citation sits directly under the lab order it supports.
        render_citation_chips(f"{a.get('title', '')} {a.get('detail', '')}", f"lab_{i}", caption="")
    st.divider()
    if st.button(f"Send {len(selected)} Order(s) to Epic", type="primary", use_container_width=True, disabled=not selected):
        st.session_state["labs_sent_to_epic"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()

@st.dialog("📋 Admission Note", width="large")
def _dialog_notes(note_text: str, patient_id: str):
    edited = st.text_area("", value=_strip_citations(note_text), height=450, label_visibility="collapsed", key="dialog_note_ta")
    c1, c2 = st.columns(2)
    if c1.button("Save to Patient File", type="primary", use_container_width=True):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True); (_CACHE_DIR / f"{patient_id}_note.md").write_text(edited)
        st.session_state["note_saved"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    if c2.button("Email to Patient", use_container_width=True):
        st.session_state["note_emailed"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    render_citation_chips(note_text, "adm_note")

# ---------------------------------------------------------------------------
# Results Rendering
# ---------------------------------------------------------------------------

# Agent reasoning outputs surfaced (in workflow order) in the durable admission review.
_ADMISSION_AGENT_NOTES = [
    ("chart_review", "📋 Chart Review"),
    ("lab_interpretation", "🧬 Lab Interpretation"),
    ("ed_note_synthesis", "📝 ED Note Synthesis"),
    ("consultant_routing", "🏥 Consultant Routing"),
    ("safety_check", "⚠️ Safety Check"),
    ("wiki_drift_check", "🔍 Wiki Alignment"),
]


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
        if st.button("Review & Send →" if not rx_done else "Review Again", key="open_rx", use_container_width=True, type="primary" if not rx_done else "secondary", disabled=not rxs): st.session_state["open_dialog"] = "rx"
    with c2:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">🧪</div><div class="action-card-title">Labs</div><div class="action-card-{"done" if labs_done else "sub"}">{lab_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Send →" if not labs_done else "Review Again", key="open_labs", use_container_width=True, type="primary" if not labs_done else "secondary", disabled=not lab_actions): st.session_state["open_dialog"] = "labs"
    with c3:
        st.markdown(f'<div class="action-card"><div class="action-card-icon">📋</div><div class="action-card-title">Admission Note</div><div class="action-card-{"done" if note_done else "sub"}">{note_sub}</div></div>', unsafe_allow_html=True)
        if st.button("Review & Sign →" if not note_done else "Review Again", key="open_note", use_container_width=True, type="primary" if not note_done else "secondary", disabled=not note_text): st.session_state["open_dialog"] = "note"
    _od = st.session_state.get("open_dialog")
    if _od == "rx": _dialog_prescriptions()
    elif _od == "labs": _dialog_labs(lab_actions)
    elif _od == "note": _dialog_notes(note_text, patient_id)

    # Durable record of every agent's reasoning so the physician can review the full
    # analysis after completion (the live run trace is gone once the workflow reruns).
    # Source chips link each suggestion back to the guideline/protocol — with the date it
    # was added to the wiki — behind it.
    if any(outputs.get(step) for step, _ in _ADMISSION_AGENT_NOTES):
        st.divider()
        st.markdown("### 📚 Agent Notes & Analysis")
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

# ---------------------------------------------------------------------------
# Discharge dialogs
# ---------------------------------------------------------------------------

@st.dialog("📝 Discharge Summary", width="large")
def _dialog_dc_summary(text: str):
    st.caption("Edit and copy into Epic.")
    edited = st.text_area("", value=_strip_citations(text), height=420, label_visibility="collapsed", key="dc_sum_ta")
    if st.button("Copy to Epic", type="primary", use_container_width=True):
        st.session_state["dc_summary_done"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    render_citation_chips(text, "dc_summary")


@st.dialog("📬 Patient Instructions", width="large")
def _dialog_dc_instructions(text: str):
    st.caption("Review, then print or send to patient portal.")
    edited = st.text_area("", value=_strip_citations(text), height=420, label_visibility="collapsed", key="dc_instr_ta")
    c1, c2 = st.columns(2)
    if c1.button("Print", type="primary", use_container_width=True):
        st.session_state["dc_instructions_done"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    if c2.button("Send to Portal", use_container_width=True):
        st.session_state["dc_instructions_done"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    render_citation_chips(text, "dc_instructions")


@st.dialog("✅ Sign-off Checklist", width="large")
def _dialog_dc_checklist(text: str):
    st.caption("Work through each item before signing.")
    # Render checklist items as checkboxes
    lines = [l for l in text.splitlines() if l.strip()]
    all_checked = True
    for i, line in enumerate(lines):
        clean = _strip_citations(line.lstrip("-•[ ] ").strip())
        if clean:
            checked = st.checkbox(clean, key=f"dc_chk_{i}")
            if not checked:
                all_checked = False
            # Citation sits directly under the checklist item that cites it.
            render_citation_chips(line, f"dc_chk_{i}", caption="")
    st.divider()
    if st.button("Sign Off", type="primary", use_container_width=True, disabled=not all_checked):
        st.session_state["dc_checklist_done"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    if not all_checked:
        st.caption("Check all items to enable sign-off.")


@st.dialog("🛡️ Safety Check", width="large")
def _dialog_dc_safety(text: str):
    st.markdown(_strip_citations(text))
    st.divider()
    if st.button("Acknowledged", type="primary", use_container_width=True):
        st.session_state["dc_safety_done"] = True
        st.session_state.pop("open_dialog", None)
        st.rerun()
    render_citation_chips(text, "dc_safety")


def render_discharge_results(outputs: dict, pending_all: list, patient_name: str = ""):
    has_summary      = "discharge_summary"   in outputs
    has_instructions = "patient_instructions" in outputs
    has_checklist    = "discharge_checklist"  in outputs
    has_safety       = "safety_check"         in outputs

    sum_done   = st.session_state.get("dc_summary_done", False)
    instr_done = st.session_state.get("dc_instructions_done", False)
    chk_done   = st.session_state.get("dc_checklist_done", False)
    safe_done  = st.session_state.get("dc_safety_done", False)

    st.markdown("### Ready for Review")

    # Row 1
    c1, c2 = st.columns(2)
    with c1:
        sub = "✓ Sent to Epic" if sum_done else "Discharge note ready"
        st.markdown(f"""
<div class="action-card">
  <div class="action-card-icon">📝</div>
  <div class="action-card-title">Discharge Summary</div>
  <div class="action-card-{'done' if sum_done else 'sub'}">{sub}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Review & Copy →" if not sum_done else "Review Again",
                     key="open_dc_sum", use_container_width=True,
                     type="primary" if not sum_done else "secondary",
                     disabled=not has_summary):
            st.session_state["open_dialog"] = "dc_summary"

    with c2:
        sub = "✓ Sent" if instr_done else "Ready to print or send"
        st.markdown(f"""
<div class="action-card">
  <div class="action-card-icon">📬</div>
  <div class="action-card-title">Patient Instructions</div>
  <div class="action-card-{'done' if instr_done else 'sub'}">{sub}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Review & Send →" if not instr_done else "Review Again",
                     key="open_dc_instr", use_container_width=True,
                     type="primary" if not instr_done else "secondary",
                     disabled=not has_instructions):
            st.session_state["open_dialog"] = "dc_instructions"

    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    # Row 2
    c3, c4 = st.columns(2)
    with c3:
        sub = "✓ Signed off" if chk_done else "Items to check"
        st.markdown(f"""
<div class="action-card">
  <div class="action-card-icon">✅</div>
  <div class="action-card-title">Sign-off Checklist</div>
  <div class="action-card-{'done' if chk_done else 'sub'}">{sub}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Review & Sign →" if not chk_done else "Review Again",
                     key="open_dc_chk", use_container_width=True,
                     type="primary" if not chk_done else "secondary",
                     disabled=not has_checklist):
            st.session_state["open_dialog"] = "dc_checklist"

    with c4:
        sub = "✓ Acknowledged" if safe_done else "Review before discharge"
        st.markdown(f"""
<div class="action-card">
  <div class="action-card-icon">🛡️</div>
  <div class="action-card-title">Safety Check</div>
  <div class="action-card-{'done' if safe_done else 'sub'}">{sub}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Review →" if not safe_done else "Review Again",
                     key="open_dc_safe", use_container_width=True,
                     type="primary" if not safe_done else "secondary",
                     disabled=not has_safety):
            st.session_state["open_dialog"] = "dc_safety"

    # Open dialogs — only one can be active at a time
    _od = st.session_state.get("open_dialog")
    if _od == "dc_summary":      _dialog_dc_summary(outputs.get("discharge_summary", ""))
    elif _od == "dc_instructions": _dialog_dc_instructions(outputs.get("patient_instructions", ""))
    elif _od == "dc_checklist":  _dialog_dc_checklist(outputs.get("discharge_checklist", ""))
    elif _od == "dc_safety":     _dialog_dc_safety(outputs.get("safety_check", ""))

    # Episode learnings
    if pending_all:
        st.divider()
        _render_episode_learnings(pending_all, patient_name or "this patient")

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

# ── Settings gear (upper-right) ────────────────────────────────────────────
# LLM Provider lives behind a ⚙️ popover that opens on click and closes when
# the icon is pressed again or the user clicks away / hits Close.
if "llm_provider" not in st.session_state:
    st.session_state["llm_provider"] = "Anthropic"

_spacer, _settings_col = st.columns([11, 1])
with _settings_col:
    with st.container(key="settingsgear"):
        with st.popover("⚙️", width="stretch"):
            st.markdown("**Settings**")
            st.radio("LLM Provider", options=["Anthropic", "Gemini"], key="llm_provider")
llm_provider = st.session_state["llm_provider"]

if app_mode == "Patient Workflows" and st.session_state.get("active_citation"):
    col_main, col_right = st.columns([3, 1])
else:
    col_main, col_right = st.container(), None

with col_main:
    if app_mode == "Dashboard":
        render_dashboard()
    elif app_mode == "Patient Workflows":
        render_patient_workflows(patient_id)
    else:
        render_wiki_management()

if col_right:
    with col_right: render_wiki_reference_card("default")
