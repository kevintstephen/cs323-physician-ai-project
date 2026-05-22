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
    get_wiki_insight, parse_wiki_sections
)
from llm import AnthropicBackend, GeminiBackend
from workflows.engine import WorkflowEngine
from workflows.admission import ADMISSION_STEPS
from workflows.discharge import DISCHARGE_STEPS
from workflows.case_management import CASE_MANAGEMENT_STEPS
from context.patient_context import PatientContext
from agents.admission.prescription import PrescriptionDraftAgent
from agents.admission.action_extraction import ActionExtractionAgent, URGENCY_CONFIG, ACTION_TYPES

load_dotenv()

# ---------------------------------------------------------------------------
# Page config & Global CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Physician AI",
    page_icon="🏥",
    layout="wide",
)

# Inject Global CSS for stickiness and professional styling
st.markdown(
    """
    <style>
    /* 1. Make the second column sticky so it follows the viewport height */
    div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stVerticalBlock"] {
        position: sticky;
        top: 2rem;
        align-self: flex-start;
        z-index: 1000;
    }

    /* 2. Prevent parent containers from clipping the sticky element */
    div[data-testid="stHorizontalBlock"], 
    div[data-testid="stVerticalBlock"],
    .main .block-container {
        overflow: visible !important;
    }

    /* 3. Styling for the Wiki Reference Box */
    .wiki-ref-box {
        background-color: #ffffff;
        border: 2px solid #1f77b4;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-top: 1rem;
    }
    
    .wiki-ref-header {
        color: #1f77b4;
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid #eee;
        padding-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Session State
if "active_citation" not in st.session_state:
    st.session_state.active_citation = None

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
        content_words = set(re.findall(r'\w{4,}', (item['content'] + " " + item['header']).lower()))
        if keywords & content_words:
            related_indices.append(i)
    return related_indices


def render_content_with_citations(text: str, key_suffix: str, doctor_id: str = "default"):
    """
    Renders text cleanly and places [📚 Wiki] interactive buttons.
    Supports [WikiID: xxxxxx], (WikiID: xxxxxx), and WikiID: xxxxxx.
    """
    if not text: return
    
    # regex to catch variations of the citation tag
    pattern = r'[\[\(]?WikiID:\s*([a-zA-Z0-9]+)[\]\)]?'
    
    # Clean text for display (remove raw tags and fix double spaces)
    display_text = re.sub(pattern, '', text).strip()
    display_text = re.sub(r'\s{2,}', ' ', display_text)
    st.markdown(display_text)
    
    # Render citations as interactive buttons
    citations = re.findall(pattern, text)
    if citations:
        cit_cols = st.columns([0.15] * 5 + [0.25])
        for i, insight_id in enumerate(citations[:5]):
            with cit_cols[i]:
                if st.button("📚 Wiki", key=f"cit_{insight_id}_{key_suffix}_{i}", type="secondary"):
                    st.session_state.active_citation = insight_id.lower()
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

    app_mode = st.radio(
        "Navigation",
        options=["Patient Workflows", "Wiki Management"],
        index=0
    )
    
    st.divider()

    if app_mode == "Patient Workflows":
        patient_id = st.selectbox(
            "Patient",
            options=["TEST-001"],
            help="Select a patient to work with",
        )

        llm_provider = st.radio(
            "LLM Provider",
            options=["Anthropic", "Gemini"],
            index=0,
        )

        st.divider()

        # Active problem list
        patient_ctx = PatientContext.load(patient_id)
        if patient_ctx.workflow_history:
            st.markdown("**Active Problem List**")
            active = patient_ctx.active_issues
            if active:
                for issue in active:
                    st.markdown(f"⚠️ {issue}")
            else:
                st.caption("No open issues.")

            st.divider()
            st.markdown("**Care Episode**")
            for rec in patient_ctx.workflow_history:
                date = rec.timestamp[:10]
                st.markdown(f"✓ {rec.workflow.replace('_', ' ').title()} — {date}")

            if st.button("Reset patient context", type="secondary"):
                PatientContext.clear(patient_id)
                st.rerun()
        else:
            st.caption("No workflows run yet.")

    st.divider()
    st.caption("Stanford CS323 — AI Awakening")

# ---------------------------------------------------------------------------
# Wiki Management View
# ---------------------------------------------------------------------------

def render_pending_update_card(i: int, item: dict, doctor_id: str, suffix: str = "", expanded: bool = False):
    """Renders a single pending update card with Edit/Approve/Reject actions."""
    label = f"✨ [{item.get('category', 'General')}] {item['header']}"
    with st.expander(label, expanded=expanded):
        new_category = item.get('category', 'General')
        new_topic = item['header']
        new_content = st.text_area("", value=item['content'], key=f"edit_{suffix}_{i}", label_visibility="collapsed")
        
        col1, col2, col3 = st.columns([1, 1, 4])
        if col1.button("✅ Approve", key=f"app_{suffix}_{i}", type="primary"):
            rules = [line.strip("- ").strip() for line in new_content.split("\n") if line.strip()]
            update_data = [{"category": new_category, "topic": new_topic, "rules": rules}]
            
            if item['type'] == 'protocol':
                update_wiki(doctor_id, update_data, [])
            else:
                update_wiki(doctor_id, [], update_data)
            
            remove_pending_update(doctor_id, i)
            st.success("Wiki evolved.")
            st.rerun()
        
        if col2.button("❌ Reject", key=f"rej_{suffix}_{i}"):
            remove_pending_update(doctor_id, i)
            st.rerun()


def render_wiki_management():
    st.header("📚 Doctor's Wiki & Preferences")
    st.markdown(
        "Grounding for all agents. Review new learnings from cases, "
        "or manually edit your clinical protocols and preferences."
    )
    
    doctor_id = "default"
    
    # --- Part 1: Review Queue ---
    pending = get_pending_updates(doctor_id)
    if pending:
        with st.expander(f"🔔 Pending Updates ({len(pending)})", expanded=False):
            st.info("The Wiki Substrate agent extracted these new insights from recent workflows. Review and approve them to evolve your wiki.")
            for i, item in enumerate(pending):
                render_pending_update_card(i, item, doctor_id, suffix="mgmt", expanded=True)
        st.divider()

    # --- Part 2: Current Wiki Content ---
    st.subheader("🖋 Current Wiki Content")
    
    col_search, col_filter = st.columns([2, 1])
    search_query = col_search.text_input("🔍 Search wiki...", "").lower()
    
    tab_protocols, tab_prefs = st.tabs(["📋 Clinical Protocols", "⚙️ Doctor Preferences"])
    
    def render_wiki_editor(filename: str, title: str):
        content = get_wiki_file_content(doctor_id, filename)
        sections = parse_wiki_sections(content)
        
        categories = sorted(list(set(s['category'] for s in sections)))
        filter_cat = col_filter.selectbox(f"Filter {title}", ["All"] + categories, key=f"filter_{filename}")

        filtered = [
            s for s in sections 
            if (filter_cat == "All" or s['category'] == filter_cat) and
               (search_query in s['category'].lower() or search_query in s['topic'].lower() or any(search_query in r.lower() for r in s['rules']))
        ]
        
        if not filtered:
            st.caption("No matching topics found.")
        
        current_display_cat = None
        for i, s in enumerate(filtered):
            if s['category'] != current_display_cat:
                st.markdown(f"#### 📁 {s['category']}")
                current_display_cat = s['category']
                
            with st.expander(f"{s['topic']}", expanded=False):
                new_cat = s['category']
                new_topic = s['topic']
                body_text = "\n".join(f"- {r}" for r in s['rules'])
                new_body = st.text_area("", value=body_text, height=200, key=f"body_ed_{filename}_{i}", label_visibility="collapsed")
                
                c1, c2, _ = st.columns([1, 1, 4])
                if c1.button("💾 Save", key=f"s_{filename}_{i}"):
                    new_sections = []
                    rules = [line.strip("- ").strip() for line in new_body.split("\n") if line.strip()]
                    for orig in sections:
                        if orig['topic'] == s['topic'] and orig['category'] == s['category']:
                            new_sections.append({"category": new_cat, "topic": new_topic, "rules": rules})
                        else:
                            new_sections.append(orig)
                    
                    new_sections.sort(key=lambda x: x['category'])
                    reconstructed = ""
                    last_cat = None
                    for ns in new_sections:
                        if ns['category'] != last_cat:
                            reconstructed += f"\n## {ns['category']}\n"
                            last_cat = ns['category']
                        reconstructed += f"### {ns['topic']}\n" + "\n".join(f"- {r}" for r in ns['rules']) + "\n\n"
                    
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
                        reconstructed += f"### {ns['topic']}\n" + "\n".join(f"- {r}" for r in ns['rules']) + "\n\n"
                    save_wiki_file_content(doctor_id, filename, reconstructed)
                    st.rerun()

    with tab_protocols:
        render_wiki_editor("clinical_protocols.md", "Protocols")

    with tab_prefs:
        render_wiki_editor("preferences.md", "Preferences")


# ---------------------------------------------------------------------------
# Patient Workflows View
# ---------------------------------------------------------------------------

def render_patient_workflows():
    epic = get_epic()
    wiki = get_wiki_text()

    try:
        patient_data = epic.get_patient(patient_id)
    except Exception as e:
        st.error(f"Could not load patient data: {e}")
        st.stop()

    vitals = patient_data.get("vitals", {})

    st.markdown(f"## Patient: {patient_data.get('name', patient_id)}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Age / Sex", f"{patient_data.get('age', '?')} {patient_data.get('sex', '')}")
    col2.metric("O₂ Sat", f"{vitals.get('o2_saturation', '?')}%")
    col3.metric("HR / BP", f"{vitals.get('heart_rate', '?')} / {vitals.get('blood_pressure', '?')}")
    col4.metric("RR", f"{vitals.get('respiratory_rate', '?')}")

    st.info(f"**Chief complaint:** {patient_data.get('chief_complaint', 'Not documented')}")

    # --- Expandable Chart ---
    with st.expander("📂 Patient Chart", expanded=True):
        tab_overview, tab_labs, tab_meds, tab_ed, tab_history = st.tabs(
            ["Overview", "Labs", "Medications & Allergies", "ED & Handoff Notes", "Prior Hospitalizations"]
        )

        with tab_overview:
            ov_col1, ov_col2 = st.columns(2)
            with ov_col1:
                st.markdown("**Past Medical History**")
                for item in patient_data.get("pmh", []):
                    st.markdown(f"- {item}")
            with ov_col2:
                st.markdown("**Baseline Functional Status**")
                st.markdown(patient_data.get("baseline_functional_status", "Not documented"))

            st.markdown("**Vitals on Arrival**")
            v = patient_data.get("vitals", {})
            vcol1, vcol2, vcol3, vcol4, vcol5, vcol6 = st.columns(6)
            vcol1.metric("Heart Rate", f"{v.get('heart_rate', '?')} bpm")
            vcol2.metric("Blood Pressure", v.get("blood_pressure", "?"))
            vcol3.metric("Resp Rate", f"{v.get('respiratory_rate', '?')}/min")
            vcol4.metric("O₂ Sat", f"{v.get('o2_saturation', '?')}%")
            vcol5.metric("Temp", f"{v.get('temperature_celsius', '?')} °C")
            vcol6.metric("Weight", f"{v.get('weight_kg', '?')} kg")

        with tab_labs:
            labs = patient_data.get("labs", {})
            if labs:
                rows = []
                for key, value in labs.items():
                    rows.append({"Test": key.replace("_", " ").title(), "Value": value})
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.caption("No labs on file.")

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
            prior = patient_data.get("prior_hospitalizations", [])
            for hosp in prior:
                label = f"{hosp.get('date', '?')} — {hosp.get('reason', '?')}  ({hosp.get('length_of_stay_days', '?')} days)"
                with st.expander(label):
                    st.markdown(f"**Treatment:** {hosp.get('treatment', '—')}")
                    st.markdown(f"**Discharge weight:** {hosp.get('discharge_weight_kg', '?')} kg")
                    st.markdown(f"**Update follows:** {hosp.get('transitional_issues', '—')}")

    # --- History Timeline ---
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
    st.markdown("### Actions")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    def run_wf(label: str, workflow_name: str, steps: list, session_fn):
        backend, model = get_backend(llm_provider)
        engine = WorkflowEngine(backend=backend, model=model, wiki=wiki)
        try: session = session_fn()
        except Exception as e: st.error(f"Error loading session: {e}"); return
        ctx = PatientContext.load(patient_id)

        st.session_state["active_workflow"] = label
        st.session_state["workflow_outputs"] = {}
        st.session_state["workflow_complete"] = False
        st.session_state["completed_actions"] = set()

        with st.status(f"Running {label}...", expanded=True) as status:
            for step_name, output, state in engine.run_steps(steps, session, patient_context=ctx, workflow_name=workflow_name):
                st.write(f"✓ {step_name.replace('_', ' ').title()}")
                if output: st.session_state["workflow_outputs"][step_name] = output.content
            status.update(label=f"{label} complete", state="complete")
        st.session_state["workflow_complete"] = True
        st.rerun()

    if btn_col1.button("🏥 Admit Patient", use_container_width=True):
        run_wf("Admission", "admission", ADMISSION_STEPS, lambda: epic.build_admission_session(patient_id))
    if btn_col2.button("📋 Review Updates", use_container_width=True):
        run_wf("Case Management", "case_management", CASE_MANAGEMENT_STEPS, lambda: epic.build_admission_session(patient_id))
    if btn_col3.button("🚪 Discharge Patient", use_container_width=True):
        run_wf("Discharge", "discharge", DISCHARGE_STEPS, lambda: epic.get_discharge_session(patient_id))

    # --- Results Display ---
    if st.session_state.get("workflow_complete"):
        outputs = st.session_state["workflow_outputs"]
        label = st.session_state.get("active_workflow")
        st.divider()
        st.markdown(f"### {label} Results")
        
        pending_all = get_pending_updates("default")
        matched_indices = set()

        if label == "Admission" and "action_extraction" in outputs:
            actions = ActionExtractionAgent.parse_actions(outputs["action_extraction"])
            if "completed_actions" not in st.session_state: st.session_state["completed_actions"] = set()
            for urgency in ("now", "today", "routine"):
                group = [(i, a) for i, a in enumerate(actions) if a.get("urgency") == urgency and i not in st.session_state["completed_actions"]]
                if group:
                    icon, l, _ = URGENCY_CONFIG[urgency]
                    st.markdown(f"#### {icon} {l}")
                    for idx, action in group:
                        col_check, col_badge, col_content = st.columns([0.5, 1, 8])
                        if col_check.button("✓", key=f"a_{idx}"): st.session_state["completed_actions"].add(idx); st.rerun()
                        a_icon, a_l = ACTION_TYPES.get(action.get("type", "order"), ("📋", "Order"))
                        col_badge.markdown(f"<span style='background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:0.75em'>{a_icon} {a_l}</span>", unsafe_allow_html=True)
                        
                        with col_content:
                            st.markdown(f"**{action.get('title', '')}**")
                            render_content_with_citations(action.get('detail', ''), f"act_{idx}")
                            
                            related = get_related_updates(action.get('title', '') + " " + action.get('detail', ''), pending_all)
                            to_render = [r_idx for r_idx in related if r_idx not in matched_indices]
                            if to_render:
                                with st.expander("✨ Wiki Suggestions", expanded=False):
                                    for r_idx in to_render:
                                        render_pending_update_card(r_idx, pending_all[r_idx], "default", suffix=f"inline_{idx}")
                                        matched_indices.add(r_idx)

        remaining = [i for i, item in enumerate(pending_all) if i not in matched_indices]
        if remaining:
            st.divider()
            st.subheader("🧠 Remaining Wiki Insights")
            for r_idx in remaining:
                render_pending_update_card(r_idx, pending_all[r_idx], "default", suffix="remaining")

        if "safety_check" in outputs:
            with st.expander("🛡 Safety Check", expanded=True): st.markdown(outputs["safety_check"])

        tab_list = [k.replace("_", " ").title() for k in outputs if k not in ("safety_check", "context_synthesis", "action_extraction", "wiki_substrate")]
        if tab_list:
            tabs = st.tabs(tab_list)
            for i, tab in enumerate(tabs):
                keys = [k for k in outputs if k not in ("safety_check", "context_synthesis", "action_extraction", "wiki_substrate")]
                with tab: 
                    render_content_with_citations(outputs[keys[i]], f"tab_{i}")

        if label == "Admission":
            st.divider()
            render_prescriptions(epic, patient_id, llm_provider, wiki)

# ---------------------------------------------------------------------------
# Prescription Section
# ---------------------------------------------------------------------------

def render_prescriptions(epic, patient_id, provider, wiki):
    st.markdown("### 💊 Prescription Orders")
    if "rx_drafts" not in st.session_state:
        if st.button("🤖 Draft Prescriptions", type="primary"):
            backend, model = get_backend(provider)
            agent = PrescriptionDraftAgent(backend=backend, model=model)
            with st.status("Drafting..."):
                session = epic.build_admission_session(patient_id)
                output = agent.run({"patient_id": patient_id, "patient_data": session.patient_data}, wiki=wiki)
                st.session_state["rx_drafts"] = agent.parse_prescriptions(output.content)
            st.rerun()
    
    if st.session_state.get("rx_drafts"):
        for rx in st.session_state["rx_drafts"]:
            with st.expander(f"**{rx.get('drug_name', '?')}**"):
                st.json(rx)

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

# Layout logic: ONLY open columns when a citation is active (Default Closed)
if app_mode == "Patient Workflows" and st.session_state.get("active_citation"):
    col_main, col_right = st.columns([3, 1])
else:
    col_main = st.container()
    col_right = None

with col_main:
    if app_mode == "Patient Workflows":
        render_patient_workflows()
    else:
        render_wiki_management()

if col_right:
    with col_right:
        # The content in this column is sticky due to Global CSS injected at top
        render_wiki_reference_card("default")
