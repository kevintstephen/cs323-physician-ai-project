"""
Epic EHR integration stub.

All methods return sample/mock data. Replace with real Epic FHIR API calls
once integration credentials are available.

Epic's FHIR R4 API docs: https://fhir.epic.com/
Auth: OAuth 2.0 with SMART on FHIR

TODO: Implement real API calls
TODO: Add proper error handling for Epic downtime / timeouts
TODO: Handle Epic's FHIR pagination for large record sets
"""

import json
from pathlib import Path

_FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


class EpicClient:
    def __init__(self, base_url: str = "", access_token: str = ""):
        # TODO: Store credentials for real API calls
        self.base_url = base_url
        self.access_token = access_token
        self._stub_mode = not base_url

    def get_patient(self, patient_id: str) -> dict:
        """Returns patient demographics and current admission data."""
        if self._stub_mode:
            return self._load_fixture("sample_patient.json")
        # TODO: GET /Patient/{patient_id}
        raise NotImplementedError("Epic API integration not yet implemented")

    def get_discharge_patient(self, patient_id: str) -> dict:
        """Returns full inpatient course data for discharge workflows."""
        if self._stub_mode:
            return self._load_fixture("sample_discharge_patient.json")
        # TODO: GET /Encounter/{encounter_id} with full inpatient course
        raise NotImplementedError("Epic API integration not yet implemented")

    def get_labs(self, patient_id: str, encounter_id: str = "") -> dict:
        """Returns current lab results."""
        if self._stub_mode:
            patient = self._load_fixture("sample_patient.json")
            return patient.get("labs", {})
        # TODO: GET /Observation?patient={patient_id}&category=laboratory
        raise NotImplementedError

    def get_prior_hospitalizations(self, patient_id: str) -> list[dict]:
        """Returns prior hospitalization summaries."""
        if self._stub_mode:
            patient = self._load_fixture("sample_patient.json")
            return patient.get("prior_hospitalizations", [])
        # TODO: GET /Encounter?patient={patient_id}&class=IMP
        raise NotImplementedError

    def get_ed_notes(self, patient_id: str, encounter_id: str = "") -> str:
        """Returns the ED physician pass-off notes for this encounter."""
        if self._stub_mode:
            patient = self._load_fixture("sample_patient.json")
            return patient.get("ed_assessment", "")
        # TODO: GET /DocumentReference?patient={patient_id}&type=ED-note
        raise NotImplementedError

    def get_handoff_notes(self, patient_id: str) -> str:
        """Returns the overnight Epic handoff notepad."""
        if self._stub_mode:
            patient = self._load_fixture("sample_patient.json")
            return patient.get("handoff_notes", "")
        # TODO: GET /DocumentReference?patient={patient_id}&type=handoff
        raise NotImplementedError

    def _load_fixture(self, filename: str) -> dict:
        fixture_path = _FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")
        return json.loads(fixture_path.read_text())
