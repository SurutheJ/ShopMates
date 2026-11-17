# Evaluation

Reproduce the retrieval and guardrail numbers with `python manage.py evaluate_ai`. Latencies for the offline rows were measured on a laptop with the Django test client and local SQLite, so they leave out network time and say nothing about a hosted site. The live rows were timed against Gemini from the same laptop.

Quality scores (1 to 10) are our own judgment of the output. The live model has only been tried in small runs, so those rows are early evidence.

## Metrics

| Feature | Metrics |
|---|---|
| Playbook retrieval | Hit@1 and Hit@3 on labelled questions, search time |
| AI draft and coach checks | Share of bad model replies rejected, fallback always valid |
| Match score and radar | Ranking agrees with the order we expected |
| Fairness calculator | Matches a hand calculation to the cent |
| Live model | Latency, error rate |
| Whole workflow | Task completion (automated flow tests), error rate |

## Tests

Data is the `seed_showcase` neighborhood.

| # | Input | Expected | Actual | Quality | Latency |
|---|---|---|---|---|---|
| 1 | "Draft with AI" for Green Street Cafe ($9 ticket) to Pageturner Books ($24), no key | Valid terms, a reason AI was not used, playbook sources | Before improvement 2: 10%, cap 50, source "fallback", reason "AI is not configured." After: cap 20 | 5 before, 7 after | 0.1 ms |
| 2 | Simulated model reply with a 90% discount | Rejected, fallback terms, discount at most 50% | Fallback, reason "discount_percent: Discount can be at most 50%." | 9 | under 1 ms |
| 3 | "Explain this deal" on the cafe/books deal (14 vs 4 customers), no key | Names who sent more, cost for each side, flags lopsided, suggests a renewal | Names both counts, estimated discount cost $3.60 vs $33.60, suggests a higher cap and a perk from the bookstore | 7 | 5.5 ms |
| 4 | Playbook: "What deal should a bakery offer a flower shop?" | Bakery and flowers passage first | `bakery-flowers`, relevance 0.51 | 9 | 4.5 ms (page) |
| 5 | Playbook: "how many redemptions should I allow" | Caps and dates passage first | Before improvement 1: `measuring-fairness` first. After: `caps-and-dates` first | 4 before, 9 after | 0.02 ms |
| 6 | Discover from the cafe: bookstore 0.1 mi, yoga 0.4 mi, other cafe 0.1 mi, bookstore 4 mi | That order | Scores 86, 78, 62, 53 | 8 | 43 ms (page) |
| 7 | Fairness: cafe ($6, 65% margin) and bookstore ($24, 35%), both 10%, cap 50, 2 months | $132.00 and $240.00 by hand, lopsided | Same figures, 45% apart, suggests 17% for the bookstore | 9 | under 1 ms |
| 8 | Live "Draft with AI", 15 calls in a row | Valid draft each time | 8 valid (0.9 to 5.3 s, median 1.1 s), 7 HTTP 429 quota errors that fell back to the built-in draft | 6 | 1.1 s median |

Other results: retrieval on 20 labelled questions (14 development, 6 held-out) is under improvement 1. Guardrail cases: 9 of 9 handled correctly. Of the 8 live drafts that succeeded, all passed the number check. Full suite: 479 tests passing.

## Failure analysis

**1. Retrieval misses on words the playbook does not use (not fixed).**
- What failed: "which kinds of shops work well together" returned `purchase-triggered` instead of `reciprocal-discount`; "how long should a promotion run" returned `bundled-experience` instead of `caps-and-dates`. 2 of 6 held-out questions miss at rank 1.
- Why: TF-IDF only matches words, and these questions share few with the passages.
- Impact: an owner sees a loosely related passage. The answer is still built from what was retrieved, so the risk is irrelevance, not invention.
- Improvement: embeddings, or more passages and synonyms once we have a bigger labelled set.

**2. The fallback draft ignored the spend gap (fixed, see improvement 2).**
- What failed: for cafe ($9) and bookstore ($24) the fallback proposed 10% with cap 50 for each shop.
- Why: the fallback was a fixed template.
- Impact: the bookstore's worst case was 50 x 10% x $24 = $120 in discounts against $45 for the cafe.

**3. The coach number check is blunt (not fixed).**
- What failed: "Renew for 30 days with a cap of 20" is rejected because 30 and 20 were not among the numbers the app computed. A reply with the right numbers and the wrong conclusion would pass.
- Why: the check compares digits and cannot read meaning.
- Impact: some good replies fall back to the plainer template, and a wrong conclusion could be shown labelled as AI.
- Improvement: pass the renewal numbers to the model as facts it may cite, and check which shop goes with which number.

**4. Live quota and wording (open).**
- What failed: 7 of 15 quick draft calls got HTTP 429, and one draft's message said "20% off drinks and 10% off books" while the checked discount was 15.
- Why: the free tier limits request rate, and Python checks fields and numbers, not sentences.
- Impact: users see the built-in draft with the line "The AI is busy right now." A contradictory sentence could reach the form, where the owner can edit it.
- Improvement: retry once, and check that the message numbers match the fields.

## Improvements, before and after

**1. Synonym expansion in retrieval.** Before: development set Hit@1 10/14, Hit@3 13/14. Change: map everyday words to the playbook's terms before indexing and searching (`gym` to `fitness`, `coffee` to `cafe`, `allow` and `limit` to `cap`, and so on). After: development set 14/14 and 14/14.
Did it work? Only partly. We built the list from the four development failures, so 14/14 is optimistic. The held-out set did not change (Hit@1 4/6 before and after). It fixes the gaps we saw and does not generalize to new ones.

**2. Spend-aware fallback cap.** Before: cafe/bookstore draft with cap 50, bookstore exposure $120. Change: when the two shops' typical spend differs by more than 40%, scale the cap by the spend ratio (never below 10). After: cap 20, exposure $48 (20 x 10% x $24). Trade-off: the cafe can also receive at most 20 redemptions. Covered by `FallbackCapTests`.

**3. Number check on draft text.** Before: the live model once wrote different percentages in its message than in its fields. Change: the offer text and message may only contain numbers that are the checked discount, cap, duration or a shop's typical spend. After: 8 of 8 live drafts passed. That is too few to measure a rejection rate; the blocked case is covered by tests.

## Load and queries

Page query counts, index checks and a 20-user load test are in [load/query_audit.md](load/query_audit.md). Inbox queries dropped from 10 to 7 after fixing a per-deal query. Median page times on the dev server were roughly 75 to 200 ms.
