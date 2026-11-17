# Roadmap to December 8

## Task table

| Task | Current status | Responsible Member | Expected completion |
|---|---|---|---|
| Django core features | Negotiation, QR redemption, staff page, summary, exports, roles and restyle done. Terms and privacy pages, notifications still to do | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Dec 3 |
| Database and APIs | 10 models, 4 migrations, public stats API, two private APIs, CSV and JSON export done. Address lookup and a per-user daily limit on Radar still to do | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Nov 30 |
| AI integration | Match score, Radar, fairness calculator, draft, coach and playbook done. Negotiation copilot and terms checker not started. Real OpenStreetMap request not yet made | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Dec 3 |
| Evaluation and testing | 479 tests, `evaluate_ai` report, 8 recorded tests, 4 failures and limits analysed, 3 improvements measured. Re-run with the live model and add Radar timings | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Dec 5 |
| Deployment | Not deployed. Local run and prod settings work. PythonAnywhere upload, outbound allowlist check and Google redirect URI to do | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Nov 24 |
| Documentation | README, AI doc, scope, evaluation, production notes written. Update after deployment and add screenshots | Suruthe Jayachandran and Sahithi Madabhushi (equal) | Dec 7 |

## Order of work

1. Deploy to PythonAnywhere and fix what breaks (allowlist, static files, Google sign-in, one live AI call).
2. Finish Radar (address lookup, daily limit, timing) and the remaining AI features.
3. Show the app to three to five shops near campus and record what they say.
4. Final evaluation numbers, docs check, 3-minute demo video, final push on Dec 8.

## Cut rules

If time runs short, we drop in this order: negotiation copilot, terms checker, notifications. Deployment, evaluation and the docs are not cut.

## Done so far

- Shop accounts, Google sign-in (tested locally), owner and staff roles, admin approval
- Discover, Radar, propose wizard, counter-offers, deal pages with history and chat
- QR vouchers, staff redemption with database-enforced single use, QR card downloads
- Deal summary, charts, renewal suggestion, exports, APIs
- Rate limits, health check, backup command, security headers, Chicago time zone everywhere
- GitHub Actions workflow that runs `check` and `test`
