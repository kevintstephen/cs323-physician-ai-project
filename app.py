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
    update_wiki, get_wiki_file_content, save_wiki_file_content
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
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Physician AI",
    page_icon="🏥",
    layout="wide",
)

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
    # Extract long words as potential keywords
    keywords = set(re.findall(r'\w{4,}', text.lower()))
    related_indices = []
    for i, item in enumerate(pending_list):
        content_words = set(re.findall(r'\w{4,}', (item['content'] + " " + item['header']).lower()))
        # If any significant keywords overlap, consider it related
        if keywords & content_words:
            related_indices.append(i)
    return related_indices

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

            if st.button("🗑 Reset patient context", type="secondary"):
                PatientContext.clear(patient_id)
                st.rerun()
        else:
            st.caption("No workflows run yet.")

    st.divider()
    st.caption("Stanford CS323 — AI Awakening")

# ---------------------------------------------------------------------------
# Wiki Management View Components (Extracted for reuse)
# ---------------------------------------------------------------------------

def render_pending_update_card(i: int, item: dict, doctor_id: str, suffix: str = "", expanded: bool = False):
    """Renders a single pending update card with Edit/Approve/Reject actions."""
    label = f"✨ Wiki Suggestion: {item['header']}"
    with st.expander(label, expanded=expanded):
        new_content = st.text_area("Edit suggestion", value=item['content'], key=f"edit_{suffix}_{i}")
        
        col1, col2, col3 = st.columns([1, 1, 4])
        if col1.button("✅ Approve", key=f"app_{suffix}_{i}", type="primary"):
            if item['type'] == 'protocol':
                update_wiki(doctor_id, {item['header']: [new_content]}, {})
            else:
                update_wiki(doctor_id, {}, {item['header']: [new_content]})
            remove_pending_update(doctor_id, i)
            st.success("Wiki evolved.")
            st.rerun()
        
        if col2.button("❌ Reject", key=f"rej_{suffix}_{i}"):
            remove_pending_update(doctor_id, i)
            st.rerun()


# ---------------------------------------------------------------------------
# Wiki Management View
# ---------------------------------------------------------------------------

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
        st.subheader(f"🔔 Pending Updates ({len(pending)})")
        st.info("The Wiki Substrate agent extracted these new insights from recent workflows. Review and approve them to evolve your wiki.")
        
        for i, item in enumerate(pending):
            render_pending_update_card(i, item, doctor_id, suffix="mgmt", expanded=True)
        st.divider()

    # --- Part 2: Current Wiki Content ---
    st.subheader("🖋 Current Wiki Content")
    
    search_query = st.text_input("🔍 Search protocols and preferences", "").lower()
    
    tab_protocols, tab_prefs = st.tabs(["📋 Clinical Protocols", "⚙️ Doctor Preferences"])
    
    def render_wiki_editor(filename: str, title: str):
        content = get_wiki_file_content(doctor_id, filename)
        # Parse into sections: [header, content]
        sections = []
        raw_sections = re.split(r'\n(##\s+)', "\n" + content)
        if raw_sections[0].strip(): # handle text before first header
             sections.append(["Intro", raw_sections[0].strip()])
        
        for i in range(1, len(raw_sections), 2):
            header = raw_sections[i+1].split('\n')[0].strip()
            body = '\n'.join(raw_sections[i+1].split('\n')[1:]).strip()
            sections.append([header, body])

        # Filter sections
        filtered = [s for s in sections if search_query in s[0].lower() or search_query in s[1].lower()]
        
        if not filtered:
            st.caption("No matching sections found.")
        
        for i, (header, body) in enumerate(filtered):
            with st.expander(f"## {header}", expanded=False):
                new_header = st.text_input("Header", value=header, key=f"h_{filename}_{i}")
                new_body = st.text_area("Content", value=body, height=200, key=f"b_{filename}_{i}")
                
                c1, c2, _ = st.columns([1, 1, 4])
                if c1.button("💾 Save", key=f"s_{filename}_{i}"):
                    # Reconstruct file
                    new_file_content = ""
                    for h, b in sections:
                        if h == header: # update this section
                            new_file_content += f"## {new_header}\n{new_body}\n\n"
                        else:
                            new_file_content += f"## {h}\n{b}\n\n"
                    save_wiki_file_content(doctor_id, filename, new_file_content)
                    st.success("Section saved.")
                    st.rerun()
                
                if c2.button("🗑 Delete", key=f"d_{filename}_{i}"):
                    new_file_content = ""
                    for h, b in sections:
                        if h != header:
                            new_file_content += f"## {h}\n{b}\n\n"
                    save_wiki_file_content(doctor_id, filename, new_file_content)
                    st.rerun()

    with tab_protocols:
        render_wiki_editor("clinical_protocols.md", "Protocols")

    with tab_prefs:
        render_wiki_editor("preferences.md", "Preferences")


