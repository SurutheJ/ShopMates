"""
Load test: N concurrent virtual users hit the main pages and we report the
median and p95 time per page.

    python scripts/load_test.py http://127.0.0.1:8002 shopmates-demo-1 --label before
    python scripts/load_test.py http://127.0.0.1:8002 shopmates-demo-1 --label after

Half the users log in as demo_cafe and half as demo_books (the two shops in
seeded deal 1), so the deal summary page has data for everyone. Start the server
with the AI limit raised and no LLM key, so the playbook runs on the fallback
and the per-user throttle does not hide the real cost:

    AI_DRAFT_LIMIT_PER_HOUR=100000 AI_API_KEY= python manage.py runserver 8002 --noreload

Results are saved to docs/load/<label>.json. Numbers only compare runs made on
the same machine with the same server command. This is the Django dev server,
not the production host.
"""
import argparse
import json
import re
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

PAGES = [
    ('inbox', '/inbox/'),
    ('discover', '/discover/'),
    ('summary', '/deals/1/summary/'),
    ('playbook', '/playbook/?q=What+deal+should+a+bakery+offer+a+flower+shop%3F'),
]
USERS = ['demo_cafe', 'demo_books']


def login(base, username, password):
    s = requests.Session()
    page = s.get(f'{base}/accounts/login/', timeout=30)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text).group(1)
    r = s.post(f'{base}/accounts/login/', data={'login': username, 'password': password,
                                                'csrfmiddlewaretoken': token},
               headers={'Referer': f'{base}/accounts/login/'}, timeout=30)
    if '/accounts/login/' in r.url:
        raise SystemExit(f'login failed for {username}')
    return s


def worker(base, session, rounds, timings, errors, start_gate):
    start_gate.wait()
    for _ in range(rounds):
        for name, path in PAGES:
            t0 = time.perf_counter()
            try:
                r = session.get(base + path, timeout=60)
                ok = r.status_code == 200
            except requests.RequestException:
                ok = False
            ms = (time.perf_counter() - t0) * 1000
            if ok:
                timings[name].append(ms)
            else:
                errors[name] += 1


def percentile(values, pct):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(pct / 100 * (len(values) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('password')
    ap.add_argument('--users', type=int, default=20)
    ap.add_argument('--rounds', type=int, default=5)
    ap.add_argument('--label', required=True)
    a = ap.parse_args()

    sessions = [login(a.base, USERS[i % 2], a.password) for i in range(a.users)]
    timings = {n: [] for n, _ in PAGES}
    errors = {n: 0 for n, _ in PAGES}
    gate = threading.Event()
    threads = [threading.Thread(target=worker, args=(a.base, s, a.rounds, timings, errors, gate))
               for s in sessions]
    for t in threads:
        t.start()
    t0 = time.perf_counter()
    gate.set()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0

    rows = {}
    print(f'{a.users} users x {a.rounds} rounds, wall {wall:.1f}s')
    print(f'{"page":10} {"n":>4} {"errors":>6} {"median ms":>10} {"p95 ms":>8}')
    for name, _ in PAGES:
        v = timings[name]
        if v:
            rows[name] = {'n': len(v), 'errors': errors[name], 'median_ms': round(statistics.median(v), 1),
                          'p95_ms': round(percentile(v, 95), 1)}
        else:
            rows[name] = {'n': 0, 'errors': errors[name], 'median_ms': None, 'p95_ms': None}
        r = rows[name]
        print(f'{name:10} {r["n"]:>4} {r["errors"]:>6} {r["median_ms"]!s:>10} {r["p95_ms"]!s:>8}')

    out = Path(__file__).resolve().parent.parent / 'docs' / 'load'
    out.mkdir(exist_ok=True)
    (out / f'{a.label}.json').write_text(json.dumps({
        'label': a.label, 'run_at': datetime.now().isoformat(timespec='seconds'),
        'users': a.users, 'rounds': a.rounds, 'wall_seconds': round(wall, 1),
        'server': 'django dev server, DEBUG on, SQLite, LLM fallback', 'pages': rows}, indent=2) + '\n')


if __name__ == '__main__':
    main()
