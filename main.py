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

from context.session import PatientSession
from tools.epic import EpicClient
from wiki.loader import load_wiki
from llm import AnthropicBackend, GeminiBackend
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


def build_session(patient_id: str, epic: EpicClient, workflow: str = "") -> PatientSession:
    if workflow == "discharge":
        patient_data = epic.get_discharge_patient(patient_id)
    else:
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
    parser.add_argument("--llm", choices=["anthropic", "gemini"], default="anthropic", help="LLM provider to use")
    parser.add_argument("--model", help="Specific model to use (optional)")
    args = parser.parse_args()

    if args.llm == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set.")
            sys.exit(1)
        backend = AnthropicBackend(api_key=api_key)
        model = args.model or os.getenv("MODEL", "claude-opus-4-7")
    else:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY not set.")
            sys.exit(1)
        backend = GeminiBackend(api_key=api_key)
        model = args.model or os.getenv("MODEL", "gemini-3.1-flash-lite")

    print(f"\nPhysician AI — running '{args.workflow}' workflow for patient {args.patient}")
    print(f"LLM Provider: {args.llm} (model: {model})")
    print(f"Loading doctor wiki: {args.doctor}")

    wiki = load_wiki(args.doctor)
    if wiki:
        print(f"Wiki loaded ({len(wiki)} chars)")
    else:
        print("No wiki found — running without doctor context")

    print("Connecting to Epic (stub mode)...")
    epic = EpicClient()
    session = build_session(args.patient, epic, workflow=args.workflow)

    engine = WorkflowEngine(backend=backend, model=model, wiki=wiki)

    steps = WORKFLOWS[args.workflow]
    print(f"\nRunning {len(steps)} steps:\n")

    state = engine.run(steps, session)
    print_results(args.workflow, state)


if __name__ == "__main__":
    main()
