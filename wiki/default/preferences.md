# Doctor Preferences

## Communication
### Communication style
- Prefers bullet points over prose for summaries
- Likes transitional issues ranked by urgency, not alphabetically
- Does not need differential diagnoses spelled out for common presentations

### Consultant communication
- Keep pages to 3-4 sentences maximum
- Lead with the one-liner: "I have a [age][sex] with [diagnosis] who needs [consult reason]"
- Nephrologist: always mention baseline creatinine upfront
- Cardiology: always mention ejection fraction if known
- Before paging cardiology for urgent/non-standard consults, confirm with attending first
- When paging cardiology for HF, include: most recent EF, BNP, baseline and current Cr, current GDMT (and notable gaps), and device status
### Consult escalation language
- Distinguish 'consultant aware' from 'formal consult placed' — 'aware' is not sufficient when formal consult is needed
- Always confirm urgent consults with attending before paging
### Case manager pages
- Lead case manager messages with one-liner (age/sex/diagnosis/disposition need), then services requested, then anticipated blockers
- Front-load Part D / prior authorization concerns when new GDMT or high-cost agents are anticipated
### Consultant communication — Cardiology
- When consulting cardiology for HFrEF, include current GDMT regimen and explicitly note any gaps (ARNI, MRA, SGLT2i)
- Mention number of HF admissions in recent timeframe when relevant to device/escalation discussion
### ED handoff clarification
- Always clarify whether ED phrasing such as 'specialty aware' represents a formal consult or a curbside before assuming consultant involvement

## Documentation
### Documentation preferences
- Assessment & Plan: problem-based format, one problem per line
- Prefers specific timelines on follow-up tasks (e.g., "within 1 week" not "soon")
- Flag [VERIFY] on any item that requires bedside exam confirmation
### Safety Check
- Perform a mandatory safety screen for drug-allergy interactions and unaddressed [VERIFY] tags before final note sign-off
- Clearly flag physical exam deficiencies that preclude clinical accuracy in the assessment
### Admission notes
- Include baseline functional status (e.g., ADL independence, ambulation distance) in the HPI for patients with chronic disease
### [VERIFY] tag standards
- Every [VERIFY] item must have an assigned owner (responsible clinician) and a deadline/timeframe
- High-stakes [VERIFY] items (device status, rhythm, oxygen status, exam findings affecting anticoagulation) should be flagged for completion during initial bedside assessment
### Admission H&P standards
- Admission H&P must include: completed Assessment & Plan, problem list, disposition, code status, and orders before sign-off
- Medication list must annotate hold decisions (e.g., metformin during AKI) inline, not deferred to orders only
- Document explicit precipitant workup for any recurrent admission for the same diagnosis
### Verification tags
- Every [VERIFY] tag should have an assigned owner (which provider is responsible for confirming)
- Bedside-confirmable items (SpO2 source, JVP, edema symmetry) should be explicitly flagged for bedside verification
### Outstanding issues from prior discharges
- On chart review, surface unresolved transitional issues from prior discharges (e.g., missed follow-up cath discussion, missed post-discharge labs) and flag for verification
- Rank outstanding prior-discharge items by urgency, not chronologically
### Assessment & Plan content
- A&P must include: target dry weight, goal UOP, explicit medication hold/continue decisions, consult triggers with specific thresholds, code status, and disposition criteria
- Specify explicit thresholds for downstream actions (e.g., 'start spironolactone when Cr stable and K <5.0') rather than vague deferrals
### Safety review handling
- If no document is provided for safety review, do not default to PASS — explicitly require the physician to supply the document
- Safety reviews should re-surface open patient-level concerns from prior wiki entries even when the current document is missing
### Case management draft format
- Use checkbox format ([x]/[ ]) for services needed (home health, PT, OT, DME, oxygen) in case management assessments
- Explicitly enumerate potential discharge blockers as a dedicated section
- Include insurance-specific coverage notes (Part A/B/D, Medigap, SNF qualifying stay) in disposition planning
### [VERIFY] tag usage
- Every [VERIFY] item on a safety-critical issue must have an assigned owner and a timeframe — not just the tag alone
- Explicitly document hold/continue decisions for renally-cleared or renally-sensitive home medications (ACEi, metformin, etc.) in the A&P rather than leaving implied
### Action item structure
- Action items should be categorized by type (verify, lab_order, consult, medication_hold, nursing_order, order) and urgency (now, today, routine)
- Each action item should cite the source workflow step (e.g., ed_note_synthesis, chart_review, lab_interpretation)
### Prescription documentation
- Include agent_notes specifying hold parameters, titration opportunities, and discharge transition plans for each medication
- Flag formulary/PA status even for inpatient meds covered under bundled DRG payment
- List renal-safe alternatives when prescribing in CKD patients
### Chart review output
- Include trend analysis across prior admissions (e.g., progressive weight gain, creatinine trajectory)
- Explicitly list outstanding follow-up items from prior discharges and their current status
- Flag prior decisions (e.g., declined procedures) that may warrant re-discussion this admission
### Case management documentation
- Use checkbox format ([x]/[ ]) for services needed/not needed in case management plans
- Include a draft message to case manager with one-liner summary and specific service requests
- Explicitly list potential blockers categorized by type (clinical, social, medication PA, DME, scheduling)
### Safety review format
- Safety reviews should explicitly state 'Overall assessment' with flag count
- Use 🚩 emoji to denote safety flags
- List both 'Flags' and 'Confirmed safe' items separately
- Do not perform safety clearance without an actual document to review — explicitly note when content is missing

## Workflow
### Workflow preferences
- Rounds at 8:30am — chart review output needed before 8:00am
- Prefers to see sickest patients first in the round order
### Chart review for recurrent admissions
- Trend discharge ('dry') weights across recent admissions to detect creeping euvolemia targets
- Verify completion of outstanding tasks from prior discharges (PCP labs, follow-up imaging, specialist visits) and flag any that were missed
- Count admissions for the same diagnosis within a rolling window (e.g., 7 months) to characterize trajectory
### Chart review structure
- Chart review should surface trends across admissions (e.g., dry weight trajectory, Cr trajectory, recurrent admission pattern) rather than just listing prior diagnoses
- Explicitly cite Wiki IDs inline in chart review, lab interpretation, and consultant routing outputs
### Consultants not needed documentation
- When ruling out a consult, document explicit reason and the threshold/trigger that would prompt reconsideration (e.g., 'reconsider nephrology if Cr rises >30% from baseline')
### Action item structure
- Categorize actions by urgency tiers: now, today, routine
- Tag each action with type (verify, lab_order, nursing_order, consult, order) and source workflow step
- Assign explicit owner/responsible provider to each [VERIFY] item

## Communication Style

### Safety/High-Risk Tasks
- Include a 'Safety Review' section in workflow outputs to identify potential contraindications (e.g., medication allergies vs. planned treatments) prior to order entry.

### Safety/Verification
- Include a 'Safety Review' or 'Flag' section in handover/charting summaries to explicitly call out unverified high-stakes items or missing administrative data (e.g., admitting physician, disposition)
