"""
Checks the design reference files against the rules in design/README.md.

    pip install playwright && playwright install chromium
    python design/check_design.py            # from the repo root

For every page, screen, tab, wizard step and open sheet, at 8 viewport sizes, it reports:
  OVERFLOW  the document scrolls (vertically or horizontally)
  CLIPPED   the pinned action bar or the inner scroll region is pushed out of view
  SQUEEZED  the inner scroll region is shorter than 72px (content not reachable in practice)
  WIDE      content inside a scroll region is wider than the region
  TAP       a visible control is smaller than 44px in height (inline text links and checkboxes inside a 44px label are exempt)
Then it checks text/background color contrast for the token pairs the design uses (WCAG 4.5:1).
Exit code 1 if anything fails. Use the same ideas on the Django pages with design/check_layout.py.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
PAGES = ['shell-demo.html', 'public-demo.html']
SIZES = [(360, 640), (390, 780), (414, 896), (768, 1024), (1024, 768), (1280, 720), (667, 375), (1440, 900)]
MIN_SCROLL = 72

JS_STATE = """
() => {
  const vw = innerWidth, vh = innerHeight, d = document.documentElement;
  const out = {overflow: d.scrollHeight > d.clientHeight || d.scrollWidth > d.clientWidth,
               dims: [d.scrollWidth, d.scrollHeight, d.clientWidth, d.clientHeight], clipped: [], squeezed: null, wide: [], tap: []};
  const scr = document.querySelector('.screen.active');
  if (!scr) return out;
  const visible = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !el.closest('[hidden]'); };
  const openSheet = scr.querySelector('.sheet-backdrop.open');
  const scope = openSheet || scr;
  Array.from(scope.querySelectorAll('.actionbar')).filter(visible).forEach(bar => { const r = bar.getBoundingClientRect(); const m = document.querySelector('.main').getBoundingClientRect();
    if (r.bottom > m.bottom + 1 || r.top < m.top) out.clipped.push('actionbar'); });
  const sc = Array.from(scope.querySelectorAll('.scroll')).filter(visible);
  sc.forEach(s => { const r = s.getBoundingClientRect(); const m = document.querySelector('.main').getBoundingClientRect();
    if (r.height < 72) out.squeezed = Math.round(r.height);
    if (r.bottom > m.bottom + 1) out.clipped.push('scroll');
    if (s.scrollWidth > s.clientWidth + 1) out.wide.push(Math.round(s.scrollWidth) + '>' + Math.round(s.clientWidth)); });
  const sels = 'button, a, select, textarea, input, [role=tab]';
  scope.querySelectorAll(sels).forEach(el => {
    if (!visible(el)) return;
    const r = el.getBoundingClientRect();
    const isBox = el.matches('input[type=checkbox],input[type=radio]');
    const lab = el.closest('label');
    if (isBox) { if (lab && lab.getBoundingClientRect().height >= 44) return; }
    if (el.tagName === 'A' && el.closest('p, label, li') && !el.classList.contains('btn')) return;
    if (el.closest('.chips') && el.classList.contains('chip') && r.height >= 44) return;
    if (r.height < 43.5) out.tap.push((el.textContent || el.getAttribute('aria-label') || el.type || el.tagName).trim().slice(0, 24) + ' ' + Math.round(r.height) + 'px');
  });
  if (!openSheet) { // top bar and nav are part of every screen
    document.querySelectorAll('.topbar button, .bottomnav button, .rail button').forEach(el => {
      if (!visible(el)) return; const r = el.getBoundingClientRect();
      if (r.height < 43.5 || r.width < 43.5) out.tap.push('nav:' + (el.getAttribute('aria-label') || el.textContent.trim().slice(0, 12)) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    });
  }
  return out;
}
"""

JS_PLAN = """
() => Array.from(document.querySelectorAll('.screen')).map(s => ({
  id: s.id.slice(2),
  tabs: Array.from(s.querySelectorAll('[data-tabs] button')).map(b => b.dataset.t),
  steps: Array.from(new Set(Array.from(s.querySelectorAll('[data-step]')).map(p => Number(p.dataset.step)))),
  sheets: Array.from(s.querySelectorAll('.sheet-backdrop')).map(b => b.id)}))
