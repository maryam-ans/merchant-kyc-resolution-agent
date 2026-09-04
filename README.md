# Merchant KYC Name-Mismatch Resolution Agent

An agent that processes a batch of merchant onboarding/re-KYC attempts,
catches the #1 real-world rejection cause — business name mismatches
across PAN, GST, and bank account records — tells the merchant exactly
what to fix, verifies whether the fix worked, and handles the rest of
the failure types as a secondary path.

## The problem

Payment aggregators in India are required, under RBI's Payment Aggregator
KYC directions, to complete full re-KYC verification for all existing
merchants by **15 September 2026**. This is a real, current deadline
creating real pressure across the industry right now.

One of the most common — and most avoidable — reasons a merchant's KYC
gets rejected is a name mismatch across their PAN, GST registration, and
bank account records. This isn't fraud. It's a paperwork-timing problem:
a business is usually registered for PAN when it's founded, registered
separately for GST later (often by an accountant), and opens a bank
account through a bank clerk who types the name from memory or a slightly
different source document. Three people, three moments, one business —
and the name drifts slightly each time ("ABC Pvt Ltd" vs "ABC Private
Limited" vs "ABC Enterprises"). Razorpay's own blog cites PAN/bank name
mismatches as the cause of roughly 40% of onboarding delays — the single
biggest rejection reason.

## How I arrived at this idea

I started broad — an early version of this project was a generic
"payment failure recovery" agent. I narrowed it in two deliberate steps:

1. **From generic payment recovery → merchant onboarding/KYC recovery**,
   anchored to the real, current RBI re-KYC deadline instead of a made-up
   problem.
2. **From "handle five KYC failure types equally" → one flagship problem,
   done deeply.** Spreading effort across five shallow categories risked
   looking like a generic AI-generated idea. Going deep on name-mismatch
   detection specifically — with the other categories handled as a
   simpler secondary path — is what makes this project defensible and
   distinctive rather than a template.

I also deliberately chose **Open Track over AI Revenue Recovery**.
Revenue Recovery, as Razorpay defines it, is about money that was already
flowing through a transaction and got interrupted (a failed payment, an
abandoned checkout, a failed subscription renewal). A merchant stuck in
KYC never had a transaction to interrupt — there's no revenue-in-motion,
just a blocked registration. There's nothing to recover, only something
to unblock. Open Track carries the same bar for execution, reliability,
and depth — so the honest label cost nothing.

## What's here

- `generate_data.py` — creates `merchants.csv`, 80 synthetic onboarding
  records with realistic clean names, subtle mismatches (should NOT be
  flagged), and real mismatches (should be flagged)
- `agent.py` — the core loop: name-match check (flagship) → fallback
  category check → decide → act → verify → log
- `dashboard.py` — Streamlit dashboard reading `audit_log.csv`
- `audit_log.csv` — created after running `agent.py`
- `architecture.png` — pipeline diagram
- `requirements.txt`

## How it works

- **Diagnose:** normalize each name (strip legal suffixes like "Pvt Ltd"
  / "LLP", lowercase, remove punctuation), then fuzzy-compare PAN vs GST
  vs bank names pairwise using Python's built-in `difflib.SequenceMatcher`.
  A similarity threshold (0.75) separates harmless clerical variation
  from a genuine mismatch. Names that pass fall through to a simpler
  keyword check for secondary issues (document quality, high-risk
  category, missing international enablement, incomplete profile).
- **Decide:** a plain lookup table maps each category to exactly one
  action, with hard stopping rules checked first — a high-risk category
  is never auto-approved, an already-approved merchant is never
  reprocessed, and a merchant is escalated after repeated retries. This
  is deliberately deterministic, not AI-driven, so the system's full
  range of possible actions can be read and audited in a dozen lines.
- **Act:** for name mismatches only, the system calls Google's Gemini API
  to generate a specific, plain-language fix message naming exactly which
  document to correct. Every other action is a deterministic simulated
  step. AI is used only where a rule genuinely can't do the job.
- **Verify:** simulates whether the merchant acted on the fix message
  (not every notification gets a response), and if they did, re-runs the
  same name-matching check against their corrected names. Verification
  only runs after confirming a real fix message was actually generated,
  not on failed API calls.
- **Log:** every decision is written to a full audit trail, explainable
  line by line.
- **Dashboard:** total merchants, mismatches caught, resolved-after-verify
  count, estimated GMV unblocked, a category breakdown chart, and the
  full audit table.

**Tech stack:** Python, `difflib`, Google Gemini API via `google-genai`,
Streamlit, CSV, Git/GitHub.

## Run it

```bash
pip install -r requirements.txt --break-system-packages

# Get a free key (no credit card needed) at https://aistudio.google.com
export GEMINI_API_KEY=your_key_here

python generate_data.py      # creates merchants.csv
python agent.py              # creates audit_log.csv, prints a summary
streamlit run dashboard.py   # opens the dashboard in your browser
```

## Real failures encountered while building this (and how they were handled)

Four distinct real failures came up while building this — not staged for
the submission, found while actually running the code against a live API.

1. **Model deprecation (404):** partway through development, Google
   deprecated the Gemini model I was originally using, for new API
   accounts. The error message itself named the correct replacement
   model, now used in `agent.py`.
2. **Per-minute rate limiting (429):** the free tier caps requests at
   5/minute for this model. Fixed by adding a fixed delay between AI
   calls in `execute_action()`.
3. **Daily rate limiting (429):** the same free tier also caps requests
   at 20/day — hit while testing, a different quota reason than #2, not
   something I'd anticipated.
4. **Intermittent server overload (503):** an unrelated "model
   experiencing high demand" error, seen occasionally.

In every case, a `try`/`except` around the API call caught the failure
and logged it clearly in the audit trail instead of crashing the batch —
the rest of the merchants kept processing normally.

**A bug I found and fixed myself, not from an external error:** the
verify step initially ran regardless of whether fix-message generation
had actually succeeded, which meant a merchant could get marked
"resolved" even when no real fix message was ever sent. I caught this by
comparing two columns in my own audit log against each other, not from a
crash. Fixed by checking that `action_detail` actually starts with
`"FIX MESSAGE:"` before running verification — otherwise it's logged as
`fix_message_generation_failed`, an honest label instead of a
misleading one.

## How this helps, practically

- **For the merchant:** instead of a generic "KYC rejected" notice, they
  get a specific, actionable instruction — reducing back-and-forth and
  resubmission delay.
- **For the payment aggregator:** the most common, most avoidable
  rejection reason gets triaged automatically, reducing manual review
  load ahead of a hard regulatory deadline, while still guaranteeing a
  human reviews anything genuinely high-risk.
- **For compliance/audit purposes:** every decision is logged with its
  reasoning, giving a reviewable trail rather than a black box.

## Known limitations (disclosed honestly)

Synthetic data was a deliberate choice, not a shortcut: real merchant
PAN/GST/bank records are sensitive financial data that can't be sourced
or scraped ethically for a project like this. The dataset is built to be
realistic and hard, not clean — it includes deliberate edge cases:
legal-suffix variations that should NOT be flagged, real typos and
abbreviations that should, and already-approved merchants to test the
stopping rules.

- Name-matching is a simplified fuzzy-match heuristic, not an official
  RBI-compliant algorithm
- Merchant responses in the VERIFY step are simulated, not real
- The "estimated GMV unblocked" number is a synthetic estimate, not
  confirmed recovered revenue
