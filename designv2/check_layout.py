"""
Fail if any page scrolls the document (vertical or horizontal) at common sizes.

    pip install playwright && playwright install chromium
    python design/check_layout.py http://localhost:8000 demo_cafe shopmates-demo-1 /inbox/ /discover/ /deals/1/

Logs in through the allauth form at /accounts/login/, then loads each path.
Exit code 1 if any page overflows. The one allowed scroll region is an inner
element, so the document itself should always fit the viewport.
"""
import sys
from playwright.sync_api import sync_playwright

SIZES = [(360, 640), (390, 780), (414, 896), (768, 1024), (1024, 768), (1280, 720), (667, 375)]


def main(base, user, password, paths):
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 390, 'height': 780})
        page.goto(f'{base}/accounts/login/')
        page.fill('input[name=login]', user)
        page.fill('input[name=password]', password)
        page.click('button[type=submit]')
        cookies = page.context.cookies()
        for w, h in SIZES:
            ctx = browser.new_context(viewport={'width': w, 'height': h})
            ctx.add_cookies(cookies)
            pg = ctx.new_page()
            for path in paths:
                pg.goto(base + path)
                r = pg.evaluate("() => ({sh: document.documentElement.scrollHeight, ch: document.documentElement.clientHeight,"
                                " sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
                if r['sh'] > r['ch'] or r['sw'] > r['cw']:
                    bad += 1
                    print(f'OVERFLOW {w}x{h} {path} {r}')
            ctx.close()
        browser.close()
    print('overflow cases:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
