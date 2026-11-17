"""
List tap targets under 44px, and text fields under 16px (iOS Safari zooms the page when one is focused), on the running app (the design check does not cover un-ported pages).

    python scripts/check_targets.py http://127.0.0.1:8002 demo_cafe shopmates-demo-1 /inbox/ /redeem/ /stats/
    python scripts/check_targets.py http://127.0.0.1:8002 - - /accounts/login/ /accounts/signup/

Use `-` for the user and password to check pages as a visitor. Needs Playwright
(pip install playwright && playwright install chromium). Runs at 390x780 only.
A link inside a sentence is reported as "inline" and does not count as a failure
(WCAG exempts links inside text); everything else under 44px in either direction fails.
Exit code 1 if anything fails.
"""
import sys

from playwright.sync_api import sync_playwright

MIN = 44

FIND = """(min) => {
  const out = [];
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button]';
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const target = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el;
    const r = target.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.height >= min && r.width >= min) continue;
    let inline = false;
    if (el.tagName === 'A') {
      const p = el.parentElement;
      const own = (el.textContent || '').trim().length;
      const all = (p.textContent || '').trim().length;
      inline = ['P', 'LI', 'SPAN', 'SMALL', 'LABEL', 'DIV'].includes(p.tagName) && all > own + 8;
    }
    out.push({tag: el.tagName.toLowerCase() + (el.type ? '[' + el.type + ']' : ''),
              text: (el.textContent || el.value || el.name || '').trim().slice(0, 30),
              w: Math.round(r.width), h: Math.round(r.height), inline});
  }
  return out;
}"""

# A text field under 16px makes iOS Safari zoom in when it is tapped.
ZOOM = """() => [...document.querySelectorAll('input, select, textarea')]
  .filter(el => !['hidden', 'checkbox', 'radio', 'submit', 'button'].includes(el.type))
  .filter(el => el.getBoundingClientRect().height > 0 && parseFloat(getComputedStyle(el).fontSize) < 16)
  .map(el => el.name || el.id || el.type)"""


def main(base, user, password, paths):
    fails = inline = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 390, 'height': 780})
        page = ctx.new_page()
        if user != '-':
            page.goto(f'{base}/accounts/login/')
            page.fill('input[name=login]', user)
            page.fill('input[name=password]', password)
            page.click('button[form=login-form]')
        for path in paths:
            page.goto(base + path)
            for item in page.evaluate(FIND, MIN):
                if item['inline']:
                    inline += 1
                    continue
                fails += 1
                print(f"UNDER {MIN}px {path}: {item['tag']} '{item['text']}' {item['w']}x{item['h']}")
            for name in page.evaluate(ZOOM):
                fails += 1
                print(f"UNDER 16px text (iOS zooms) {path}: field '{name}'")
        browser.close()
    print(f'problems (under {MIN}px or text under 16px): {fails}   (inline links not counted: {inline})')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
