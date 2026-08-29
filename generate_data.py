"""
generate_data.py
-----------------
Creates a synthetic batch of merchant onboarding/re-KYC attempts and saves
them to merchants.csv.

Flagship problem: name mismatches across PAN, GST registration, and bank
account records. This is a real, common rejection reason under RBI's
Payment Aggregator KYC requirements (existing merchants must be fully
re-KYC'd by 15 September 2026). Businesses often register their legal name
slightly differently across these three documents (e.g. "ABC Pvt Ltd" vs
"ABC Private Limited" vs "ABC Enterprises"), which is exactly the kind of
messy, human problem an LLM is good at catching and explaining -- a strict
exact-string rule would miss most real-world variants.

We deliberately generate:
  - Clear name matches (should pass straight through)
  - Subtle name mismatches (legal suffix differences, abbreviations, typos)
  - A smaller set of OTHER failure types (document quality, high-risk
    category, missing international enablement, incomplete profile) so
    your agent still has to handle more than one thing -- just not as the
    main event.

Run it with:
    python generate_data.py
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

BUSINESS_ROOTS = ["Sunrise Traders", "Bluepeak Retail", "Nimbus Foods",
                   "Greenline Logistics", "Vertex Apparel", "Coral Handicrafts",
                   "Ashoka Electronics", "Meridian Books", "Orbit Fitness",
                   "Silverline Textiles", "Amber Organics", "Kite Studio"]

LEGAL_SUFFIXES = ["Pvt Ltd", "Private Limited", "LLP", "Enterprises", "& Co"]

BUSINESS_TYPES = ["e-commerce", "retail", "food_delivery", "logistics",
                   "education", "wellness", "electronics"]

# Free-text reasons for non-name-mismatch cases (keep these simpler than the
# name-mismatch logic -- they're the supporting cast, not the star)
OTHER_REASONS = {
    "document_quality_issue": [
        "uploaded GST certificate is blurry, unreadable",
        "PAN card photo cropped, number not visible",
    ],
    "category_risk_flag": [
        "business category flagged high-risk, needs manual review",
        "crypto-adjacent business model, requires compliance sign-off",
    ],
    "missing_international_enablement": [
        "merchant wants to accept international cards, module not enabled",
    ],
    "incomplete_profile": [
        "bank account not linked yet",
        "business address field left blank",
    ],
}


def make_name_variant(base_name, mismatch_level):
    """
    mismatch_level:
      'subtle' -> legal suffix differs in a way that could confuse a naive
                  exact-match check but a human (or LLM) would recognize
                  as the same business
      'real'   -> a genuinely different-looking name (typo, abbreviation,
                  truncation) that should be flagged
    """
    if mismatch_level == "subtle":
        return base_name.replace("Pvt Ltd", random.choice(LEGAL_SUFFIXES))
    # 'real' mismatch: truncate, abbreviate, or typo the name
    words = base_name.split()
    choice = random.choice(["truncate", "abbreviate", "typo"])
    if choice == "truncate":
        return " ".join(words[:1])
    if choice == "abbreviate":
        return "".join(w[0] for w in words if w.isalpha()).upper() + " " + random.choice(LEGAL_SUFFIXES)
    # typo: swap two letters in the first word
    w = list(words[0])
    if len(w) > 3:
        i = random.randint(0, len(w) - 2)
        w[i], w[i + 1] = w[i + 1], w[i]
    return "".join(w) + " " + " ".join(words[1:])


def random_timestamp(days_back=14):
    delta = timedelta(days=random.randint(0, days_back),
                       hours=random.randint(0, 23))
    return (datetime.now() - delta).strftime("%Y-%m-%d %H:%M:%S")


def make_merchant(idx):
    base = f"{random.choice(BUSINESS_ROOTS)} {random.choice(LEGAL_SUFFIXES)}"
    pan_name = base

    # 50% clean names, 30% subtle mismatch (the interesting case for your
    # LLM step), 20% obviously different (the case a simple rule CAN catch)
    r = random.random()
    if r < 0.5:
        gst_name = base
        bank_name = base
        mismatch_type = "none"
    elif r < 0.8:
        gst_name = make_name_variant(base, "subtle")
        bank_name = base if random.random() < 0.5 else make_name_variant(base, "subtle")
        mismatch_type = "subtle"
    else:
        gst_name = make_name_variant(base, "real")
        bank_name = base
        mismatch_type = "real"

    # Only some merchants also have an "other" issue -- most either pass
    # cleanly on names or fail specifically because of the name mismatch
    other_category = None
    other_note = ""
    if mismatch_type == "none" and random.random() < 0.35:
        other_category = random.choice(list(OTHER_REASONS.keys()))
        other_note = random.choice(OTHER_REASONS[other_category])

    status = "pending"
    if mismatch_type == "none" and other_category is None and random.random() < 0.1:
        status = "approved"  # a few already-approved merchants on purpose,
        # to test your "don't act on already-approved" stopping rule

    return {
        "merchant_id": f"mer_{idx:04d}",
        "business_type": random.choice(BUSINESS_TYPES),
        "pan_name": pan_name,
        "gst_name": gst_name,
        "bank_account_name": bank_name,
        "other_note": other_note,  # empty string if no secondary issue
        "estimated_monthly_gmv": round(random.uniform(50000, 2000000), 2),
        "international_enabled": random.random() < 0.2,
        "retry_count": random.choice([0, 0, 0, 1, 1, 2]),
        "status": status,
        "timestamp": random_timestamp(),
    }


def main(n=80, out_path="merchants.csv"):
    rows = [make_merchant(i) for i in range(1, n + 1)]
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {n} synthetic merchant onboarding records to {out_path}")


if __name__ == "__main__":
    main()
