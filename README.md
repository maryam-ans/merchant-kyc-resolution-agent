Merchant KYC Name-Mismatch Resolution Agent

An agent that processes a batch of merchant onboarding/re-KYC attempts, catches the #1 real-world rejection cause — business name mismatches across PAN, GST, and bank account records — tells the merchant exactly what to fix, verifies whether the fix worked, and handles the rest of the failure types as a secondary path.

Why this problem: RBI's Payment Aggregator KYC directions require existing merchants to complete full re-KYC by 15 September 2026. Name mismatches across a business's PAN, GST registration, and bank account are one of the most common, avoidable rejection reasons — Razorpay's own blog cites PAN/bank name mismatches as the cause of roughly 40% of onboarding delays. These mismatches are messy enough (legal suffix differences, abbreviations, typos) that a naive exact-match check gets it wrong constantly.

Track: Open Track. Razorpay's Revenue Recovery track is specifically about money already in motion that gets interrupted mid-transaction (failed payments, abandoned checkouts, failed subscriptions). A merchant stuck in KYC never had a transaction to interrupt — there's no revenue-in-motion, just a blocked registration. There's nothing to recover, only something to unblock, so this belongs in Open Track, which carries the same bar for execution, reliability, and depth.

What's here
generate_data.py — creates merchants.csv, 80 synthetic onboarding records with realistic clean names, subtle mismatches (should NOT be flagged), and real mismatches (should be flagged)
agent.py — the core loop: name-match check (flagship) → fallback category check → decide → act → verify → log
dashboard.py — Streamlit dashboard reading audit_log.csv: total merchants, name mismatches caught, resolved-after-verify count, and estimated GMV unblocked, plus a category breakdown chart and the full audit table
audit_log.csv — created after running agent.py
architecture.png — pipeline diagram (data in → diagnose → decide → act → verify → log → dashboard)
requirements.txt
How the flagship logic works
Strip legal suffixes (Pvt Ltd / Private Limited / LLP / etc.) and normalize each name
Fuzzy-compare PAN name vs GST name vs bank account name pairwise (Python's built-in difflib, no extra dependency)
Below a similarity threshold → real mismatch → Gemini writes a specific, plain-language fix message naming which document to correct
Above the threshold → treated as the same business, falls through to checking secondary issues (document quality, risk category, etc.) with simple keyword rules
For flagged mismatches, a VERIFY step simulates whether the merchant acted on the fix message and re-checks the names — closing the loop from diagnosis to confirmed resolution. Verification only runs after confirming a real fix message was actually generated, not on failed API calls.
Run it
bash
pip install -r requirements.txt --break-system-packages

Get a free key (no credit card needed) at https://aistudio.google.com
export GEMINI_API_KEY=your_key_here

python generate_data.py      # creates merchants.csv
python agent.py              # creates audit_log.csv, prints a summary
streamlit run dashboard.py   # opens the dashboard in your browser
Real failures encountered while building this (and how they were handled)
Model deprecation (404): partway through development, Google deprecated the Gemini model originally used, for new API accounts. The error message itself named the correct replacement model, now used in agent.py.
Per-minute rate limiting (429): the Gemini free tier caps requests at 5/minute for this model. Fixed by adding a fixed delay between AI calls in execute_action().
Daily rate limiting (429): the same free tier also caps requests at 20/day for this model — hit while testing, a different quota reason than #2.
Intermittent server overload (503): an unrelated "model experiencing high demand" error, seen occasionally.

In every case, a try/except around the API call meant the failure was caught and logged clearly in the audit trail instead of crashing the batch — the rest of the merchants kept processing normally.

A logic bug I found and fixed myself: the verify step initially ran regardless of whether fix-message generation had actually succeeded, incorrectly marking some merchants "resolved" or "still_mismatched" even when no real fix message was ever sent. Fixed by checking that action_detail actually starts with "FIX MESSAGE:" before running verification — otherwise it's logged as fix_message_generation_failed, an honest label instead of a misleading one.

Known limitations (disclosed honestly)
Data is synthetic, not connected to a real onboarding system or the actual Razorpay API
Name-matching is a simplified fuzzy-match heuristic, not an official RBI-compliant algorithm
Merchant responses in the VERIFY step are simulated, not real
The "estimated GMV unblocked" number is a synthetic estimate, not confirmed recovered revenue
