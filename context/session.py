from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

@dataclass
class PatientSession:
    """
    Holds all raw patient data for a single workflow run.
    Created at the start of a session and discarded at the end —
    no patient data is written to disk or persisted anywhere.

    Used by: admission workflow, and as the base for DischargeSession.
    """
    patient_id: str
    patient_data: dict          # vitals, labs, demographics, chief complaint
    prior_history: list[dict] = field(default_factory=list)
    ed_notes: str = ""          # ED physician pass-off notes
    handoff_notes: str = ""     # overnight handoff from Epic


@dataclass
class WorkflowState:
    """
    Accumulates agent outputs as a workflow progresses.
    Each step writes its output here; later steps read from it.
    """
    session: PatientSession
    outputs: dict[str, str] = field(default_factory=dict)
    status: str = "running"     # running | complete | error | awaiting_input


# ---------------------------------------------------------------------------
# Discharge-specific data types
# ---------------------------------------------------------------------------

@dataclass
class LabResult:
    """
    A single lab value at a point in time.
    Collected into LabTrend to show movement across a hospitalization.
    """
    name: str
    value: str                  # string to handle both numeric and text results
    unit: str
    reference_range: str
    timestamp: str              # ISO 8601
    is_abnormal: bool = False
    is_critical: bool = False


@dataclass
class LabTrend:
    """
    All values for a single lab test across the hospitalization, in
    chronological order. Agents use this to identify improving vs.
    worsening trends and flag values that are still abnormal at discharge.
    """
    name: str
    unit: str
    results: list[LabResult] = field(default_factory=list)

    @property
    def latest(self) -> Optional[LabResult]:
        return self.results[-1] if self.results else None

    @property
    def admission_value(self) -> Optional[LabResult]:
        return self.results[0] if self.results else None


@dataclass
class ClinicalNote:
    """
    A single note in the patient's chart.
    note_type covers: progress_note | consult | procedure | nursing | discharge_planning
    """
    note_type: str
    author: str
    author_role: str            # resident | attending | fellow | NP | PA | specialist
    specialty: str              # internal_medicine | cardiology | nephrology | etc.
    timestamp: str
    content: str


@dataclass
class ImagingReport:
    """
    A radiology or cardiology imaging report.
    incidental_findings are surfaced explicitly so the TransitionalIssuesAgent
    can flag them without having to parse the full report text.
    """
    modality: str               # CT | MRI | XR | Echo | US | PET
    body_region: str            # chest | abdomen | head | cardiac | etc.
    timestamp: str
    ordering_indication: str
    findings: str
    impression: str
    incidental_findings: list[str] = field(default_factory=list)
    requires_follow_up: bool = False
    follow_up_recommendation: str = ""


@dataclass
class MedicationChange:
    """
    One medication entry in a reconciliation list.
    status captures what changed between admission and discharge:
      continued | new | dose_increased | dose_decreased | discontinued | held
    monitoring_needed surfaces what the outpatient provider must track
    (e.g., "check BMP in 1 week for creatinine and potassium").
    """
    name: str
    dose: str
    route: str
    frequency: str
    status: str
    indication: str
    change_reason: str = ""
    monitoring_needed: str = ""


@dataclass
class VitalsEntry:
    """
    A single vitals snapshot. Collected into a list to show trending
    across the hospitalization (e.g., weight loss from diuresis,
    heart rate normalization, weaning off supplemental oxygen).
    """
    timestamp: str
    heart_rate: Optional[int] = None
    blood_pressure: str = ""
    respiratory_rate: Optional[int] = None
    o2_saturation: Optional[float] = None
    temperature_celsius: Optional[float] = None
    weight_kg: Optional[float] = None
    o2_delivery: str = ""       # RA | 2L NC | 4L NC | NRB | etc.
    fluid_balance_ml: Optional[int] = None


# ---------------------------------------------------------------------------
# Discharge session
# ---------------------------------------------------------------------------

@dataclass
class DischargeSession(PatientSession):
    """
    Full inpatient course data needed for the discharge workflow.

    Extends PatientSession (admission context) with everything that happened
    during the hospitalization: clinical notes, lab trends, imaging reports,
    medication reconciliation, and social context for transitional planning.

    Like PatientSession, this object is created for a single workflow run
    and discarded when complete — no patient data persists.

    EHR source mappings (for future Epic FHIR integration):
      progress_notes    → DocumentReference (type: progress-note)
      consult_notes     → DocumentReference (type: consultation-note)
      procedure_notes   → DocumentReference (type: procedure-note)
      lab_trends        → Observation (category: laboratory), grouped by code
      imaging_reports   → DiagnosticReport (category: imaging)
      admission/discharge_medications → MedicationRequest + MedicationStatement
      vitals_trend      → Observation (category: vital-signs)
    """

    # Hospitalization metadata
    admission_date: str = ""
    discharge_date: str = ""
    length_of_stay_days: int = 0
    admitting_diagnosis: str = ""
    discharge_diagnosis: str = ""
    discharge_disposition: str = ""     # home | SNF | inpatient_rehab | LTACH | AMA

    # Clinical documentation
    progress_notes: list[ClinicalNote] = field(default_factory=list)
    consult_notes: list[ClinicalNote] = field(default_factory=list)
    procedure_notes: list[ClinicalNote] = field(default_factory=list)

    # Lab data — full trends across hospitalization
    lab_trends: list[LabTrend] = field(default_factory=list)

    # Imaging
    imaging_reports: list[ImagingReport] = field(default_factory=list)

    # Medication reconciliation
    admission_medications: list[MedicationChange] = field(default_factory=list)
    discharge_medications: list[MedicationChange] = field(default_factory=list)

    # Vital sign trends (weight trend is critical for CHF)
    vitals_trend: list[VitalsEntry] = field(default_factory=list)

    # Discharge planning context
    pending_follow_ups: list[dict] = field(default_factory=list)    # already scheduled

    # Social and insurance context — critical for transitional issues
    # (a follow-up that the patient can't afford or access is a readmission risk)
    insurance: str = ""
    primary_care_provider: str = ""
    social_support: str = ""            # lives alone | family | assisted living | etc.
    functional_status_at_discharge: str = ""