# ---------------------------------------------------------------------------
# Patient Workflows View (The original UI)
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
                # Lab display logic
                LAB_META = {
                    "sodium":      ("Na",         "mEq/L",  "136–145"),
                    "potassium":   ("K",          "mEq/L",  "3.5–5.0"),
                    "creatinine":  ("Cr",         "mg/dL",  "0.6–1.2"),
                    "bun":         ("BUN",        "mg/dL",  "7–20"),
                    "glucose":     ("Glucose",    "mg/dL",  "70–99"),
                    "bnp":         ("BNP",        "pg/mL",  "<100"),
                    "troponin_i":  ("Troponin I", "ng/mL",  "<0.04"),
                    "wbc":         ("WBC",        "/µL",    "4500–11000"),
                    "hemoglobin":  ("Hgb",        "g/dL",   "13.5–17.5"),
                    "hematocrit":  ("Hct",        "%",      "41–53"),
                    "platelets":   ("Platelets",  "/µL",    "150000–400000"),
                    "inr":         ("INR",        "",       "0.8–1.1"),
                }
                ABNORMAL_CHECK = {
                    "sodium":      lambda v: not (136 <= v <= 145),
                    "potassium":   lambda v: not (3.5 <= v <= 5.0),
                    "creatinine":  lambda v: v > 1.2,
                    "bun":         lambda v: v > 20,
                    "glucose":     lambda v: not (70 <= v <= 99),
                    "bnp":         lambda v: v > 100,
                    "troponin_i":  lambda v: v >= 0.04,
                    "wbc":         lambda v: not (4500 <= v <= 11000),
                    "hemoglobin":  lambda v: v < 13.5,
                    "hematocrit":  lambda v: v < 41,
                    "platelets":   lambda v: not (150000 <= v <= 400000),
                    "inr":         lambda v: v > 1.1,
                }
                rows = []
                for key, value in labs.items():
                    meta = LAB_META.get(key, (key.replace("_", " ").title(), "", ""))
                    name, unit, ref = meta
                    check = ABNORMAL_CHECK.get(key)
                    flag = ""
                    try:
                        if check and check(float(value)): flag = "⚠️"
                    except: pass
                    rows.append({"Test": f"{flag} {name}".strip(), "Value": f"{value} {unit}".strip(), "Reference": ref})
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
                    st.markdown(f"**Transitional issues:** {hosp.get('transitional_issues', '—')}")

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

    # --- Workflow Execution Helper ---
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

        # Admission-specific results (Action list)
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
                            st.markdown(f"**{action.get('title', '')}**\n\n<small>{action.get('detail', '')}</small>", unsafe_allow_html=True)
                            
                            # Interleave contextual wiki updates
                            related = get_related_updates(action.get('title', '') + " " + action.get('detail', ''), pending_all)
                            to_render = [r_idx for r_idx in related if r_idx not in matched_indices]
                            if to_render:
                                with st.expander("✨ Wiki Suggestions", expanded=False):
                                    for r_idx in to_render:
                                        render_pending_update_card(r_idx, pending_all[r_idx], "default", suffix=f"inline_{idx}")
                                        matched_indices.add(r_idx)

        # Catch-all for wiki insights that didn't match an action
        remaining = [i for i, item in enumerate(pending_all) if i not in matched_indices]
        if remaining:
            st.divider()
            st.subheader("🧠 Remaining Wiki Insights")
            for r_idx in remaining:
                render_pending_update_card(r_idx, pending_all[r_idx], "default", suffix="remaining")

        # Safety Check
        if "safety_check" in outputs:
            with st.expander("🛡 Safety Check", expanded=True): st.markdown(outputs["safety_check"])

        # Tabs for discharge/other outputs
        tab_list = [k.replace("_", " ").title() for k in outputs if k not in ("safety_check", "context_synthesis", "action_extraction", "wiki_substrate")]
        if tab_list:
            tabs = st.tabs(tab_list)
            for i, tab in enumerate(tabs):
                key = list(outputs.keys())[i] # This indexing is slightly fragile but works for simple list
                # actually let's just filter properly
                keys = [k for k in outputs if k not in ("safety_check", "context_synthesis", "action_extraction", "wiki_substrate")]
                with tab: st.markdown(outputs[keys[i]])

        # Prescription section
        if label == "Admission":
            st.divider()
            render_prescriptions(epic, patient_id, llm_provider, wiki)

# ---------------------------------------------------------------------------
# Prescription Section (Extracted for brevity)
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
        for i, rx in enumerate(st.session_state["rx_drafts"]):
            with st.expander(f"**{rx.get('drug_name', '?')}**"):
                st.json(rx) # Minimal placeholder for the detailed card

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

if app_mode == "Patient Workflows":
    render_patient_workflows()
else:
    render_wiki_management()
