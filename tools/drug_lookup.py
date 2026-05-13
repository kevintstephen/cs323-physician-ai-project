"""
Drug lookup tools for the PrescriptionDraftAgent.

Three tools:
  look_up_drug_info   — real OpenFDA drug label API (live HTTP call)
  check_prior_auth    — mock formulary with realistic CHF drug PA tiers
  get_alternatives    — therapeutic alternatives when PA is required

Tool definitions are provided in Anthropic function-calling format (ANTHROPIC_TOOL_DEFS)
and as a backend-agnostic list (TOOL_DEFS) for the fallback generate_with_tools path.
"""

import json
import urllib.parse
import urllib.request


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def look_up_drug_info(drug_name: str) -> str:
    """
    Calls the OpenFDA drug label endpoint.
    Returns truncated sections: dosing, warnings, interactions, adverse reactions.
    Falls back gracefully if the API is unreachable or the drug isn't found.
    """
    try:
        query = urllib.parse.quote(f'"{drug_name}"')
        url = (
            f"https://api.fda.gov/drug/label.json"
            f"?search=openfda.generic_name:{query}&limit=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "PhysicianAI/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        result = data["results"][0]
        SECTIONS = [
            "indications_and_usage",
            "dosage_and_administration",
            "warnings_and_cautions",
            "warnings",
            "drug_interactions",
            "adverse_reactions",
            "contraindications",
        ]
        summary = {}
        for key in SECTIONS:
            if key in result:
                val = result[key]
                if isinstance(val, list):
                    val = val[0]
                # Truncate long sections — agents don't need full label text
                summary[key] = val[:600].strip()

        # Also surface the brand/generic names if available
        openfda = result.get("openfda", {})
        summary["generic_name"] = openfda.get("generic_name", [drug_name])[0]
        summary["brand_name"] = openfda.get("brand_name", [""])[0]

        return json.dumps(summary)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({
                "note": f"No FDA label found for '{drug_name}'. "
                        "Verify drug name or consult pharmacist.",
            })
        return json.dumps({"error": f"FDA API error {e.code}: {e.reason}"})
    except Exception as e:
        return json.dumps({"error": f"Could not retrieve drug info: {str(e)}"})


# ---------------------------------------------------------------------------
# Prior auth mock — realistic CHF formulary tier table
# ---------------------------------------------------------------------------

# (tier, pa_required, approval_likelihood_pct, clinical_notes)
_FORMULARY: dict[str, tuple] = {
    # Loop diuretics
    "furosemide":            (1, False, 99,  "Preferred generic diuretic. No PA required."),
    "lasix":                 (1, False, 99,  "Brand Lasix; generic furosemide preferred but no PA."),
    "torsemide":             (2, False, 90,  "Tier 2. No PA required but step therapy may apply."),
    "bumetanide":            (2, False, 88,  "Tier 2. No PA required."),
    # Aldosterone antagonists
    "spironolactone":        (1, False, 95,  "Preferred. No PA required for standard HF doses."),
    "eplerenone":            (2, True,  78,  "Tier 2. PA may be required. Document intolerance to spironolactone."),
    # Thiazide-like
    "metolazone":            (2, True,  80,  "Tier 2. PA may be required. Used for diuretic resistance."),
    # ACE inhibitors
    "lisinopril":            (1, False, 99,  "Preferred ACE inhibitor. No PA required."),
    "enalapril":             (1, False, 99,  "Preferred ACE inhibitor. No PA required."),
    "ramipril":              (1, False, 99,  "Preferred ACE inhibitor. No PA required."),
    # ARBs
    "losartan":              (1, False, 99,  "Preferred ARB. No PA required."),
    "valsartan":             (1, False, 99,  "Preferred ARB. No PA required."),
    "candesartan":           (2, False, 90,  "Tier 2 ARB. No PA required."),
    # ARNI
    "sacubitril/valsartan":  (3, True,  65,  "Entresto — Tier 3. PA required. Must document LVEF ≤40% and prior ACE/ARB trial. Approval rate ~65%."),
    "entresto":              (3, True,  65,  "Sacubitril/valsartan — Tier 3. PA required. Must document LVEF ≤40% and prior ACE/ARB trial. Approval rate ~65%."),
    # Beta-blockers
    "carvedilol":            (1, False, 99,  "Preferred beta-blocker. No PA required."),
    "metoprolol succinate":  (1, False, 99,  "Preferred beta-blocker. No PA required."),
    "bisoprolol":            (1, False, 99,  "Preferred beta-blocker. No PA required."),
    # SGLT2 inhibitors
    "empagliflozin":         (3, True,  70,  "Jardiance — Tier 3. PA required for HF indication. Requires HFrEF documentation. Approval rate ~70%."),
    "jardiance":             (3, True,  70,  "Empagliflozin — Tier 3. PA required for HF indication. Approval rate ~70%."),
    "dapagliflozin":         (3, True,  70,  "Farxiga — Tier 3. PA required for HF indication. Approval rate ~70%."),
    "farxiga":               (3, True,  70,  "Dapagliflozin — Tier 3. PA required for HF indication. Approval rate ~70%."),
    # If channel blocker
    "ivabradine":            (4, True,  45,  "Corlanor — Tier 4 specialty. Strict criteria: sinus rhythm, HR ≥70, LVEF ≤35%, maximally tolerated beta-blocker. Approval rate ~45%."),
    # Digoxin
    "digoxin":               (2, False, 85,  "Tier 2. No PA required. Serum level monitoring required."),
    # Vasodilators
    "hydralazine":           (1, False, 99,  "Preferred generic. No PA required."),
    "isosorbide dinitrate":  (1, False, 99,  "Preferred generic. No PA required."),
    # Electrolytes / supplements
    "potassium chloride":    (1, False, 99,  "Tier 1 / OTC. No PA required."),
    "magnesium oxide":       (1, False, 99,  "OTC. No PA required."),
    # Statins
    "atorvastatin":          (1, False, 99,  "Preferred statin. No PA required."),
    "rosuvastatin":          (1, False, 99,  "Preferred statin. No PA required."),
    # Antiplatelet / anticoagulant
    "aspirin":               (1, False, 99,  "OTC. No PA required."),
    "clopidogrel":           (1, False, 99,  "Preferred generic. No PA required."),
    "warfarin":              (1, False, 99,  "Preferred anticoagulant for some indications. INR monitoring required."),
    "apixaban":              (3, True,  72,  "Eliquis — Tier 3. PA required for AFib/VTE. Approval rate ~72%."),
    "eliquis":               (3, True,  72,  "Apixaban — Tier 3. PA required for AFib/VTE. Approval rate ~72%."),
    "rivaroxaban":           (3, True,  70,  "Xarelto — Tier 3. PA required. Approval rate ~70%."),
    "xarelto":               (3, True,  70,  "Rivaroxaban — Tier 3. PA required. Approval rate ~70%."),
    # Diabetes
    "metformin":             (1, False, 99,  "Preferred for T2DM. No PA required."),
    "insulin glargine":      (2, False, 90,  "Tier 2 insulin. No PA required."),
}

_ALTERNATIVES: dict[str, list[str]] = {
    "sacubitril/valsartan": ["lisinopril 10–40mg daily (Tier 1, no PA)", "valsartan 40–160mg twice daily (Tier 1, no PA)"],
    "entresto":             ["lisinopril 10–40mg daily (Tier 1, no PA)", "valsartan 40–160mg twice daily (Tier 1, no PA)"],
    "empagliflozin":        ["dapagliflozin 10mg daily (same tier/PA)", "spironolactone 25mg daily (Tier 1, no PA, different mechanism)"],
    "jardiance":            ["dapagliflozin 10mg daily (same tier/PA)", "spironolactone 25mg daily (Tier 1, no PA, different mechanism)"],
    "dapagliflozin":        ["empagliflozin 10mg daily (same tier/PA)", "spironolactone 25mg daily (Tier 1, no PA, different mechanism)"],
    "farxiga":              ["empagliflozin 10mg daily (same tier/PA)", "spironolactone 25mg daily (Tier 1, no PA, different mechanism)"],
    "eplerenone":           ["spironolactone 25–50mg daily (Tier 1, no PA, first-line)"],
    "torsemide":            ["furosemide 40–80mg daily (Tier 1, no PA, preferred)"],
    "metolazone":           ["chlorothiazide IV (Tier 2, no PA, IV option for diuretic resistance)"],
    "ivabradine":           ["maximize carvedilol or metoprolol succinate to max tolerated dose first"],
    "apixaban":             ["warfarin (Tier 1, no PA, requires INR monitoring)", "rivaroxaban 20mg daily (similar tier/PA)"],
    "eliquis":              ["warfarin (Tier 1, no PA, requires INR monitoring)", "rivaroxaban 20mg daily (similar tier/PA)"],
    "rivaroxaban":          ["warfarin (Tier 1, no PA, requires INR monitoring)", "apixaban 5mg twice daily (similar tier/PA)"],
    "xarelto":              ["warfarin (Tier 1, no PA, requires INR monitoring)", "apixaban 5mg twice daily (similar tier/PA)"],
}


def check_prior_auth(drug_name: str, dose: str, indication: str, insurance: str) -> str:
    """
    Checks prior authorization likelihood against a mock formulary.
    Covers CHF, HFrEF, AFib, VTE, and T2DM drug classes with realistic
    Medicare/commercial PA rates.
    """
    key = drug_name.lower().strip()
    entry = _FORMULARY.get(key)

    if entry is None:
        return json.dumps({
            "drug": drug_name,
            "dose": dose,
            "indication": indication,
            "insurance": insurance,
            "tier": "unknown",
            "pa_required": True,
            "pa_approval_likelihood_pct": 60,
            "notes": (
                f"'{drug_name}' not found in formulary. PA likely required. "
                f"Check payer portal for {insurance} specific coverage."
            ),
            "alternatives": [],
        })

    tier, pa_required, likelihood, notes = entry
    alts = _ALTERNATIVES.get(key, [])

    return json.dumps({
        "drug": drug_name,
        "dose": dose,
        "indication": indication,
        "insurance": insurance,
        "tier": tier,
        "pa_required": pa_required,
        "pa_approval_likelihood_pct": likelihood,
        "notes": notes,
        "alternatives": alts if pa_required else [],
    })


def get_alternatives(drug_name: str, indication: str) -> str:
    """Returns therapeutic alternatives — most useful when PA is required or denied."""
    key = drug_name.lower().strip()
    alts = _ALTERNATIVES.get(key, [])
    return json.dumps({
        "drug": drug_name,
        "indication": indication,
        "alternatives": alts if alts else [],
        "note": (
            "No standard alternatives in formulary database."
            if not alts
            else "Consider switching to a lower-tier alternative to avoid PA delay."
        ),
    })


# ---------------------------------------------------------------------------
# Tool executor — called by the engine during the tool-use loop
# ---------------------------------------------------------------------------

_IMPLEMENTATIONS: dict = {
    "look_up_drug_info": lambda a: look_up_drug_info(**a),
    "check_prior_auth":  lambda a: check_prior_auth(**a),
    "get_alternatives":  lambda a: get_alternatives(**a),
}


def execute_tool(name: str, args: dict) -> str:
    fn = _IMPLEMENTATIONS.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return fn(args)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Tool definitions — Anthropic API format
# ---------------------------------------------------------------------------

TOOL_DEFS = [
    {
        "name": "look_up_drug_info",
        "description": (
            "Looks up a drug's FDA label: dosing guidelines, warnings, drug "
            "interactions, and adverse reactions. Call this for every drug before "
            "finalizing a prescription draft."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name": {
                    "type": "string",
                    "description": "Generic or brand drug name (e.g. 'furosemide', 'Lasix')",
                },
            },
            "required": ["drug_name"],
        },
    },
    {
        "name": "check_prior_auth",
        "description": (
            "Checks whether a drug requires prior authorization (PA) for a given "
            "indication and insurance plan, and returns the estimated PA approval "
            "likelihood. Always call this for Tier 2+ drugs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name":  {"type": "string", "description": "Generic or brand drug name"},
                "dose":       {"type": "string", "description": "Prescribed dose (e.g. '80mg')"},
                "indication": {"type": "string", "description": "Clinical indication"},
                "insurance":  {"type": "string", "description": "Patient's insurance plan"},
            },
            "required": ["drug_name", "dose", "indication", "insurance"],
        },
    },
    {
        "name": "get_alternatives",
        "description": (
            "Returns therapeutic alternatives to a drug — most useful when PA is "
            "required or when a Tier 3/4 drug could be substituted with a Tier 1/2 "
            "equivalent. Always call this when check_prior_auth returns pa_required=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "drug_name":  {"type": "string", "description": "Drug to find alternatives for"},
                "indication": {"type": "string", "description": "Clinical indication"},
            },
            "required": ["drug_name", "indication"],
        },
    },
]
