from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.models import Shop, ShopMembership
from deals import services

User = get_user_model()
TEST_PASSWORD = 'test-pass-12345'


def make_user(username):
    return User.objects.create_user(username, f'{username}@example.com', TEST_PASSWORD)


def make_shop(name, owner=None, category='cafe', status=Shop.Status.APPROVED, order_value=10, **extra):
    shop = Shop.objects.create(name=name, category=category, address=f'1 {name} St',
                               typical_order_value=order_value, status=status, **extra)
    if owner is not None:
        ShopMembership.objects.create(user=owner, shop=shop, role=ShopMembership.Role.OWNER)
    return shop


def make_terms(**overrides):
    today = timezone.localdate()
    terms = {
        'offer_text': '10% off one purchase',
        'discount_percent': 10,
        'redemption_cap': 5,
        'start_date': today,
        'end_date': today + timedelta(days=30),
        'terms': '',
    }
    terms.update(overrides)
    return terms


class DealTestCase(TestCase):
    """Two approved shops (cafe, books) with owners, plus helpers to put them in a deal."""

    def setUp(self):
        cache.clear()
        self.cafe_owner = make_user('cafe_owner')
        self.books_owner = make_user('books_owner')
        self.cafe = make_shop('Green Cafe', self.cafe_owner, category='cafe', order_value=10)
        self.books = make_shop('Pageturner', self.books_owner, category='bookstore', order_value=20)

    def proposed_deal(self, **term_overrides):
        return services.create_draft(self.cafe, self.books, self.cafe_owner,
                                     make_terms(**term_overrides), send=True)

    def active_deal(self, **term_overrides):
        deal = self.proposed_deal(**term_overrides)
        services.accept(deal, self.books_owner)
        deal.refresh_from_db()
        return deal

    def redeem_once(self, deal, referring, honoring_user):
        voucher = services.issue_voucher(deal, referring)
        return services.redeem_voucher(voucher.code, honoring_user)
