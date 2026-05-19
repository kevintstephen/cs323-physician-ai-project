# Physician AI — CS323 Project

A multi-agent system that assists physicians with high-burden clinical workflows: admission workups, discharge documentation, and case management coordination.

## Quick start

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd cs323-physician-ai-project

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY or GEMINI_API_KEY

# 5. Run the admission workflow on sample patient data
python main.py admission --patient TEST-001 --llm (gemini or default:anthropic)

# 6. Open front-end with Streamlit
streamlit run app.py
```

The sample patient (TEST-001) is a 67-year-old CHF patient — a realistic EM case based on our physician interviews. No real patient data is used.

## Project structure

```
.
├── agents/
│   ├── base.py                   # BaseAgent — extend this to add a new agent
│   ├── safety.py                 # Safety auditor — runs at end of every workflow
│   ├── admission/                # Admission workflow agents (complete)
│   │   ├── chart_review.py
│   │   ├── lab_interpretation.py
│   │   ├── ed_note_synthesis.py
│   │   ├── consultant_routing.py
│   │   └── note_drafter.py
│   ├── discharge/                # Discharge workflow agents (stubs — build these next)
│   │   ├── summary.py
│   │   └── transitional_issues.py
│   └── case_management/          # Case management agents (stub — needs sub-agents)
│       └── coordinator.py
├── workflows/
│   ├── engine.py                 # DAG runner — never needs to change
│   ├── admission.py              # Admission workflow definition
│   ├── discharge.py              # Discharge workflow definition
│   └── case_management.py        # Case management workflow definition
├── context/
│   └── session.py                # PatientSession, WorkflowState data models
├── wiki/
│   ├── loader.py                 # Loads doctor's wiki from markdown files
│   └── doctor/                   # Doctor's accumulated clinical preferences
│       ├── preferences.md
│       └── clinical_protocols.md
├── tools/
│   └── epic.py                   # Epic EHR client (stub — returns sample data)
├── tests/
│   ├── test_admission_workflow.py
│   └── fixtures/
│       └── sample_patient.json   # Realistic CHF patient for local testing
└── main.py                       # CLI entry point
```

## Running workflows

```bash
# Admission workup
python main.py admission --patient TEST-001

# Discharge documentation
python main.py discharge --patient TEST-001

# Case management assessment
python main.py case-management --patient TEST-001

# Save output to a file
python main.py admission --patient TEST-001 > output.txt
```

## Running tests

```bash
pytest tests/ -v
```

Tests use mocked Anthropic responses — no API key required to run them.

## How to add a new agent

1. Create a file in `agents/<workflow>/your_agent.py`
2. Extend `BaseAgent` and implement `name`, `system_prompt`, and `format_prompt()`
3. Add it as a `WorkflowStep` in the relevant `workflows/<workflow>.py`

```python
# agents/admission/my_new_agent.py
from agents.base import BaseAgent

class MyNewAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "my_new_step"

    @property
    def system_prompt(self) -> str:
        return "You are a ... Your job is to ..."

    def format_prompt(self, context: dict) -> str:
        return f"Patient data: {context['patient_data']}\n\nPlease ..."
```

```python
# workflows/admission.py — add to ADMISSION_STEPS
WorkflowStep(
    name="my_new_step",
    agent_class=MyNewAgent,
    context_keys=["chart_review"],  # which prior outputs to pass in
),
```

The engine handles the rest.

## How to add a new workflow

1. Create agent files in `agents/<new_workflow>/`
2. Create `workflows/<new_workflow>.py` with a `NEW_WORKFLOW_STEPS` list
3. Import and register it in `main.py`

## How the wiki works

The `wiki/doctor/` directory contains markdown files describing how this doctor practices. Every agent receives this content as a cached system context, so personalization is automatic.

To update the wiki, edit the markdown files. To add a new page, create a new `.md` file in `wiki/doctor/` — it's loaded automatically.

## Architecture

```
PatientSession (created, used, discarded — no patient data persisted)
       │
       ▼
WorkflowEngine.run(steps, session)
       │
       ├── WorkflowStep: chart_review     ──┐
       ├── WorkflowStep: lab_interpretation  ├── parallel_group=1 (future)
       ├── WorkflowStep: ed_note_synthesis ──┘
       │
       ├── WorkflowStep: consultant_routing  (reads outputs from group 1)
       ├── WorkflowStep: note_draft          (reads all prior outputs)
       └── WorkflowStep: safety_check        (audits final draft)
                                                    │
                                                    ▼
                                          WorkflowState (outputs dict)
                                                    │
                                                    ▼
                                          Physician reviews + acts
```

Each agent call uses **prompt caching** on the system prompt and doctor wiki — the two stable, reused inputs. Only the patient-specific user message is uncached. This reduces latency and cost for multi-step workflows.

## Model

Default: `claude-opus-4-7`. Override in `.env`:
```
MODEL=claude-sonnet-4-6
```

## What's implemented vs. what's a stub

| Component | Status |
|---|---|
| Admission workflow (all 6 steps) | Complete |
| Discharge: hospital course summary | Stub — needs full prompt |
| Discharge: transitional issues | Stub — needs full prompt |
| Case management: coordinator | Stub — needs to be broken into sub-agents |
| Epic integration | Stub — returns sample data |
| Async workflow state (for multi-day case mgmt) | Not started |
| Parallel step execution | Architecture supports it; engine runs sequentially |

## Team

Kevin, Isabel, Kristi — Stanford CS323, Spring 2026
