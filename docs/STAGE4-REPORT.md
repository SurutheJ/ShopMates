# Stage 4 report: the rest of the screens, and the end of `.legacy`

Session 6 did QR, Redeem, Playbook, My shop, Staff and Radar. Session 7 did everything below, so every page is now on designv2 and nothing renders inside `.legacy`.

## Done in session 7
| Page | What changed |
|---|---|
| Landing | Hero, 4 steps, pinned Log in / Create account (or Set up your shop when signed in). |
| Login, Sign up | Google button first, one banner for form errors, pinned primary button. Label "Username or email". |
| Log out, Password reset, reset sent, new password, password changed, change password | Ported (allauth templates overridden in `templates/account/`). Reset text no longer promises a one-hour link (allauth's default is longer). |
| Google button | Ghost block button with the Google logo; the "or" line is part of the partial. |
| Voucher start and voucher | Empty states for used and expired, `.code` tile for ready. Still bare: no nav, no account links. |
| Pending, forbidden, 403, 403_csrf, 404 | One empty-state layout with an icon and a Go home button. |
| 500 | Stays standalone (no static files, by design and by test); now uses the design colours and a near-black button. |
| Stats | Three tiles, category cards. |
| Deal summary | Native screen: back, status badge, table, chart, fairness callout, coach, export, pinned QR and card buttons. |
| Counter card | Logo mark, coral border, green perk line (`card.css`). |
| Inbox | Empty or no-preview inbox is centred at 768 and wider (`.split.solo`). |
| States | Empty states on every list; spinner while the AI buttons wait (`.busy`); red text when they fail (`.failed`); offline banner (`#offline-note`, shown by `app.js` on the browser's offline event). |

## `.legacy`
No template uses it. `base.html` no longer loads `static/css/base.css`, and the default content block (used only by allauth pages we did not restyle) is a plain narrow screen. `base.css` is cut down to a comment; the file can be deleted.

## Files created or changed (session 7)
- Templates changed: `base.html`, `home.html`, `account/{login,signup,logout}.html`, `partials/_google_button.html`, `accounts/{pending,forbidden}.html`, `403.html`, `403_csrf.html`, `404.html`, `500.html`, `deals/{voucher_start,voucher_show,stats,deal_summary,_counter_card,inbox}.html`.
- Templates created: `account/password_{reset,reset_done,reset_from_key,reset_from_key_done,change}.html`, `partials/_auth_fields.html`.
- Python created: `accounts/templatetags/{__init__,ui}.py` (`as_input` filter: allauth builds its own forms, so the `input` class is added in the template).
- CSS and JS: `static/css/app.css` (appended rules), `static/css/card.css`, `static/css/base.css` (emptied), `static/js/app.js` (status helper, offline note).
- `scripts/check_targets.py`: login click now targets `button[form=login-form]` (see below).
- Tests created: `accounts/test_public_screens.py`, `shopmates_project/test_ported_pages.py`; added to `shopmates_project/test_shell.py` and `deals/tests/test_inbox_screen.py`.
- `accounts/forms.py`: one comment reworded.

## Result
`check` clean, `makemigrations --check` clean, **516 tests OK** (479 at the start of the session). `check_layout` 0 overflow (visitor, owner, staff pages) and `check_targets` 0 problems, run on the scratch preview, port 8002, against a copy of `db.sqlite3`.

## Found along the way
- The Google button now comes before Log in, and both check scripts clicked the first `button[type=submit]`, so they would have clicked Google and run as a visitor. I fixed `scripts/check_targets.py`. `designv2/check_layout.py` has the same line and I did not touch it (off limits); I ran a copy with the selector changed.
- An early owner-page run in this session passed only because it was never signed in; I re-ran everything after the fix.
- Dev settings show Django's own debug 404, which is what first looked like an overflow on `/no-such-page/`. Our 404 was checked with `DEBUG=False`.

## Not verified
Safari and Firefox, a real phone, landscape; the offline banner was tested by dispatching the browser's `offline` event, not by cutting a real connection; the ready voucher (an unused code) was not looked at on screen, only tested; the 403 and 403_csrf pages were not opened in a browser (same layout as 404, covered by tests); the rest of allauth's own pages (email addresses, set password, social connections) are unstyled generic markup and not linked from the app; spinner and red error text were not seen on screen (a live AI call was not made).
