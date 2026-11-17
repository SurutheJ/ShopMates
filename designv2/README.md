# ShopMates design v2 — "Light Coral" + logo

Static reference for restyling the Django app. Open `gallery.html` to see every screen at phone/tablet/desktop/landscape.
`shell-demo.html` (14 screens, signed-in shell) and `public-demo.html` (12 public screens) are the layout source of truth; `agreement.html` and `qr-card.html` are the printables.

## Palette (tokens.css; the "Light and coral" canvas board)
- Page #FFFFFF, surface/sand #F7F2EE, line #EDE5DF · Ink #1A1410 (text, primary buttons, nav pill), ink-2 #3A2F29, muted #6A5C54
- Coral accent #FF7A59 (soft #FFE9E1, coral-as-text #B5391A): stat tiles, active nav, "your turn", counts, steps
- Green #15803D only for success/good (soft #DCFCE7, text #166534) · yellow #F5A81C small highlight (warn text #7A4A00)
- **Primary buttons are near-black with white text, not coral. Never white text on coral: use ink.**
- Category tints: `.cat--<value>` sets `--cat-bg/--cat-fg` (nine categories); initials circle uses the same pair.

## Logo assets (assets/ → Django static/img/)
- `logo-horizontal.png` landing/agreement header · `logo-mark.png` top bar, QR card, small spaces · `logo-wordmark.png` text only
- `logo-stacked-cream.png` / `logo-stacked-white.png` splash/login on cream or white/dark · `app-icon-{192,512,1024}.png`, `favicon-64.png`
- Font: Plus Jakarta Sans with system fallback (no external fonts; self-host the woff2 if desired).

## Applying to Django
1. Replace `static/css/tokens.css` and `components.css` content with these (class names unchanged from v1 design/).
2. Templates: add the inline SVG icon sprite from shell-demo.html and use `<use href="#i-…">`; swap the top bar brand for the mark+wordmark images; use `.stats .stat.coral|teal|ink|sun|sand` tiles; inbox rows `.row.turn` for "Waiting on you"; initials avatars with `.cat--<category>`; status pills get their icons via CSS `::before` (no emoji).
3. Keep v1 rules: page never scrolls (one `.scroll` region), pinned `.actionbar`, 44px targets, 4.5:1 contrast, four list states.

## Checks
`python3 -I check_design.py` (Playwright; contrast pairs + 536 viewport/screen states — currently 0 failing) and `check_layout.py`.

## Screen → Django template map
Each mock screen is a `<section id="s-NAME">` in the file listed; open it with `shell-demo.html?screen=NAME` (add `&step=2` for wizard steps).
| Screen (id) | Mock file | Django template to restyle |
|---|---|---|
| inbox | shell-demo | templates/deals/inbox.html, _deal_row.html |
| discover | shell-demo | templates/accounts/discover.html |
| shop | shell-demo | templates/accounts/shop_detail.html |
| propose, counter | shell-demo | templates/deals/deal_form.html, _counter_card.html |
| deal, agree | shell-demo | templates/deals/deal_detail.html, deal_summary.html |
| live | shell-demo | templates/deals/qr.html, card.html (QR + Results + Agreement tabs) |
| redeem | shell-demo | templates/deals/redeem.html |
| playbook | shell-demo | templates/deals/playbook.html |
| insights | shell-demo | templates/deals/stats.html |
| me | shell-demo | templates/accounts/shop_form.html, shop_staff.html |
| notifs, states | shell-demo | notification list + the four list states (empty/loading/error/offline) used everywhere |
| landing | public-demo | templates/home.html |
| login, signup, reset | public-demo | templates/account/*.html, partials/_google_button.html |
| voucher | public-demo | templates/deals/voucher_start.html, voucher_show.html |
| pending, terms, onboard | public-demo | templates/accounts/pending.html, onboarding |
| e404, e500, offline | public-demo | templates/404.html, 500.html, 403.html |
| (shell: top bar, nav) | shell-demo | templates/base.html, partials/_navbar.html, _nav_items.html |
| agreement / qr-card (print) | agreement.html, qr-card.html | deals voucher/agreement print views |

## Build order
1. tokens.css + components.css into `static/css`, logo assets into `static/img`, favicon in base.html. 2. base.html shell (top bar with mark, floating nav pill, icon sprite). 3. Inbox, Discover, Shop, Deal screens. 4. Remaining screens. 5. Run the Django tests, then `check_design.py` against rendered pages. Match the mock markup and class names rather than inventing new ones. The mocks are the spec and the rules above are the checklist.
