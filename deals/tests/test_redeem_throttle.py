from django.test import override_settings
from django.urls import reverse

from deals import services
from deals.models import Redemption

from .helpers import DealTestCase


@override_settings(REDEEM_LIMIT_PER_HOUR=3)
class RedeemThrottleTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = self.active_deal()
        self.url = reverse('deals:redeem')

    def post_code(self, code):
        return self.client.post(self.url, {'code': code})

    def test_guessing_codes_is_stopped_after_the_limit(self):
        self.client.force_login(self.books_owner)
        for _ in range(3):
            self.assertEqual(self.post_code('AAAAAA').status_code, 302)
        blocked = self.post_code('AAAAAA')
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, 'Too many attempts', status_code=429)

    def test_a_valid_code_is_refused_once_blocked(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        self.client.force_login(self.books_owner)
        for _ in range(3):
            self.post_code('AAAAAA')
        self.assertEqual(self.post_code(voucher.code).status_code, 429)
        self.assertEqual(Redemption.objects.count(), 0)

    def test_the_limit_is_per_user_not_shared_between_shops(self):
        self.client.force_login(self.books_owner)
        for _ in range(4):
            self.post_code('AAAAAA')
        self.client.force_login(self.cafe_owner)
        self.assertEqual(self.post_code('AAAAAA').status_code, 302)

    def test_normal_use_under_the_limit_still_redeems(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        self.client.force_login(self.books_owner)
        self.assertEqual(self.post_code(voucher.code).status_code, 302)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_viewing_the_page_does_not_count(self):
        self.client.force_login(self.books_owner)
        for _ in range(6):
            self.assertEqual(self.client.get(self.url).status_code, 200)
