# Stage 3 report: Inbox, Discover, Shop, Deal (designv2 restyle)

Written after the fact, so there is no per-stage history: the file list comes from working notes and `git status`, not from a diff of this stage alone.

## What was done
- **Inbox**: head with shop name, tabs (Your turn, Running, Waiting, Past), two stat tiles, deal rows with initials avatars, pinned "Find a neighbor" bar, preview pane from 1100px. Staff and pending-shop versions.
- **Discover**: search, category chips (short names), match rows with a score pill and reason line, tap-to-open tile with keywords, Radar icon button.
- **Shop page**: Back, Report (coming soon), three tiles (match, miles, typical spend), "Why this match" card, pinned "Propose a deal".
- **Propose wizard and counter form**: four steps with stepper, "Is it balanced?" card on step 4, counter form with diff.
- **Deal page**: Terms, Chat, History tabs; pinned Decline / Counter / Accept.

## Files created or changed
- Templates: `deals/inbox.html`, `deals/_deal_row.html`, `accounts/discover.html`, `accounts/shop_detail.html`, `deals/deal_form.html`, `deals/deal_detail.html`, `partials/_field.html`.
- CSS and JS: `static/css/app.css` (sections for inbox, discover tile, wizard, deal), `static/js/app.js` (tabs, wizard, fairness card, AI draft).
- Python: `ai/matching.py` (`_KEYWORDS`), `accounts/models.py` (`Shop.category_short`), `deals/forms.py` (`class="input"` on widgets), `deals/views.py`.
- Tests: `deals/tests/test_inbox_screen.py`, `test_deal_screen.py`, `test_deal_form_layout.py`, `accounts/test_screens.py`, `accounts/test_shop_screens.py`.

## Checked
Layout (no page scroll) and tap targets on these pages at the sizes in `check_layout.py`; the 1280 inbox centring added in session 7 (empty inbox is one 640px column, like My shop).

## Not verified
Keyboard Tab order in the wizard and tiles; Safari and Firefox; the Discover tile at 768 and 1280; the "Is it balanced?" card was only syntax-checked in session 6.
