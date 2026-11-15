from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import ShopMembership
from deals import services
from deals.models import Deal, Redemption
from deals.services import DealError, RedeemError

from .helpers import DealTestCase, make_shop, make_terms, make_user

S = Deal.Status


class RedemptionRuleTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = self.active_deal(redemption_cap=2)

    def test_a_customer_of_the_cafe_gets_a_voucher_for_the_bookstore(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        self.assertEqual(voucher.referring_shop, self.cafe)
        self.assertEqual(voucher.honoring_shop, self.books)
        self.assertEqual(len(voucher.code), services.CODE_LENGTH)

    def test_codes_avoid_look_alike_characters(self):
        for _ in range(30):
            code = services.issue_voucher(self.deal, self.cafe).code
            self.assertFalse(set(code) & set('01OIL'))

    def test_bookstore_staff_can_redeem_once(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        redemption = services.redeem_voucher(voucher.code, self.books_owner)
        self.assertEqual(redemption.confirmed_by, self.books_owner)

    def test_second_redemption_of_the_same_code_is_rejected(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        services.redeem_voucher(voucher.code, self.books_owner)
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher(voucher.code, self.books_owner)
        self.assertEqual(ctx.exception.reason, 'already_used')
        self.assertEqual(Redemption.objects.count(), 1)

    def test_the_database_itself_refuses_a_double_redemption(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        Redemption.objects.create(voucher=voucher, confirmed_by=self.books_owner)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Redemption.objects.create(voucher=voucher, confirmed_by=self.books_owner)

    def test_the_referring_shop_cannot_redeem_its_own_customers_code(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher(voucher.code, self.cafe_owner)
        self.assertEqual(ctx.exception.reason, 'wrong_shop')
        self.assertEqual(Redemption.objects.count(), 0)

    def test_staff_of_the_honoring_shop_can_redeem(self):
        staff = make_user('books_staff')
        ShopMembership.objects.create(user=staff, shop=self.books, role=ShopMembership.Role.STAFF)
        voucher = services.issue_voucher(self.deal, self.cafe)
        services.redeem_voucher(voucher.code, staff)
        self.assertEqual(Redemption.objects.get().confirmed_by, staff)

    def test_unknown_code(self):
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher('NOPE1234', self.books_owner)
        self.assertEqual(ctx.exception.reason, 'not_found')

    def test_codes_are_normalized(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        messy = f' {voucher.code[:4].lower()}-{voucher.code[4:].lower()} '
        services.redeem_voucher(messy, self.books_owner)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_expired_voucher_is_rejected(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        voucher.expires_at = timezone.now() - timedelta(minutes=1)
        voucher.save()
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher(voucher.code, self.books_owner)
        self.assertEqual(ctx.exception.reason, 'expired')

    def test_cap_is_enforced_per_honoring_shop(self):
        v1 = services.issue_voucher(self.deal, self.cafe)
        v2 = services.issue_voucher(self.deal, self.cafe)
        v3 = services.issue_voucher(self.deal, self.cafe)
        services.redeem_voucher(v1.code, self.books_owner)
        services.redeem_voucher(v2.code, self.books_owner)
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher(v3.code, self.books_owner)
        self.assertEqual(ctx.exception.reason, 'cap_reached')
        # the cafe's own cap is separate and still open
        services.redeem_voucher(services.issue_voucher(self.deal, self.books).code, self.cafe_owner)

    def test_no_new_vouchers_once_the_cap_is_reached(self):
        for _ in range(2):
            services.redeem_voucher(services.issue_voucher(self.deal, self.cafe).code, self.books_owner)
        with self.assertRaises(DealError):
            services.issue_voucher(self.deal, self.cafe)

    def test_cannot_redeem_when_the_deal_is_not_active(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        Deal.objects.filter(pk=self.deal.pk).update(status=S.WITHDRAWN)
        with self.assertRaises(RedeemError) as ctx:
            services.redeem_voucher(voucher.code, self.books_owner)
        self.assertEqual(ctx.exception.reason, 'not_active')

    def test_no_vouchers_before_the_deal_starts(self):
        first_owner, second_owner = make_user('early_owner'), make_user('early_partner')
        first = make_shop('Early Cafe', first_owner)
        second = make_shop('Early Books', second_owner, category='bookstore')
        start = timezone.localdate() + timedelta(days=5)
        deal = services.create_draft(
            first, second, first_owner,
            make_terms(start_date=start, end_date=start + timedelta(days=9)), send=True)
        services.accept(deal, second_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACCEPTED)
        with self.assertRaises(DealError):
            services.issue_voucher(deal, first)


class SummaryTests(DealTestCase):
    def test_counts_and_estimated_cost(self):
        deal = self.active_deal(redemption_cap=10, discount_percent=10)
        for _ in range(3):
            self.redeem_once(deal, self.cafe, self.books_owner)    # cafe sent 3, books honored 3
        self.redeem_once(deal, self.books, self.cafe_owner)         # books sent 1, cafe honored 1
        summary = services.summary(deal)
        cafe_side, books_side = summary['sides']
        self.assertEqual((cafe_side['sent'], cafe_side['received']), (3, 1))
        self.assertEqual((books_side['sent'], books_side['received']), (1, 3))
        self.assertAlmostEqual(books_side['cost'], 3 * 0.10 * 20)   # 3 x 10% x $20
        self.assertAlmostEqual(cafe_side['cost'], 1 * 0.10 * 10)

    def test_a_lopsided_deal_suggests_a_renewal(self):
        deal = self.active_deal(redemption_cap=10)
        for _ in range(4):
            self.redeem_once(deal, self.cafe, self.books_owner)
        summary = services.summary(deal)
        self.assertTrue(summary['lopsided'])
        self.assertIn(self.cafe.name, summary['suggestion'])

    def test_a_balanced_deal_is_not_flagged(self):
        deal = self.active_deal(redemption_cap=10)
        for _ in range(2):
            self.redeem_once(deal, self.cafe, self.books_owner)
            self.redeem_once(deal, self.books, self.cafe_owner)
        self.assertFalse(services.summary(deal)['lopsided'])

    def test_too_few_redemptions_are_never_called_lopsided(self):
        deal = self.active_deal(redemption_cap=10)
        self.redeem_once(deal, self.cafe, self.books_owner)
        self.assertFalse(services.summary(deal)['lopsided'])
