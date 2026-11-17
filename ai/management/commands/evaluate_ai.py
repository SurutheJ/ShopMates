"""
Repeatable evaluation of the AI features. Prints a Markdown report.

    python manage.py evaluate_ai
    python manage.py evaluate_ai --live     # also times the real LLM (needs AI_API_KEY)

Everything here uses the same code paths as the app. Model failures are
simulated with a fake client, so the guardrail results are real but say
nothing about the quality of a live model's wording.
"""

import json
import time
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from accounts.models import Shop
from ai import matching, playbook
from ai.playbook_data import PASSAGES
from ai.client import AIError, default_client
from ai.services import answer_playbook, draft_deal
from deals.forms import DealTermsForm  # noqa: F401  (documented dependency of draft validation)

TODAY = date(2026, 11, 15)

# Frozen question sets (see ai/test_eval_sets.py). Each case is (question, expected passage id).
EVAL_SETS = Path(__file__).resolve().parents[2] / 'eval_sets'


def load_set(name):
    cases = json.loads((EVAL_SETS / f'{name}.json').read_text())['cases']
    return [(c['question'], c['expected']) for c in cases]


RETRIEVAL = load_set('dev_retrieval')
HELD_OUT = load_set('held_out_retrieval')




class Fake:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error

    def generate_json(self, prompt):
        if self.error:
            raise self.error
        return self.response


def shop(name, category, value):
    return Shop(name=name, category=category, address='x', typical_order_value=value)



GOOD = {'offer_text': '15% off a drink with a book receipt', 'discount_percent': 15, 'redemption_cap': 40,
        'suggested_duration_days': 21, 'message_to_neighbor': 'Hi! Want to swap referrals for three weeks?'}
DRAFT_CASES = [
    ('valid output', GOOD, 'ai'),
    ('discount 90% (over limit)', {**GOOD, 'discount_percent': 90}, 'fallback'),
    ('discount is text', {**GOOD, 'discount_percent': 'lots'}, 'fallback'),
    ('missing key', {k: v for k, v in GOOD.items() if k != 'redemption_cap'}, 'fallback'),
    ('duration 9999 days', {**GOOD, 'suggested_duration_days': 9999}, 'fallback'),
    ('empty offer text', {**GOOD, 'offer_text': ''}, 'fallback'),
    ('400+ char message (should be trimmed)', {**GOOD, 'message_to_neighbor': 'x' * 900}, 'ai'),
    ('model returns a list, not an object', None, 'fallback'),
    ('API error', AIError('The AI service could not be reached (Timeout).'), 'fallback'),
]


