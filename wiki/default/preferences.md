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
### Patient instructions formatting
- Patient instructions should use plain-language parenthetical definitions for medical terms (e.g., 'diuretic (a medicine that helps your body pass extra water)')
- Provide medication list as a table with columns: medication, dose, when to take, what it's for
- Separate warning signs into 'Go to ER immediately' vs. 'Call doctor within 24 hours' tiers
- Explicitly instruct patient to leave with booked appointment dates/times rather than just referrals
- Address caregiver by name (e.g., daughter) and instruct patient to share the discharge paper with them when relevant
### Patient instructions - appointment booking emphasis
- Patient instructions should include an explicit reminder paragraph directing the patient (and named caregiver) to confirm appointments are booked with dates/times before leaving the hospital, not just referred.
  - Rationale: Empowers patient/caregiver to act as a final check against discharge with unbooked follow-up, especially when living alone with engaged family.
  - Added: 2026-06-02

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
### Discharge summary internal consistency
- Hospital Course narrative and Discharge Medications list must agree on dose and frequency; any discrepancy is a hard stop before sign-off
- Admission and discharge dates must be cross-checked against prior workflow context (chart review, prior notes) to confirm correct hospitalization
- Truncated or incomplete sections (e.g., Follow-Up) must be flagged explicitly and completed before sign-off, not silently passed
### At-a-Glance discharge summary header
- Lead discharge summary with an 'At a Glance' block: why admitted, key intervention, discharge weight vs. dry weight, critical follow-up, and 'Do not miss' incidental findings
- 'Do not miss' section should explicitly enumerate new incidental imaging or echo findings with modality and timeframe for follow-up
### Physician sign-off checklist structure
- Organize discharge checklist into three tiers: 'Before placing the discharge order', 'Before the patient leaves', and 'Confirm is arranged (can delegate but must verify)'
- Each checklist item should cite the relevant Wiki ID(s) inline
- Delegable items must still be explicitly verified by the physician, not assumed complete
### Safety review structure
- Safety review should explicitly call out internal document inconsistencies (dose discrepancies, date mismatches, truncated sections) as flags, not just clinical issues
- When flagging 'consultant aware' language, require confirmation that formal consult was placed and referral is booked
- Include a count of total flags in the overall assessment line
### Clinical Documentation Standards
- In the Assessment & Plan, specify explicit thresholds for downstream actions (e.g., 'start spironolactone when Cr stable and K <5.0') rather than using vague, deferred language.
  - Rationale: Reduces clinical ambiguity and ensures clear, actionable plan-of-care for the multidisciplinary team [WikiID: cfacb2].
### Draft completeness check
- Before sign-off, check that note drafts are not truncated mid-sentence or contain unclosed brackets/sections; flag incomplete drafts explicitly in safety review.
  - Rationale: Truncated notes may omit safety-critical content (e.g., allergy lists, plan items) and pose medico-legal and clinical risk.
### Medication list annotations
- Each home medication in the admission note should be annotated inline with explicit continue/hold/dose-adjust decision AND the specific numerical hold threshold parameters (e.g., 'Hold if SBP <100, Cr >2.0, or K+ >5.0').
  - Rationale: Explicit numerical thresholds prevent ambiguity for covering clinicians and nursing staff regarding when to hold the next dose.
### Prescription agent_notes content
- Prescription agent_notes should include: dose rationale (e.g., 2x home PO for IV loop), explicit hold/escalation triggers with numerical thresholds, discharge transition plan (when to resume home regimen), and PA workflow timing for high-risk agents.
  - Rationale: Consolidating dose logic, safety thresholds, and discharge planning per-medication reduces handoff errors and discharge delays.
### Prescription PA notes
- When a formulary tool flags PA on an inpatient-only medication, explicitly annotate in pa_notes that the flag is a 'false positive' due to Part A DRG bundling, and distinguish from any genuine outpatient Part D PA risk at discharge.
  - Rationale: Disambiguates spurious PA flags from real discharge-time coverage barriers and prevents downstream workflow confusion.
  - Added: 2026-06-02
### Drug info summary content
- Prescription drug_info_summary should explicitly enumerate drug-drug and drug-disease interactions specific to the current patient (e.g., carvedilol masking hypoglycemia in T2DM, furosemide-induced hypokalemia worsened by insulin, lisinopril potentiating hypotension with diuresis) rather than generic class warnings.
  - Rationale: Patient-specific interaction surfacing is more actionable for the care team than generic class-level warnings.
  - Added: 2026-06-02
### Truncated draft handling
- Discharge summaries that terminate mid-sentence or mid-citation (e.g., '[WikiID: b3') must be explicitly flagged as truncated in safety review and blocked from sign-off — do not infer missing sections from prior context.
  - Rationale: Truncated drafts may omit critical sections (Discharge Medications, Follow-Up, Warning Signs); silent completion by reviewer risks fabricating content not authored by the physician.
  - Added: 2026-06-02
### Carry-forward check section
- Transitional Issues drafts should include an explicit 'Carry-Forward Check' section noting prior discharge transitional items reviewed, even if none are unresolved.
  - Rationale: Explicit documentation of the carry-forward review confirms the check was performed, rather than leaving its absence ambiguous.
  - Added: 2026-06-02

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
### Wiki drift audit integrity
- When wiki drift audits encounter conflicting signals (e.g., 'no wiki loaded' but wiki content visible in context), explicitly flag the discrepancy and request physician confirmation rather than proceeding with a PASS verdict.
  - Rationale: Defaulting to PASS on ambiguous source state risks missing actual drift; physician must confirm authoritative wiki version.

## Communication Style

### Safety/High-Risk Tasks
- Include a 'Safety Review' section in workflow outputs to identify potential contraindications (e.g., medication allergies vs. planned treatments) prior to order entry.

### Safety/Verification
- Include a 'Safety Review' or 'Flag' section in handover/charting summaries to explicitly call out unverified high-stakes items or missing administrative data (e.g., admitting physician, disposition)

## Discharge Planning

### Multipurpose cardiology visit framing
- When a single outpatient cardiology visit will address multiple agenda items (e.g., CRT-D candidacy + valve management + GDMT gap closure), explicitly enumerate all agenda items in the transitional issues entry for that visit.
  - Rationale: Enumerating the agenda ensures the consulting cardiologist addresses all items in one visit and prevents items from being deferred across multiple appointments.
  - Added: 2026-06-02
