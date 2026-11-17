"""The public stats page lists each category as label and value rows, not a wide table."""
import re

from django.test import override_settings
from django.urls import reverse

from .helpers import DealTestCase


class StatsPageTests(DealTestCase):
    def page(self):
        response = self.client.get(reverse('deals:stats'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    @override_settings(STATS_MIN_GROUP=1)
    def test_each_category_is_a_kv_list_and_there_is_no_table(self):
        self.active_deal()
        html = self.page()
        self.assertNotIn('<table', html)
        block = re.search(r'<dl class="kv">(.*?)</dl>', html, re.S)
        self.assertIsNotNone(block)
        for label in ('Shops', 'Deals', 'Redemptions', 'Per shop'):
            self.assertIn(f'<dt>{label}</dt>', block.group(1))

    @override_settings(STATS_MIN_GROUP=5)
    def test_small_categories_stay_hidden_on_the_page(self):
        self.active_deal()
        html = self.page()
        self.assertNotIn('<dl class="kv">', html)
        self.assertIn('Not enough shops in any category yet', html)
        self.assertIn('hidden for privacy', html)