class Command(BaseCommand):
    help = 'Run the AI evaluation and print a Markdown report.'

    def add_arguments(self, parser):
        parser.add_argument('--live', action='store_true', help='Also time the real LLM (needs AI_API_KEY).')

    def handle(self, *args, **options):
        out = self.stdout.write
        out('# AI evaluation report\n')

        # A. Match score ordering
        out('## A. Partner match ranking (expected order)\n')
        me = shop('Green Cafe', 'cafe', 9)
        candidates = [
            ('Bookstore 0.1 mi', shop('Books', 'bookstore', 22), 0.1),
            ('Yoga 0.4 mi', shop('Yoga', 'fitness', 15), 0.4),
            ('Other cafe 0.1 mi', shop('Cafe2', 'cafe', 9), 0.1),
            ('Bookstore 4 mi', shop('FarBooks', 'bookstore', 22), 4.0),
        ]
        ranked = sorted(candidates, key=lambda c: -matching.match_score(me, c[1], c[2])['score'])
        for name, s, d in ranked:
            out(f"- {name}: {matching.match_score(me, s, d)['score']}")
        expected = ['Bookstore 0.1 mi', 'Yoga 0.4 mi']
        out(f"\nTop two as expected: {[r[0] for r in ranked[:2]] == expected}\n")

        # B. Retrieval, before and after query expansion
        out('## B. Playbook retrieval (TF-IDF)\n')
        out('| # | Question | Expected | Top result (baseline) | Top result (with synonyms) |')
        out('|---|---|---|---|---|')
        base_idx, exp_idx = playbook.Index(PASSAGES, expand=False), playbook.Index(PASSAGES, expand=True)

        def run(label, cases):
            h = {'base1': 0, 'base3': 0, 'exp1': 0, 'exp3': 0}
            times = []
            for i, (question, expected) in enumerate(cases, 1):
                base_ids = [r['id'] for r in base_idx.search(question, k=3)]
                start = time.perf_counter()
                exp_ids = [r['id'] for r in exp_idx.search(question, k=3)]
                times.append((time.perf_counter() - start) * 1000)
                h['base1'] += bool(base_ids) and base_ids[0] == expected
                h['base3'] += expected in base_ids
                h['exp1'] += bool(exp_ids) and exp_ids[0] == expected
                h['exp3'] += expected in exp_ids
                out(f"| {label}{i} | {question} | {expected} | "
                    f"{(base_ids[0] if base_ids else '(none)')}{' ✓' if base_ids and base_ids[0] == expected else ''} | "
                    f"{(exp_ids[0] if exp_ids else '(none)')}{' ✓' if exp_ids and exp_ids[0] == expected else ''} |")
            return h, sum(times) / len(times)

        dev, dev_ms = run('D', RETRIEVAL)
        held, held_ms = run('H', HELD_OUT)
        for name, h, n in (('Development set (used to design the fix)', dev, len(RETRIEVAL)),
                           ('Held-out set (written beforehand)', held, len(HELD_OUT))):
            out(f"\n{name}: baseline Hit@1 {h['base1']}/{n}, Hit@3 {h['base3']}/{n}; "
                f"with synonyms Hit@1 {h['exp1']}/{n}, Hit@3 {h['exp3']}/{n}.")
        out(f'\nMean search time {dev_ms:.3f} ms.\n')

        # C. Draft validation
        out('## C. AI draft guardrails (simulated model output)\n')
        out('| # | Case | Expected | Actual | Pass |')
        out('|---|---|---|---|---|')
        a, b = shop('Green Cafe', 'cafe', 9), shop('Pageturner', 'bookstore', 24)
        b.name = 'Pageturner'
        passed = 0
        for i, (label, response, expected) in enumerate(DRAFT_CASES, 1):
            client = Fake(error=response) if isinstance(response, Exception) else Fake(response=response)
            result = draft_deal(a, b, client=client, today=TODAY)
            ok = result['source'] == expected
            if label.startswith('400+'):
                ok = ok and len(result['message']) <= 400
            passed += ok
            out(f"| {i} | {label} | {expected} | {result['source']} | {'yes' if ok else 'NO'} |")
        out(f'\nPassed {passed}/{len(DRAFT_CASES)}.\n')

        # D. Playbook answer guardrails
        out('## D. Playbook answer guardrails\n')
        ok_cite = answer_playbook('bakery flower shop deal', client=Fake({'answer': 'Offer pastry.', 'used': ['bakery-flowers']}))
        bad_cite = answer_playbook('bakery flower shop deal', client=Fake({'answer': 'Sure.', 'used': ['invented']}))
        no_hit = answer_playbook('qqqq zzzz', client=Fake({'answer': 'x', 'used': []}))
        out(f"- Grounded answer accepted: {ok_cite['source'] == 'ai'}")
        out(f"- Invented source rejected: {bad_cite['source'] == 'fallback'}")
        out(f"- Unmatched question gets no model call: {no_hit['source'] == 'none'}\n")

        # E. Live model
        out('## E. Live LLM\n')
        if not options['live']:
            out('Not run (use --live with AI_API_KEY set).')
        elif default_client() is None:
            out('Skipped: AI_API_KEY is not set.')
        else:
            out('| Pair | Source | Seconds | Discount | Cap |')
            out('|---|---|---|---|---|')
            for x, y in [(a, b), (shop('Rise Bakery', 'bakery', 8), shop('Petal', 'flowers', 30)),
                         (shop('Yoga', 'fitness', 15), shop('Grind', 'cafe', 7))]:
                start = time.perf_counter()
                result = draft_deal(x, y, today=TODAY)
                secs = time.perf_counter() - start
                terms = result['terms']
                out(f"| {x.get_category_display()} + {y.get_category_display()} | {result['source']} | {secs:.1f} | "
                    f"{terms['discount_percent']} | {terms['redemption_cap']} |")
                if result['source'] == 'fallback':
                    out(f"|  | reason: {result['reason']} | | | |")
