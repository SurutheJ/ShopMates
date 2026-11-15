# Instructions for AI coding sessions

Read `docs/DECISIONS.md` first, then `docs/PRODUCT.md` and `docs/ARCHITECTURE.md`. They are the source of truth. The repo currently contains plans only; check the code before claiming anything exists.

## Project in one paragraph

Shopmates is a Django monolith that lets neighboring shops negotiate cross-promotion deals, redeem them with staff-confirmed QR codes, and see a fairness summary. A hosted LLM drafts text and explains numbers; Python validates and calculates.

## Working style the owner wants

- Direct and honest. Push back on weak ideas and say what you did not verify.
- Short answers. No filler.
- Ask before big decisions (see "Open" in DECISIONS.md). Do not guess an answer to an open decision.
- Report real results only. Never claim something works until it has been run. Say what was and wasn't tested.
- Don't mention AI in academic ideation or paper text unless asked.
- The main screen is an inbox of actions, not a dashboard.

## Rules for changes

- Never commit to `main`. Use a feature branch. Don't push or open PRs unless asked.
- Stage specific files. Never commit `.env`, `db.sqlite3`, weights, or local tool folders.
- Never print or paste secrets. If a key is needed, tell the user to put it in `.env`.
- Keep the monolith. LLM calls go only through `ai/client.py`.
- The LLM never computes numbers the app trusts, and its output is validated and escaped.
- Authorization on every view and API: a shop must never see another shop's deals.
- Redemption confirmation must be idempotent and enforced by a database constraint.
- Prefer the simplest thing that satisfies the requirement. No extra features, no speculative abstractions.

## Before you finish a task

- Run the tests and the system check.
- If a UI change, load the page and look at it.
- Update the relevant doc if behavior or a decision changed.
- State what is verified and what is not.

## Known environment constraints

Free hosting (PythonAnywhere): 512 MB disk, CPU limits, and an outbound allowlist. No local ML models. See `docs/DEPLOYMENT.md`.
