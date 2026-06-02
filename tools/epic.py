"""
Epic EHR integration stub.

All methods return sample/mock data built from fixtures in tests/fixtures/.
Replace with real Epic FHIR R4 API calls once integration credentials are available.

Epic developer resources:
  API docs:   https://fhir.epic.com/
  Auth:       OAuth 2.0 with SMART on FHIR
  Sandbox:    https://fhir.epic.com/TestPatients

FHIR resource mappings (for real implementation):
  get_patient()                  → GET /Patient/{id}
  get_labs()                     → GET /Observation?patient={id}&category=laboratory
  get_prior_hospitalizations()   → GET /Encounter?patient={id}&class=IMP
  get_ed_notes()                 → GET /DocumentReference?patient={id}&type=ED-note
  get_handoff_notes()            → GET /DocumentReference?patient={id}&type=handoff
  get_discharge_session()        → Composite of multiple FHIR resources (see below)

TODO: Implement real FHIR API calls
TODO: Add OAuth token refresh logic
TODO: Handle FHIR pagination (_count + next bundle links)
TODO: Add retry logic and timeout handling for Epic downtime
"""

import json
from pathlib import Path

from context.session import (
    ClinicalNote,
    DischargeSession,
    ImagingReport,
    LabResult,
    LabTrend,
    MedicationChange,
    PatientSession,
    VitalsEntry,
)

_FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


