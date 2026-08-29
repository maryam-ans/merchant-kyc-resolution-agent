# Merchant KYC Name-Mismatch Recovery Agent (Buildathon starter)

An agent that processes a batch of merchant onboarding/re-KYC attempts,
catches the #1 real-world rejection cause -- business name mismatches
across PAN, GST, and bank account records -- explains the exact fix, and
handles the rest of the failure types as a secondary path.

**Why this problem:** RBI's Payment Aggregator KYC directions require
existing merchants to complete full re-KYC by **15 September 2026**. Name
mismatches across a business's PAN, GST registration, and bank account are
one of the most common, avoidable rejection reasons -- and they're messy
enough (legal suffix differences, abbreviations, typos) that a naive
exact-match check gets it wrong constantly.

This is a **skeleton, not the finished project** -- built so it runs today
and you can extend it with real understanding of every line.

## What's here

- `generate_data.py` -- creates `merchants.csv`, 80 synthetic onboarding
  records with realistic clean names, subtle mismatches (should NOT be
  flagged), and real mismatches (should be flagged)
- `agent.py` -- the core loop: name-match check (flagship) → fallback
  category check → decide → act → log
- `audit_log.csv` -- created after running `agent.py`
- `requirements.txt`

## How the flagship logic works

1. Strip legal suffixes (Pvt Ltd / Private Limited / LLP / etc.) and
   normalize each name
2. Fuzzy-compare PAN name vs GST name vs bank account name pairwise
   (Python's built-in `difflib`, no extra dependency)
3. Below a similarity threshold → real mismatch → Gemini writes a specific,
   plain-language fix message naming which document to correct
4. Above the threshold → treated as the same business, falls through to
   checking secondary issues (document quality, risk category, etc.) with
   simple keyword rules

## Run it

```bash
pip install -r requirements.txt --break-system-packages

# Get a free key (no credit card needed) at https://aistudio.google.com
export GEMINI_API_KEY=your_key_here

python generate_data.py   # creates merchants.csv
python agent.py           # creates audit_log.csv, prints a summary
```

## Important honesty notes for your pitch

- The "estimated monthly GMV unblocked" number is a **synthetic estimate**,
  not confirmed recovered revenue -- say this explicitly in your video,
  don't let the number stand alone without context
- The name-matching logic is a **simplified heuristic**, not an official
  RBI-compliant matching algorithm -- don't claim regulatory accuracy you
  haven't verified
- The 15 September 2026 deadline is real (RBI Payment Aggregator
  Directions) -- verify it yourself from a primary source before quoting
  it in front of judges

## What to build next (your job, not done yet)

- [ ] Streamlit dashboard reading `audit_log.csv`: mismatches caught,
      categories breakdown, estimated GMV unblocked, before/after
      onboarding completion rate
- [ ] A real "break it on purpose" test (malformed row, empty name field)
      -- confirm the agent logs it and keeps going
- [ ] Architecture diagram: data in → name-match check → fallback category
      check → decide → act → log → dashboard
- [ ] Tighten your one-sentence pitch in your own words, not copied from
      research