"""


def luminance(hex_):
    h = hex_.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PAIRS = [  # (name, foreground, background): the v2 "Light Coral" palette
    ('ink on page', '#1A1410', '#FFFFFF'), ('ink on sand', '#1A1410', '#F7F2EE'), ('ink-2 on card', '#3A2F29', '#FFFFFF'),
    ('muted on card', '#6A5C54', '#FFFFFF'), ('muted on page', '#6A5C54', '#FFFFFF'), ('muted on sand', '#6A5C54', '#F7F2EE'),
    ('muted on teal-soft', '#6A5C54', '#DCFCE7'),
    ('ink on coral (primary button, coral tile)', '#1A1410', '#FF7A59'), ('ink on coral-press', '#1A1410', '#FF9275'),
    ('white on ink (nav pill, dark button, toast)', '#FFFFFF', '#1A1410'), ('nav label on ink', '#B8ADA6', '#1A1410'),
    ('coral-ink on card', '#B5391A', '#FFFFFF'), ('coral-ink on coral-soft', '#B5391A', '#FFE9E1'),
    ('white on green', '#FFFFFF', '#15803D'), ('white on green-press', '#FFFFFF', '#116B33'),
    ('green-ink on page (links)', '#166534', '#FFFFFF'), ('green-ink on teal-soft (ok badge, callout)', '#166534', '#DCFCE7'),
    ('ink on sun (yellow tile)', '#1A1410', '#F5A81C'), ('sun-ink on sun-soft (warn badge)', '#7A4A00', '#FFEFC9'),
    ('sun-ink on card (warning text)', '#7A4A00', '#FFFFFF'), ('ink on sun-soft', '#1A1410', '#FFEFC9'),
    ('danger on danger-soft', '#B42318', '#FEE2E2'), ('danger on card', '#B42318', '#FFFFFF'), ('ink on danger-soft', '#1A1410', '#FEE2E2'),
    ('ink on coral-wash (waiting row)', '#1A1410', '#FFF4EF'), ('muted on coral-wash', '#6A5C54', '#FFF4EF'),
    ('cafe', '#92400E', '#FDE8C4'), ('bookstore', '#1E40AF', '#DBEAFE'), ('bakery', '#9D174D', '#FCE7F3'),
    ('restaurant', '#991B1B', '#FEE2E2'), ('flowers', '#6B21A8', '#F3E8FF'), ('fitness', '#166534', '#DCFCE7'),
    ('salon', '#9F1239', '#FFE4E6'), ('retail', '#075985', '#E0F2FE'), ('other', '#44403C', '#E7E5E4'),
    ('white on category avatar (cafe)', '#FFFFFF', '#92400E'), ('white on category avatar (bookstore)', '#FFFFFF', '#1E40AF'),
]


def main():
    bad = 0
    checked = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome') if pathlib.Path('/usr/bin/google-chrome').exists() else p.chromium.launch()
        for page_name in PAGES:
            url = (HERE / page_name).as_uri()
            for w, h in SIZES:
                ctx = browser.new_context(viewport={'width': w, 'height': h})
                pg = ctx.new_page()
                pg.goto(url)
                plan = pg.evaluate(JS_PLAN)
                for s in plan:
                    states = [('base', None)]
                    states += [('tab ' + t, ('tab', t)) for t in s['tabs']]
                    states += [('step %d' % n, ('step', n)) for n in s['steps'][1:]] if s['steps'] else []
                    states += [('sheet ' + sh, ('sheet', sh)) for sh in s['sheets']]
                    for label, act in states:
                        pg.evaluate('(id) => SM.show(id)', s['id'])
                        if act and act[0] == 'tab':
                            pg.evaluate("(t) => SM.selectTab(document.querySelector('.screen.active [data-tabs] button[data-t=\"' + t + '\"]'))", act[1])
                        elif act and act[0] == 'step':
                            pg.evaluate("(n) => SM.setStep(document.querySelector('.screen.active'), n)", act[1])
                        elif act and act[0] == 'sheet':
                            pg.evaluate("(id) => document.getElementById(id).classList.add('open')", act[1])
                        r = pg.evaluate(JS_STATE)
                        checked += 1
                        tag = f'{page_name} {w}x{h} {s["id"]} [{label}]'
                        if r['overflow']:
                            bad += 1; print('OVERFLOW', tag, r['dims'])
                        if r['clipped']:
                            bad += 1; print('CLIPPED ', tag, r['clipped'])
                        if r['squeezed'] is not None:
                            bad += 1; print('SQUEEZED', tag, str(r['squeezed']) + 'px')
                        if r['wide']:
                            bad += 1; print('WIDE    ', tag, r['wide'])
                        if r['tap']:
                            bad += 1; print('TAP     ', tag, sorted(set(r['tap']))[:6])
                ctx.close()
        browser.close()
    print(f'states checked: {checked}, failing states: {bad}')
    low = 0
    for name, fg, bg in PAIRS:
        rt = ratio(fg, bg)
        flag = 'ok ' if rt >= 4.5 else 'LOW'
        if rt < 4.5:
            low += 1
        print(f'{flag} {rt:5.2f}  {name}')
    print('contrast pairs below 4.5:', low)
    sys.exit(1 if (bad or low) else 0)


if __name__ == '__main__':
    main()