class EpicClient:
    def __init__(self, base_url: str = "", access_token: str = ""):
        self.base_url = base_url
        self.access_token = access_token
        self._stub_mode = not base_url

    # -----------------------------------------------------------------------
    # Admission workflow methods
    # -----------------------------------------------------------------------

    def _get_patient_fixture(self, patient_id: str) -> dict:
        """Loads the per-patient fixture file, falling back to sample_patient.json."""
        per_patient = f"patient_{patient_id}.json"
        fixture_path = _FIXTURES_DIR / per_patient
        if fixture_path.exists():
            return self._load_fixture(per_patient)
        return self._load_fixture("sample_patient.json")

    def get_patient(self, patient_id: str) -> dict:
        """Patient demographics, current vitals, labs, medications, allergies."""
        if self._stub_mode:
            return self._get_patient_fixture(patient_id)
        # TODO: GET /Patient/{patient_id} + GET /Observation (current encounter)
        raise NotImplementedError("Epic API integration not yet implemented")

    def get_discharge_patient(self, patient_id: str) -> dict:
        """Returns full inpatient course data for discharge workflows."""
        if self._stub_mode:
            return self._load_fixture("sample_discharge_patient.json")
        # TODO: GET /Encounter/{encounter_id} with full inpatient course
        raise NotImplementedError("Epic API integration not yet implemented")

    def get_labs(self, patient_id: str, encounter_id: str = "") -> dict:
        """Current lab results for the active encounter."""
        if self._stub_mode:
            return self._get_patient_fixture(patient_id).get("labs", {})
        # TODO: GET /Observation?patient={patient_id}&category=laboratory&encounter={encounter_id}
        raise NotImplementedError

    def get_prior_hospitalizations(self, patient_id: str) -> list[dict]:
        """Summarized prior hospitalization records."""
        if self._stub_mode:
            return self._get_patient_fixture(patient_id).get("prior_hospitalizations", [])
        # TODO: GET /Encounter?patient={patient_id}&class=IMP&_sort=-date
        raise NotImplementedError

    def get_ed_notes(self, patient_id: str, encounter_id: str = "") -> str:
        """ED physician pass-off notes for this encounter."""
        if self._stub_mode:
            return self._get_patient_fixture(patient_id).get("ed_assessment", "")
        # TODO: GET /DocumentReference?patient={patient_id}&type=34878-9 (ED note LOINC)
        raise NotImplementedError

    def get_handoff_notes(self, patient_id: str) -> str:
        """Overnight nursing/resident handoff from Epic's handoff notepad."""
        if self._stub_mode:
            return self._get_patient_fixture(patient_id).get("handoff_notes", "")
        # TODO: GET /DocumentReference?patient={patient_id}&type=handoff
        raise NotImplementedError

    # -----------------------------------------------------------------------
    # Discharge workflow method
    # -----------------------------------------------------------------------

    def get_discharge_session(
        self, patient_id: str, encounter_id: str = ""
    ) -> DischargeSession:
        """
        Returns the full inpatient course as a DischargeSession.

        In stub mode, loads from sample_discharge.json.

        In production this would be a composite of several FHIR calls:
          - Patient demographics          → /Patient/{id}
          - Progress/consult/procedure notes → /DocumentReference (by type)
          - Lab trends across encounter   → /Observation?category=laboratory
          - Imaging reports               → /DiagnosticReport?category=imaging
          - Medication reconciliation     → /MedicationRequest + /MedicationStatement
          - Vital signs trend             → /Observation?category=vital-signs
          - Encounter metadata            → /Encounter/{encounter_id}
        """
        if self._stub_mode:
            data = self._load_fixture("sample_discharge.json")
            return self._build_discharge_session(data)
        # TODO: Implement composite FHIR fetch
        raise NotImplementedError("Epic discharge session integration not yet implemented")

    # -----------------------------------------------------------------------
    # Session builders
    # -----------------------------------------------------------------------

    def build_admission_session(self, patient_id: str) -> PatientSession:
        """Convenience method: fetches all admission data and returns a PatientSession."""
        return PatientSession(
            patient_id=patient_id,
            patient_data=self.get_patient(patient_id),
            prior_history=self.get_prior_hospitalizations(patient_id),
            ed_notes=self.get_ed_notes(patient_id),
            handoff_notes=self.get_handoff_notes(patient_id),
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_discharge_session(self, data: dict) -> DischargeSession:
        """
        Constructs a DischargeSession from the raw fixture/API dict.
        Each nested object is built explicitly so the type is enforced at
        construction time rather than at agent call time.
        """
        return DischargeSession(
            # PatientSession base fields
            patient_id=data["patient_id"],
            patient_data=data["patient_data"],
            prior_history=data.get("prior_history", []),
            ed_notes=data.get("ed_notes", ""),
            handoff_notes=data.get("handoff_notes", ""),

            # Hospitalization metadata
            admission_date=data.get("admission_date", ""),
            discharge_date=data.get("discharge_date", ""),
            length_of_stay_days=data.get("length_of_stay_days", 0),
            admitting_diagnosis=data.get("admitting_diagnosis", ""),
            discharge_diagnosis=data.get("discharge_diagnosis", ""),
            discharge_disposition=data.get("discharge_disposition", ""),

            # Clinical notes
            progress_notes=[
                ClinicalNote(**n) for n in data.get("progress_notes", [])
            ],
            consult_notes=[
                ClinicalNote(**n) for n in data.get("consult_notes", [])
            ],
            procedure_notes=[
                ClinicalNote(**n) for n in data.get("procedure_notes", [])
            ],

            # Lab trends
            lab_trends=[
                LabTrend(
                    name=lt["name"],
                    unit=lt["unit"],
                    results=[LabResult(**r) for r in lt.get("results", [])],
                )
                for lt in data.get("lab_trends", [])
            ],

            # Imaging
            imaging_reports=[
                ImagingReport(**r) for r in data.get("imaging_reports", [])
            ],

            # Medication reconciliation
            admission_medications=[
                MedicationChange(**m) for m in data.get("admission_medications", [])
            ],
            discharge_medications=[
                MedicationChange(**m) for m in data.get("discharge_medications", [])
            ],

            # Vital sign trends
            vitals_trend=[
                VitalsEntry(**v) for v in data.get("vitals_trend", [])
            ],

            # Discharge planning context
            pending_follow_ups=data.get("pending_follow_ups", []),
            insurance=data.get("insurance", ""),
            primary_care_provider=data.get("primary_care_provider", ""),
            social_support=data.get("social_support", ""),
            functional_status_at_discharge=data.get("functional_status_at_discharge", ""),
        )

    def _load_fixture(self, filename: str) -> dict:
        fixture_path = _FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")
        return json.loads(fixture_path.read_text())
