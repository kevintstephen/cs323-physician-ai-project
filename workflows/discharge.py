from agents.discharge.inpatient_course import InpatientCourseAgent
from agents.discharge.summary import DischargeSummaryAgent
from agents.discharge.medication_reconciliation import MedicationReconciliationAgent
from agents.discharge.transitional_issues import TransitionalIssuesAgent
from agents.discharge.patient_instructions import PatientInstructionsAgent
from agents.safety import SafetyAgent
from agents.discharge.action_extraction import DischargeActionExtractionAgent
from workflows.engine import WorkflowStep

# ---------------------------------------------------------------------------
# Discharge workflow
#
# Triggered when the attending orders discharge.
#
# Step 1 — InpatientCourseAgent
#   Reads all raw clinical data (notes, labs, imaging, vitals) and produces
#   a structured timeline. Foundation for all downstream steps.
#
# Steps 2 + 3 — DischargeSummaryAgent + MedicationReconciliationAgent
#   Both read from the inpatient course synthesis and can run in parallel
#   (parallel_group=2). Engine currently runs sequentially; group marker
#   is set for when parallel execution is implemented.
#
# Step 4 — TransitionalIssuesAgent
#   The most trust-sensitive output. Scans five explicit categories and
#   sources every item back to the clinical data.
#
# Step 5 — PatientInstructionsAgent
#   Plain-language after-visit summary written for the patient and family.
#
# Step 6 — SafetyAgent
#   Audits the full discharge package before it reaches the physician.
#
# Step 7 — DischargeActionExtractionAgent
#   Reads all prior outputs and produces a single physician sign-off checklist
#   ranked by when each action must happen (before order, before leaving,
#   confirm is arranged). Runs last so it can include safety flags.
# ---------------------------------------------------------------------------

DISCHARGE_STEPS: list[WorkflowStep] = [
    WorkflowStep(
        name="inpatient_course",
        agent_class=InpatientCourseAgent,
    ),
    WorkflowStep(
        name="discharge_summary",
        agent_class=DischargeSummaryAgent,
        context_keys=["inpatient_course"],
        parallel_group=2,
    ),
    WorkflowStep(
        name="medication_reconciliation",
        agent_class=MedicationReconciliationAgent,
        context_keys=["inpatient_course"],
        parallel_group=2,
    ),
    WorkflowStep(
        name="transitional_issues",
        agent_class=TransitionalIssuesAgent,
        context_keys=["inpatient_course", "discharge_summary", "medication_reconciliation"],
    ),
    WorkflowStep(
        name="patient_instructions",
        agent_class=PatientInstructionsAgent,
        context_keys=["inpatient_course", "discharge_summary",
                      "medication_reconciliation", "transitional_issues"],
    ),
    WorkflowStep(
        name="safety_check",
        agent_class=SafetyAgent,
        context_keys=["discharge_summary", "medication_reconciliation", "transitional_issues"],
    ),
    WorkflowStep(
        name="discharge_checklist",
        agent_class=DischargeActionExtractionAgent,
        context_keys=["discharge_summary", "medication_reconciliation",
                      "transitional_issues", "safety_check"],
    ),
]
