# First-draft checklist (P2-A3)

| Requirement | Where | Status |
|---|---|---|
| 1. Updated product scope (1 page) | [UPDATED_PRODUCT_SCOPE.md](UPDATED_PRODUCT_SCOPE.md) | Done |
| 2. Functional Django project | `manage.py`, `shopmates_project/` | Done |
| At least one app | `accounts`, `deals`, `ai` | Done |
| At least two models | 10 models; `Shop`, `Deal`, `DealVersion`, `Voucher`, `Redemption` and others | Done |
| At least one relationship | `Deal.proposer` and `Deal.recipient` to `Shop`; `DealVersion.deal`; `Redemption.voucher` (one-to-one) | Done |
| Working views and templates | `deals/views.py`, `accounts/views.py`, `templates/` | Done |
| At least one form | Proposal and counter form (`deals/forms.py`), shop form, redeem form | Done |
| One database-backed workflow | Propose, accept, activate, redeem, see it counted on the summary; covered in `deals/tests/test_lifecycle.py` and `test_redemption.py` | Done |
| 3. Initial AI implementation | [INITIAL_AI_IMPLEMENTATION.md](INITIAL_AI_IMPLEMENTATION.md), [../README_AI.md](../README_AI.md) | Done |
| 4. Progress and roadmap table | [ROADMAP.md](ROADMAP.md) | Done |
| 5. GitHub push with README | [../README.md](../README.md) has install and run steps | Pushed by the team |

Checked on the final commit of this branch: `python manage.py check` reports no issues, `makemigrations --check` reports no changes, and `python manage.py test` runs 479 tests, all passing.
