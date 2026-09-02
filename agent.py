"""
agent.py
--------
For each merchant onboarding attempt in merchants.csv:

  1. DIAGNOSE   -> flagship check: does the business name on PAN, GST, and
                   bank account records actually match? (fuzzy, not exact --
                   see normalize_name() and name_similarity() below). If
                   names look fine, fall back to checking other_note for
                   secondary issues (document quality, risk category, etc).
  2. DECIDE     -> pick ONE bounded action per merchant, with explicit
                   stopping rules (never auto-approve high-risk categories,
                   never touch already-approved merchants).
  3. ACT        -> for name mismatches, ask Claude to write the EXACT fix
                   the merchant needs to make (which field, what to change
                   it to). This is the differentiated, "went deep on one
                   thing" part of the project.
  4. LOG        -> every decision written to audit_log.csv, explainable
                   line by line.

Run it with:
    python agent.py
(after generate_data.py, and with GEMINI_API_KEY set for the full
name-mismatch explanations -- it still runs and logs sensibly without one)
"""

import csv
import os
import re
import time
import random
from datetime import datetime
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# STEP 1a: NAME MATCHING (the flagship logic -- this is the part worth
# spending your real effort polishing, since it's what makes this project
# yours rather than a generic template)
# ---------------------------------------------------------------------------

