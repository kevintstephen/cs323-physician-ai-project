"""
Physician AI — CLI entry point

Usage:
    python main.py admission --patient TEST-001
    python main.py discharge --patient TEST-001
    python main.py case-management --patient TEST-001

All commands use the Epic stub (sample patient data) unless EPIC_BASE_URL is set.
Output is printed to stdout. Redirect to a file to save:
    python main.py admission --patient TEST-001 > output/admission_TEST-001.txt
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

from context.session import PatientSession
from tools.epic import EpicClient
from wiki.loader import load_wiki
from workflows.engine import WorkflowEngine
from workflows.admission import ADMISSION_STEPS
from workflows.discharge import DISCHARGE_STEPS
from workflows.case_management import CASE_MANAGEMENT_STEPS

load_dotenv()

WORKFLOWS = {
    "admission": ADMISSION_STEPS,
    "discharge": DISCHARGE_STEPS,
    "case-management": CASE_MANAGEMENT_STEPS,
}


def build_session(patient_id: str, epic: EpicClient) -> PatientSession:
    patient_data = epic.get_patient(patient_id)
    return PatientSession(
        patient_id=patient_id,
        patient_data=patient_data,
        prior_history=epic.get_prior_hospitalizations(patient_id),
        ed_notes=epic.get_ed_notes(patient_id),
        handoff_notes=epic.get_handoff_notes(patient_id),
    )


def print_results(workflow_name: str, state) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {workflow_name.upper()} WORKFLOW RESULTS — Patient {state.session.patient_id}")
    print(f"{'=' * 70}\n")
    for step_name, output in state.outputs.items():
        print(f"\n{'─' * 70}")
        print(f"  [{step_name.upper().replace('_', ' ')}]")
        print(f"{'─' * 70}\n")
        print(output)
    print(f"\n{'=' * 70}")
    print(f"  Status: {state.status.upper()}")
    print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(description="Physician AI — multi-agent workflow runner")
    parser.add_argument("workflow", choices=list(WORKFLOWS.keys()), help="Workflow to run")
    parser.add_argument("--patient", default="TEST-001", help="Patient ID (default: TEST-001)")
    parser.add_argument("--doctor", default="default", help="Doctor wiki profile to load")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    print(f"\nPhysician AI — running '{args.workflow}' workflow for patient {args.patient}")
    print(f"Loading doctor wiki: {args.doctor}")

    wiki = load_wiki(args.doctor)
    if wiki:
        print(f"Wiki loaded ({len(wiki)} chars)")
    else:
        print("No wiki found — running without doctor context")

    print("Connecting to Epic (stub mode)...")
    epic = EpicClient()
    session = build_session(args.patient, epic)

    client = anthropic.Anthropic(api_key=api_key)
    engine = WorkflowEngine(client=client, wiki=wiki)

    steps = WORKFLOWS[args.workflow]
    print(f"\nRunning {len(steps)} steps:\n")

    state = engine.run(steps, session)
    print_results(args.workflow, state)


if __name__ == "__main__":
    main()
