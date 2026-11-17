"""Pages must not run more queries as data grows (the N+1 problem).

Each test loads a page with a little data and again with a lot, and requires
the same number of queries. A page that loops over rows and hits the database
inside the loop fails here.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Shop
from deals import services
from deals.models import DealMessage

from .helpers import DealTestCase, make_shop, make_terms, make_user


class QueryCountTests(DealTestCase):
    def queries(self, url, user):
        self.client.force_login(user)
        self.client.get(url)  # warm-up: a first view may write one-time status changes
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx)

    def add_partner_deals(self, start, count):
        """`count` neighbors each send the cafe a proposal; every other one is accepted and running."""
        for i in range(start, start + count):
            owner = make_user(f'partner_owner_{i}')
            partner = make_shop(f'Partner {i}', owner, category='bakery')
            deal = services.create_draft(partner, self.cafe, owner, make_terms(), send=True)
            if i % 2:
                services.accept(deal, self.cafe_owner)

    def test_inbox_query_count_does_not_grow_with_deals(self):
        self.add_partner_deals(0, 2)
        small = self.queries(reverse('deals:inbox'), self.cafe_owner)
        self.add_partner_deals(2, 8)
        large = self.queries(reverse('deals:inbox'), self.cafe_owner)
        self.assertEqual(small, large, f'inbox: {small} queries with 2 deals, {large} with 10')

    def test_discover_query_count_does_not_grow_with_shops(self):
        for i in range(2):
            make_shop(f'Shop {i}', category='bakery')
        small = self.queries(reverse('accounts:discover'), self.cafe_owner)
        for i in range(2, 12):
            make_shop(f'Shop {i}', category='bakery')
        large = self.queries(reverse('accounts:discover'), self.cafe_owner)
        self.assertEqual(small, large, f'discover: {small} vs {large}')

    def test_deal_page_query_count_does_not_grow_with_messages_and_versions(self):
        deal = self.proposed_deal()
        small = self.queries(deal.get_absolute_url(), self.cafe_owner)
        for i in range(10):
            DealMessage.objects.create(deal=deal, author=self.books_owner, shop=self.books, body=f'hello {i}')
        for i in range(3):
            user = self.books_owner if i % 2 == 0 else self.cafe_owner
            services.counter(deal, user, make_terms(discount_percent=10 + i + 1))
            deal.refresh_from_db()
        large = self.queries(deal.get_absolute_url(), self.cafe_owner)
        self.assertEqual(small, large, f'deal page: {small} vs {large}')

    def test_summary_query_count_does_not_grow_with_redemptions(self):
        deal = self.active_deal(redemption_cap=50)
        self.redeem_once(deal, self.cafe, self.books_owner)
        small = self.queries(reverse('deals:summary', args=[deal.pk]), self.cafe_owner)
        for _ in range(10):
            self.redeem_once(deal, self.cafe, self.books_owner)
            self.redeem_once(deal, self.books, self.cafe_owner)
        large = self.queries(reverse('deals:summary', args=[deal.pk]), self.cafe_owner)
        self.assertEqual(small, large, f'summary: {small} vs {large}')

    def test_stats_query_count_does_not_grow_with_data(self):
        for i in range(5):  # a category is only listed from 5 shops (STATS_MIN_GROUP)
            make_shop(f'Bakery {i}', category='bakery')
        small = self.queries(reverse('deals:stats'), self.cafe_owner)
        for i in range(5, 17):
            make_shop(f'Extra {i}', category='bakery')
        large = self.queries(reverse('deals:stats'), self.cafe_owner)
        self.assertEqual(small, large)
