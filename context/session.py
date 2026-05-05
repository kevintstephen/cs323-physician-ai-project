from dataclasses import dataclass, field


@dataclass
class PatientSession:
    """
    Holds all raw patient data for a single workflow run.
    This object is created at the start of a session and discarded at the end —
    no patient data is written to disk or persisted anywhere.
    """
    patient_id: str
    patient_data: dict  # vitals, labs, demographics, chief complaint
    prior_history: list[dict] = field(default_factory=list)  # prior hospitalization records
    ed_notes: str = ""       # ED physician pass-off notes
    handoff_notes: str = ""  # overnight handoff from Epic


@dataclass
class WorkflowState:
    """
    Accumulates agent outputs as a workflow progresses.
    Each step writes its output here; later steps read from it.
    """
    session: PatientSession
    outputs: dict[str, str] = field(default_factory=dict)  # step_name -> agent output text
    status: str = "running"  # running | complete | error | awaiting_input
