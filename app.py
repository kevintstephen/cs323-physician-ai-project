"""
Physician AI — Streamlit frontend

Run with:
    streamlit run app.py

The physician selects a patient in the sidebar, then uses contextual action
buttons to trigger agentic workflows. Each step streams progress in real time
via st.status() as the agent network runs.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from tools.epic import EpicClient
from wiki.loader import load_wiki
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
# Sidebar — patient + LLM selection
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🏥 Physician AI")
    st.caption("Multi-agent clinical workflow assistant")
    st.divider()

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

    # Active problem list — always visible in sidebar
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
        st.caption("No workflows run yet for this patient.")

    st.divider()
    st.caption("Stanford CS323 — AI Awakening")


# ---------------------------------------------------------------------------
# LLM backend setup
# ---------------------------------------------------------------------------

def get_backend(provider: str):
    """
    Returns (backend, model) for the selected LLM provider.
    Not cached — the client is cheap to create and caching causes stale
    class references after hot-reloads (AttributeError on new methods).
    """
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


@st.cache_data
def get_wiki(doctor: str = "default") -> str:
    return load_wiki(doctor) or ""


# ---------------------------------------------------------------------------
# Patient summary card
# ---------------------------------------------------------------------------

epic = get_epic()
wiki = get_wiki()

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

# ---------------------------------------------------------------------------
# Patient chart — tabbed intake data
# ---------------------------------------------------------------------------

with st.expander("📂 Patient Chart", expanded=True):
    tab_overview, tab_labs, tab_meds, tab_ed, tab_history = st.tabs(
        ["Overview", "Labs", "Medications & Allergies", "ED & Handoff Notes", "Prior Hospitalizations"]
    )

    # ── Overview ────────────────────────────────────────────────────────────
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

    # ── Labs ────────────────────────────────────────────────────────────────
    with tab_labs:
        labs = patient_data.get("labs", {})
        if labs:
            # Reference ranges and units for display
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

            # Flag abnormals simply by comparing to rough thresholds
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
                    if check and check(float(value)):
                        flag = "⚠️"
                except (TypeError, ValueError):
                    pass
                rows.append({
                    "Test": f"{flag} {name}".strip(),
                    "Value": f"{value} {unit}".strip(),
                    "Reference": ref,
                })

            import pandas as pd
            st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No labs on file.")

    # ── Medications & Allergies ──────────────────────────────────────────────
    with tab_meds:
        med_col1, med_col2 = st.columns(2)

        with med_col1:
            st.markdown("**Current Medications**")
            for med in patient_data.get("current_medications", []):
                st.markdown(f"- {med}")

        with med_col2:
            st.markdown("**Allergies**")
            allergies = patient_data.get("allergies", [])
            if allergies:
                for a in allergies:
                    st.markdown(f"- **{a.get('drug', '?')}** — {a.get('reaction', '?')}")
            else:
                st.markdown("NKDA")

    # ── ED & Handoff Notes ───────────────────────────────────────────────────
    with tab_ed:
        st.markdown("**ED Physician Assessment**")
        st.markdown(patient_data.get("ed_assessment", "No ED note on file."))
        st.divider()
        st.markdown("**Overnight Handoff Notes**")
        st.markdown(patient_data.get("handoff_notes", "No handoff notes on file."))

    # ── Prior Hospitalizations ───────────────────────────────────────────────
    with tab_history:
        prior = patient_data.get("prior_hospitalizations", [])
        if prior:
            for hosp in prior:
                label = f"{hosp.get('date', '?')} — {hosp.get('reason', '?')}  ({hosp.get('length_of_stay_days', '?')} days)"
                with st.expander(label, expanded=False):
                    st.markdown(f"**Treatment:** {hosp.get('treatment', '—')}")
                    st.markdown(f"**Discharge weight:** {hosp.get('discharge_weight_kg', '?')} kg")
                    st.markdown(f"**Transitional issues:** {hosp.get('transitional_issues', '—')}")
        else:
            st.caption("No prior hospitalizations on file.")


# ---------------------------------------------------------------------------
# Patient history timeline — grows with each completed workflow
# ---------------------------------------------------------------------------

patient_ctx = PatientContext.load(patient_id)

if patient_ctx.workflow_history:
    with st.expander("🕓 Patient History", expanded=False):
        for rec in reversed(patient_ctx.workflow_history):
            date = rec.timestamp[:10]
            time = rec.timestamp[11:16]
            col_label, col_body = st.columns([1, 4])
            col_label.markdown(
                f"**{rec.workflow.replace('_', ' ').title()}**\n\n"
                f"<small>{date} {time} UTC</small>",
                unsafe_allow_html=True,
            )
            with col_body:
                st.markdown(rec.summary)
                if rec.key_findings:
                    st.markdown("**Key findings:** " + " · ".join(rec.key_findings))
                if rec.open_issues:
                    for issue in rec.open_issues:
                        st.markdown(f"⚠️ {issue}")
                if rec.resolved_issues:
                    for res in rec.resolved_issues:
                        st.markdown(f"✅ {res}")
            st.divider()

st.divider()

# ---------------------------------------------------------------------------
# Workflow action buttons
# ---------------------------------------------------------------------------

st.markdown("### Actions")

btn_col1, btn_col2, btn_col3 = st.columns(3)

admit_clicked     = btn_col1.button("🏥 Admit Patient",      use_container_width=True)
review_clicked    = btn_col2.button("📋 Review Updates",     use_container_width=True)
discharge_clicked = btn_col3.button("🚪 Discharge Patient",  use_container_width=True)

# ---------------------------------------------------------------------------
# Workflow runner
# ---------------------------------------------------------------------------

def run_workflow(label: str, workflow_name: str, steps: list, session_fn):
    """
    Runs a workflow pipeline and stores results in session_state.
    Loads patient context before the run (so agents see prior history),
    then saves the updated context after synthesis completes.
    Streams per-step progress via st.status().
    """
    backend, model = get_backend(llm_provider)
    engine = WorkflowEngine(backend=backend, model=model, wiki=wiki)

    try:
        session = session_fn()
    except Exception as e:
        st.error(f"Could not load session data: {e}")
        return

    # Load (or create) the running patient context for this patient
    ctx = PatientContext.load(patient_id)

    st.session_state["active_workflow"] = label
    st.session_state["workflow_outputs"] = {}
    st.session_state["workflow_complete"] = False
    st.session_state["completed_actions"] = set()  # reset action checklist

    with st.status(f"Running {label}...", expanded=True) as status:
        for step_name, output, state in engine.run_steps(
            steps, session,
            patient_context=ctx,
            workflow_name=workflow_name,
        ):
            if step_name == "context_synthesis":
                st.write("✓ Patient context updated")
            else:
                friendly = step_name.replace("_", " ").title()
                st.write(f"✓ {friendly}")
            if output is not None:
                st.session_state["workflow_outputs"][step_name] = output.content

        status.update(label=f"{label} complete", state="complete")

    st.session_state["workflow_complete"] = True
    st.session_state["final_state"] = state
    # Rerun so sidebar + history panel reflect the newly saved context.
    # Outputs are already in session_state so the results panel renders correctly.
    st.rerun()


if admit_clicked:
    run_workflow(
        label="Admission Workflow",
        workflow_name="admission",
        steps=ADMISSION_STEPS,
        session_fn=lambda: epic.build_admission_session(patient_id),
    )

if review_clicked:
    run_workflow(
        label="Case Management",
        workflow_name="case_management",
        steps=CASE_MANAGEMENT_STEPS,
        session_fn=lambda: epic.build_admission_session(patient_id),
    )

if discharge_clicked:
    run_workflow(
        label="Discharge Workflow",
        workflow_name="discharge",
        steps=DISCHARGE_STEPS,
        session_fn=lambda: epic.get_discharge_session(patient_id),
    )

# ---------------------------------------------------------------------------
# Prescription drafting — on-demand agent with tool use
# (defined before the results block so they're in scope when called)
# ---------------------------------------------------------------------------

def _run_prescription_agent():
    """Runs the PrescriptionDraftAgent and stores parsed drafts in session_state."""
    backend, model = get_backend(llm_provider)
    agent = PrescriptionDraftAgent(backend=backend, model=model)

    outputs = st.session_state.get("workflow_outputs", {})
    session = epic.build_admission_session(patient_id)
    context = {
        "patient_id": patient_id,
        "patient_data": session.patient_data,
        "ed_notes": session.ed_notes,
        "chart_review": outputs.get("chart_review", ""),
        "lab_interpretation": outputs.get("lab_interpretation", ""),
        "ed_note_synthesis": outputs.get("ed_note_synthesis", ""),
        "note_draft": outputs.get("note_draft", ""),
    }

    with st.status("Drafting prescriptions — calling drug database and PA checker...", expanded=True) as status:
        st.write("🔍 Analysing admission notes...")
        output = agent.run(context, wiki=wiki)
        st.write("✓ Tool lookups complete")
        st.write("✓ Prescriptions drafted")
        status.update(label="Drafts ready — review below", state="complete")

    drafts = agent.parse_prescriptions(output.content)
    st.session_state["prescription_drafts"] = drafts
    st.rerun()


def _render_rx_card(idx: int, rx: dict):
    """Renders one editable prescription card with PA status and approve/discard buttons."""
    pa_required = rx.get("pa_required", False)
    pa_pct = rx.get("pa_likelihood_pct")

    if pa_required:
        badge = f"🔴 PA Required (~{pa_pct}% approval)" if pa_pct else "🔴 PA Required"
    else:
        badge = "🟢 No PA Required"

    with st.expander(
        f"**{rx.get('drug_name', '?')}** {rx.get('dose', '')} — {badge}",
        expanded=True,
    ):
        c1, c2, c3 = st.columns(3)
        drug_name = c1.text_input("Drug name", value=rx.get("drug_name", ""), key=f"rx_drug_{idx}")
        dose      = c2.text_input("Dose",      value=rx.get("dose", ""),      key=f"rx_dose_{idx}")
        route_opts = ["PO", "IV", "SQ", "inhaled", "topical"]
        route     = c3.selectbox(
            "Route", route_opts,
            index=route_opts.index(rx.get("route", "PO")) if rx.get("route", "PO") in route_opts else 0,
            key=f"rx_route_{idx}",
        )

        c4, c5, c6 = st.columns(3)
        frequency = c4.text_input("Frequency", value=rx.get("frequency", ""), key=f"rx_freq_{idx}")
        quantity  = c5.text_input("Quantity",  value=rx.get("quantity", ""),  key=f"rx_qty_{idx}")
        refills   = c6.text_input("Refills",   value=rx.get("refills", "0"),  key=f"rx_ref_{idx}")

        indication = st.text_input("Indication", value=rx.get("indication", ""), key=f"rx_ind_{idx}")
        notes      = st.text_area("Agent notes / monitoring", value=rx.get("agent_notes", ""),
                                  height=80, key=f"rx_notes_{idx}")

        if rx.get("drug_info_summary"):
            st.caption(f"ℹ️ **Drug info:** {rx['drug_info_summary']}")
        if rx.get("pa_notes"):
            if pa_required:
                st.warning(f"**PA:** {rx['pa_notes']}")
            else:
                st.caption(f"**PA:** {rx['pa_notes']}")
        if rx.get("alternatives"):
            st.caption("**Alternatives:** " + " · ".join(rx["alternatives"]))

        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        if btn_col1.button("✓ Approve", key=f"approve_{idx}", type="primary"):
            st.session_state["approved_orders"].append({
                "_idx": idx,
                "drug_name": drug_name,
                "dose": dose,
                "route": route,
                "frequency": frequency,
                "quantity": quantity,
                "refills": refills,
                "indication": indication,
                "notes": notes,
                "status": "pending_pharmacy",
            })
            st.rerun()
        if btn_col2.button("✗ Discard", key=f"discard_{idx}"):
            st.session_state["approved_orders"].append({"_idx": idx, "status": "discarded"})
            st.rerun()


def _render_prescription_section():
    """Renders the full prescription drafting section below the admission results."""
    st.markdown("### 💊 Prescription Orders")

    if "prescription_drafts" not in st.session_state:
        st.session_state["prescription_drafts"] = []
    if "approved_orders" not in st.session_state:
        st.session_state["approved_orders"] = []

    # ── Draft button ──────────────────────────────────────────────────────────
    if not st.session_state["prescription_drafts"]:
        st.caption(
            "The agent will read the admission notes, call the FDA drug database "
            "and prior auth checker for each medication, then draft editable orders."
        )
        if st.button("🤖 Draft Prescriptions", type="primary"):
            _run_prescription_agent()

    # ── Editable prescription cards ───────────────────────────────────────────
    if st.session_state["prescription_drafts"]:
        approved_idxs = {o["_idx"] for o in st.session_state["approved_orders"]}
        pending = [i for i in range(len(st.session_state["prescription_drafts"]))
                   if i not in approved_idxs]

        if pending:
            st.caption(f"{len(pending)} order(s) awaiting review · Edit any field before approving.")
        else:
            st.success("✅ All orders reviewed.")

        for idx in pending:
            _render_rx_card(idx, st.session_state["prescription_drafts"][idx])

        if st.button("🔄 Re-draft from scratch", type="secondary"):
            st.session_state["prescription_drafts"] = []
            st.session_state["approved_orders"] = []
            st.rerun()

    # ── Pharmacy queue ────────────────────────────────────────────────────────
    pharmacy_orders = [o for o in st.session_state.get("approved_orders", [])
                       if o.get("status") == "pending_pharmacy"]
    if pharmacy_orders:
        st.divider()
        st.markdown("#### 📬 Pharmacy Queue")
        for order in pharmacy_orders:
            col1, col2 = st.columns([4, 1])
            col1.markdown(
                f"**{order['drug_name']}** {order['dose']} {order['route']} "
                f"{order['frequency']} — *{order['indication']}*"
            )
            col2.markdown("🟡 Pending pharmacy")


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

if st.session_state.get("workflow_complete") and st.session_state.get("workflow_outputs"):
    outputs = st.session_state["workflow_outputs"]
    workflow_label = st.session_state.get("active_workflow", "Workflow")
    is_admission = workflow_label == "Admission Workflow"

    st.divider()
    st.markdown(f"### {workflow_label} Results")

    # ── Zone 1: Action list (admission only) ─────────────────────────────────
    if is_admission and "action_extraction" in outputs:
        raw_ae = outputs["action_extraction"]
        with st.expander("🐛 [DEBUG] Raw action_extraction output", expanded=False):
            st.text(raw_ae[:3000])
        actions = ActionExtractionAgent.parse_actions(raw_ae)

        if "completed_actions" not in st.session_state:
            st.session_state["completed_actions"] = set()

        pending   = [a for i, a in enumerate(actions) if i not in st.session_state["completed_actions"]]
        completed = [a for i, a in enumerate(actions) if i in st.session_state["completed_actions"]]
        total     = len(actions)
        done      = len(completed)

        # Progress bar
        if total:
            st.progress(done / total, text=f"{done} of {total} actions complete")

        # Render by urgency group
        for urgency_key in ("now", "today", "routine"):
            group = [(i, a) for i, a in enumerate(actions)
                     if a.get("urgency") == urgency_key
                     and i not in st.session_state["completed_actions"]]
            if not group:
                continue

            icon, label, _ = URGENCY_CONFIG[urgency_key]
            st.markdown(f"#### {icon} {label}")

            for idx, action in group:
                a_icon, a_label = ACTION_TYPES.get(action.get("type", "order"), ("📋", "Order"))
                col_check, col_badge, col_content = st.columns([0.5, 1, 8])

                if col_check.button("✓", key=f"action_done_{idx}", help="Mark complete"):
                    st.session_state["completed_actions"].add(idx)
                    st.rerun()

                col_badge.markdown(
                    f"<span style='background:#f0f0f0;padding:2px 6px;"
                    f"border-radius:4px;font-size:0.75em'>{a_icon} {a_label}</span>",
                    unsafe_allow_html=True,
                )

                with col_content:
                    st.markdown(f"**{action.get('title', '')}**")
                    if action.get("detail"):
                        st.caption(action["detail"])

            st.markdown("")  # spacing between groups

        # Completed actions — collapsed
        if completed:
            with st.expander(f"✅ Completed ({done})", expanded=False):
                for i, a in enumerate(actions):
                    if i in st.session_state["completed_actions"]:
                        a_icon, _ = ACTION_TYPES.get(a.get("type", "order"), ("📋", ""))
                        st.markdown(f"~~{a_icon} {a.get('title', '')}~~")

        st.divider()

    # ── Zone 2: Safety check banner ───────────────────────────────────────────
    if "safety_check" in outputs:
        safety_text = outputs["safety_check"]
        flag_words = ["flag", "concern", "warning", "risk", "alert", "caution", "attention"]
        has_flags = any(w in safety_text.lower() for w in flag_words)
        with st.expander(
            "🔴 Safety Check — Flags Identified" if has_flags else "🟢 Safety Check — Clear",
            expanded=has_flags,
        ):
            st.markdown(safety_text)

    # ── Zone 3: Full agent outputs (collapsed) ────────────────────────────────
    _internal = {"safety_check", "context_synthesis", "action_extraction"}
    with st.expander("📄 Full Agent Outputs", expanded=False):
        for step_name, content in outputs.items():
            if step_name in _internal:
                continue
            friendly = step_name.replace("_", " ").title()
            st.markdown(f"##### {friendly}")
            st.markdown(content)
            st.markdown("---")

    # ── Prescription section (admission only) ─────────────────────────────────
    if is_admission:
        st.divider()
        _render_prescription_section()