# Common legal suffixes that should NOT count as a "real" mismatch on their
# own -- "ABC Pvt Ltd" and "ABC Private Limited" are the same business.
LEGAL_SUFFIX_PATTERN = re.compile(
    r"\b(pvt\.?|private|ltd\.?|limited|llp|enterprises|& co\.?|and co\.?)\b",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Strip legal suffixes, lowercase, collapse whitespace, so we're
    comparing the actual business name, not the corporate wrapper around it."""
    stripped = LEGAL_SUFFIX_PATTERN.sub("", name)
    stripped = re.sub(r"[^a-z0-9 ]", "", stripped.lower())
    return re.sub(r"\s+", " ", stripped).strip()


def name_similarity(a: str, b: str) -> float:
    """0.0 (totally different) to 1.0 (identical) after normalization."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


NAME_MATCH_THRESHOLD = 0.75  # below this, we flag it as a real mismatch


def check_name_mismatch(pan_name, gst_name, bank_name):
    """
    Returns (is_mismatch: bool, details: str) comparing all three names
    pairwise. details lists exactly which pair(s) diverge and by how much
    -- this feeds directly into the LLM prompt so the fix message is
    specific, not generic.
    """
    pairs = [
        ("PAN", "GST", pan_name, gst_name),
        ("PAN", "Bank", pan_name, bank_name),
        ("GST", "Bank", gst_name, bank_name),
    ]
    mismatches = []
    for label_a, label_b, name_a, name_b in pairs:
        sim = name_similarity(name_a, name_b)
        if sim < NAME_MATCH_THRESHOLD:
            mismatches.append(f"{label_a} ('{name_a}') vs {label_b} ('{name_b}') "
                               f"-- similarity {sim:.2f}")
    if mismatches:
        return True, "; ".join(mismatches)
    return False, ""

def simulate_merchant_response(response_rate=0.75):
    return random.random() < response_rate

def verify_correction(merchant):
    if not simulate_merchant_response():
        return "no_response"
    # 85% of merchants who respond correct it exactly right;
    # 15% make a partial fix (e.g. only update one document, or make
    # a typo while retyping the name) -- realistic, not everyone gets
    # it perfectly right on the first try.
    if random.random() < 0.85:
        corrected_gst = merchant["pan_name"]
        corrected_bank = merchant["pan_name"]
    else:
        corrected_gst = merchant["pan_name"]
        corrected_bank = merchant["gst_name"]  # forgot to fix the bank record too

    is_mismatch, _ = check_name_mismatch(
        merchant["pan_name"], corrected_gst, corrected_bank
    )

    if is_mismatch:
        return "still_mismatched"
    else:
        return "resolved"

# ---------------------------------------------------------------------------
# STEP 1b: SECONDARY DIAGNOSIS (supporting cast -- kept simple on purpose)
# ---------------------------------------------------------------------------

OTHER_RULE_MAP = {
    "blurry": "document_quality_issue",
    "unreadable": "document_quality_issue",
    "cropped": "document_quality_issue",
    "high-risk": "category_risk_flag",
    "compliance sign-off": "category_risk_flag",
    "international cards": "missing_international_enablement",
    "not linked": "incomplete_profile",
    "left blank": "incomplete_profile",
}


def diagnose_other(note: str) -> str:
    """Simple keyword match against the free-text note. No LLM call needed
    here -- this is deliberately the 'easy' path so your budget (time and
    API calls) goes toward the name-mismatch logic instead."""
    if not note:
        return "clean_ok"
    note_lower = note.lower()
    for keyword, category in OTHER_RULE_MAP.items():
        if keyword in note_lower:
            return category
    return "incomplete_profile"  # safe default for anything unrecognized


# ---------------------------------------------------------------------------
# STEP 2: DECIDE (bounded, explainable)
# ---------------------------------------------------------------------------

MAX_RETRIES = 3

ACTION_MAP = {
    "name_mismatch": "send_name_fix_instructions",
    "document_quality_issue": "request_document_reupload",
    "category_risk_flag": "escalate_manual_review",
    "missing_international_enablement": "suggest_enable_international",
    "incomplete_profile": "request_missing_fields",
    "clean_ok": "auto_approve",
}


def decide_action(category: str, status: str, retry_count: int):
    if status == "approved":
        return "no_action", "already approved -- never re-process approved merchants"

    # Hard rule: high-risk category NEVER gets auto-approved, no matter what.
    if category == "category_risk_flag":
        return "escalate_manual_review", "high-risk category always requires a human"

    if retry_count >= MAX_RETRIES:
        return "escalate_manual_review", f"hit max retries ({MAX_RETRIES})"

    action = ACTION_MAP.get(category, "escalate_manual_review")
    return action, f"category={category}"


# ---------------------------------------------------------------------------
# STEP 3: ACT (simulated where it should be)
# ---------------------------------------------------------------------------

def execute_action(merchant, category, action, mismatch_details, client):
    if action == "send_name_fix_instructions":
        try:
            prompt = (
                "A merchant's business name doesn't match across their KYC "
                "documents. Details: " + mismatch_details + ". "
                "In 2 short sentences, tell them plainly which document(s) "
                "to correct and what name to standardize on (pick the PAN "
                "name as the source of truth, since that's the government "
                "ID). Keep it under 45 words, no legal jargon."
            )
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            result = f"FIX MESSAGE: {response.text.strip()}"
        except Exception as e:
            result = f"[fix message generation failed, logging only: {e}]"
        time.sleep(13)
        return result

    if action == "request_document_reupload":
        return "SIMULATED: sent document re-upload request"
    if action == "escalate_manual_review":
        return "SIMULATED: created manual review task for compliance team"
    if action == "suggest_enable_international":
        return "SIMULATED: flagged merchant as eligible for international module"
    if action == "request_missing_fields":
        return "SIMULATED: sent request for missing profile fields"
    if action == "auto_approve":
        return "SIMULATED: merchant auto-approved, onboarding complete"
    return "n/a"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main(in_path="merchants.csv", audit_path="audit_log.csv"):
    client = None
    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            print("WARNING: GEMINI_API_KEY not set. Name-mismatch fix "
                  "messages will be skipped (logged as no-key instead).")
    except ImportError:
        print("WARNING: 'google-genai' package not installed. Run "
              "'pip install google-genai --break-system-packages'.")

    with open(in_path) as f:
        merchants = list(csv.DictReader(f))

    audit_rows = []
    unblocked_gmv = 0.0
    unblocked_count = 0
    name_mismatch_caught = 0
    resolved_count = 0

    for m in merchants:
        is_mismatch, details = check_name_mismatch(
            m["pan_name"], m["gst_name"], m["bank_account_name"]
        )
        if is_mismatch:
            category = "name_mismatch"
            name_mismatch_caught += 1
        else:
            category = diagnose_other(m["other_note"])

        action, decision_reason = decide_action(
            category, m["status"], int(m["retry_count"])
        )

        if client and action != "no_action":
            action_detail = execute_action(m, category, action, details, client)
        else:
            action_detail = "SKIPPED (no API key)" if action != "no_action" else "n/a"
        
        verification_result = "n/a"
        if category == "name_mismatch" and action == "send_name_fix_instructions":
            if action_detail.startswith("FIX MESSAGE:"):
                verification_result = verify_correction(m)
            else:
                verification_result = "fix_message_generation_failed"
        if verification_result == "resolved":
            resolved_count += 1

        # Count GMV as "unblocked" only for merchants we actively moved
        # forward (not for no_action / already-approved). Labeled clearly
        # as an ESTIMATE, not confirmed recovered revenue -- be upfront
        # about this distinction in your pitch.
        if action not in ("no_action",):
            unblocked_gmv += float(m["estimated_monthly_gmv"])
            unblocked_count += 1

        audit_rows.append({
            "merchant_id": m["merchant_id"],
            "business_type": m["business_type"],
            "category": category,
            "name_mismatch_details": details,
            "action": action,
            "decision_reason": decision_reason,
            "action_detail": action_detail,
            "estimated_monthly_gmv": m["estimated_monthly_gmv"],
            "verification_result": verification_result,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    with open(audit_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=audit_rows[0].keys())
        writer.writeheader()
        writer.writerows(audit_rows)

    print(f"\nProcessed {len(merchants)} merchants.")
    print(f"Name mismatches caught: {name_mismatch_caught}")
    print(f"Merchants moved forward (any action): {unblocked_count}")
    print(f"Estimated monthly GMV unblocked (NOT confirmed revenue): "
          f"Rs {unblocked_gmv:,.2f}")
    print(f"Full audit trail written to {audit_path}")
    print(f"Of {name_mismatch_caught} name mismatches, {resolved_count} resolved after simulated correction.")


if __name__ == "__main__":
    main()
