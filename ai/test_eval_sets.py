"""The development and held-out question sets are frozen: changing one fails these tests.

If you add questions on purpose, make a new dated file instead of editing a frozen one,
and say so in docs/EVALUATION.md. A held-out set that was edited after tuning is not held out.
"""
import hashlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from ai.playbook_data import PASSAGES

SETS = Path(__file__).resolve().parent / 'eval_sets'
FROZEN = {
    'dev_retrieval': (14, '7662be397b99a77b28aa99af3729a9c1dab15c864fee6e5b31f1ea2a28c86178'),
    'held_out_retrieval': (6, '7ef88d03a32cc54bfa5c1060c18ef2974f1e462bab8fd790a2d73fd2f2661a41'),
}


class FrozenSetsTests(SimpleTestCase):
    def load(self, name):
        return json.loads((SETS / f'{name}.json').read_text())

    def test_sets_match_their_frozen_hash(self):
        for name, (count, digest) in FROZEN.items():
            data = self.load(name)
            canon = json.dumps(data['cases'], sort_keys=True, separators=(',', ':'))
            self.assertEqual(len(data['cases']), count, name)
            self.assertEqual(hashlib.sha256(canon.encode()).hexdigest(), digest, name)

    def test_every_set_has_a_freeze_date(self):
        for name in FROZEN:
            self.assertEqual(self.load(name)['frozen_on'], '2026-11-16')

    def test_expected_ids_exist_in_the_playbook(self):
        ids = {p['id'] for p in PASSAGES}
        for name in FROZEN:
            for case in self.load(name)['cases']:
                self.assertIn(case['expected'], ids, case['question'])

    def test_dev_and_held_out_do_not_share_questions(self):
        dev = {c['question'] for c in self.load('dev_retrieval')['cases']}
        held = {c['question'] for c in self.load('held_out_retrieval')['cases']}
        self.assertFalse(dev & held)
