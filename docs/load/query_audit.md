# Query audit and index check (tasks 1.18 and 1.19), 16 Nov 2026

All numbers below come from runs on 16 Nov on one laptop, SQLite, Django dev server settings. Nothing here was measured on the host.

## 1.18 Queries per page

Seeded demo data (`seed_showcase`), signed in as `demo_cafe`, Django test client. Counts include the session, user, shop, rate-limit cache and badge queries.

| Page | Before | After |
|---|---|---|
| inbox | 10 | 7 |
| discover | 5 | 5 |
| shop detail | 5 | 5 |
| deal page | 12 | 12 |
| deal summary | 13 | 13 |
| playbook (with a question) | 15 | 15 |
| redeem | 5 | 5 |
| stats | 7 | 7 |

"Before" was taken after the shared rate limit (task 1.1) went in, so it already includes the database cache queries. The inbox badge query for the new shell (2.2) was added after this table was made.

Growth tests (`deals/tests/test_query_counts.py`) compare a small and a large data set. Only the inbox grew: 10 queries with 2 deals and 30 with 10, about 2.5 queries per deal. Cause: `current_version` ran a query per deal and `sync_status` ran two count queries per running deal. Fix: prefetch versions in the inbox, one grouped count query in `sync_all`. After the fix the count is the same at 2 and at 10 deals. Discover, deal page, summary and stats did not grow.

## 1.19 Indexes: no migration added

Every foreign key already has an index (Django adds them), and `Voucher.code`, the one-redemption-per-voucher link and `(deal, version number)` are unique. Not indexed: `Deal.status`, `Deal.updated_at`, `Redemption.confirmed_at`.

Test: a throwaway copy of the database with 208 shops, 5,004 deals, 40,018 vouchers and 40,018 redemptions (random data, not real use). Median of 15 runs, SQLite `EXPLAIN QUERY PLAN`.

| Query | Median, no new index | Median, with candidate indexes |
|---|---|---|
| Inbox deals for one shop (uses the existing proposer and recipient indexes) | 1.24 ms | 1.23 ms |
| Recent redemptions at a shop | 0.62 ms | 0.63 ms |
| Redemptions at a shop for one deal (cap count) | 0.19 ms | 0.16 ms |
| Stats: deals in a category | 2.15 ms | 2.14 ms |
| Stats: redemptions in a category | 6.18 ms | 1.59 ms (see below) |
| `update_deal_statuses` (all open deals, a full scan) | 43.11 ms | 42.84 ms |

Candidates tried on the copy only: indexes on `Deal.status`, `Deal.updated_at`, `Redemption.confirmed_at`, then `ANALYZE`.

- No page query is slow, and the candidate indexes did not change any of them.
- The only improvement, stats redemptions, came with a changed plan (it started at the shop table). We ran `ANALYZE` in the same step, so we cannot say the new indexes caused it. Not isolated.
- `update_deal_statuses` is the slowest query and scans all open deals. It is an optional command, not a page.
- Conclusion: the plan expected indexes on `Deal.status` and `Redemption.confirmed_at`; the measurements do not support adding them. Revisit if real data gets large.

## Load test (task 1.24)

`scripts/load_test.py`, 20 concurrent users (10 as `demo_cafe`, 10 as `demo_books`), 5 rounds of 4 pages. Dev server with `AI_DRAFT_LIMIT_PER_HOUR=100000 AI_API_KEY=` so the playbook used the rule-based fallback and the throttle did not interfere. Raw results are in this folder.

Median ms, run 1 / run 2:

| Page | Before | After |
|---|---|---|
| inbox | 102.1 / 103.1 | 85.5 / 87.0 |
| discover | 82.2 / 82.0 | 77.9 / 87.1 |
| summary | 188.1 / 184.4 | 165.9 / 165.0 |
| playbook | 74.3 / 74.6 | 97.0 / 91.3 |

- The p95 values moved a lot between runs of the same code (inbox 125 and 342 ms before), so only the medians are compared.
- Inbox: fewer queries explains it. Playbook: the shared rate limit now writes its counter to the database cache; likely cause, not isolated. Summary: we changed nothing aimed at it, so its drop is unexplained and may be noise.
- "After" was taken before the app shell (2.2) landed. The shell adds one query for the inbox badge on every page, so re-run the load test once the shell is done.
- The allauth login rate limit (about 30 logins a minute per IP) blocks a second run started within a minute; wait about 65 seconds between runs.

## After the app shell (task 2.2), 16 Nov 2026

Same machine, same server command (dev server, `--noreload`, AI on the rule-based fallback, throttle raised), 20 users x 5 rounds, two runs (`after_shell_run1.json`, `after_shell_run2.json`). Median ms, run 1 / run 2, against the earlier "after" runs:

| Page | After the query fixes | After the shell |
|---|---|---|
| inbox | 85.5 / 87 | 91.3 / 94.3 |
| discover | 78 / 87 | 86.2 / 85.3 |
| summary | 166 / 165 | 176.5 / 181.4 |
| playbook | 97 / 91 | 96.0 / 91.3 |

No request errors in either run. The shell adds the inbox-badge query to every page, and the pages now send three CSS files, so a few milliseconds more is expected. The rise is about 5 to 16 ms on inbox, discover and summary and none on playbook. Two runs on a dev server are noisy, so treat these as "slightly slower, not a regression" and not as exact. p95 was not compared.

## After the expired-deal badge change (D-A), 16 Nov 2026

The inbox badge now skips proposals past their response deadline (one extra `WHERE` condition, same single count query). Same machine and server command (restarted first), 20 users x 5 rounds, two runs (`after_badge_run1.json`, `after_badge_run2.json`). Median ms, run 1 / run 2:

| Page | After the shell | After the badge change |
|---|---|---|
| inbox | 91.3 / 94.3 | 102.6 / 99.6 |
| discover | 86.2 / 85.3 | 94.0 / 96.5 |
| summary | 176.5 / 181.4 | 173.2 / 197.4 |
| playbook | 96.0 / 91.3 | 101.9 / 100.7 |

No request errors. Pages are about 5 to 10 ms slower on three of four, but the change added no query (the count was already there), the summary page does not use the badge differently, and the run-to-run spread on the summary alone is 24 ms. The cause was not isolated, so read this as "same within dev-server noise", not as proof of no cost. Other things running on the laptop were not controlled. p95 was not compared.
