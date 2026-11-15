from datetime import timedelta

from django.utils import timezone

from accounts.models import ShopMembership
from deals import services
from deals.models import Deal
from deals.services import DealError

from .helpers import DealTestCase, make_shop, make_terms, make_user

S = Deal.Status


class NegotiationTests(DealTestCase):
    def test_send_moves_draft_to_proposed_and_gives_the_turn_to_the_recipient(self):
        deal = services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms())
        self.assertEqual(deal.status, S.DRAFT)
        services.send_proposal(deal, self.cafe_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.PROPOSED)
        self.assertEqual(deal.turn_id, self.books.pk)
        self.assertIsNotNone(deal.response_deadline)

    def test_proposer_cannot_accept_their_own_proposal(self):
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.accept(deal, self.cafe_owner)

    def test_recipient_accepting_starts_the_deal_when_the_start_date_is_today(self):
        deal = self.proposed_deal()
        services.accept(deal, self.books_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACTIVE)

    def test_future_start_stays_accepted_until_that_day(self):
        start = timezone.localdate() + timedelta(days=3)
        deal = self.proposed_deal(start_date=start, end_date=start + timedelta(days=10))
        services.accept(deal, self.books_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACCEPTED)
        services.sync_status(deal, now=timezone.now() + timedelta(days=3, hours=1))
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACTIVE)

    def test_counter_creates_a_new_version_and_flips_the_turn(self):
        deal = self.proposed_deal()
        services.counter(deal, self.books_owner, make_terms(discount_percent=15, redemption_cap=8))
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.COUNTERED)
        self.assertEqual(deal.turn_id, self.cafe.pk)
        self.assertEqual(deal.versions.count(), 2)
        self.assertEqual(deal.current_version.discount_percent, 15)
        # the first version is kept unchanged
        self.assertEqual(deal.versions.get(number=1).discount_percent, 10)

    def test_original_proposer_can_accept_a_counter_and_it_uses_the_latest_terms(self):
        deal = self.proposed_deal()
        services.counter(deal, self.books_owner, make_terms(discount_percent=15))
        services.accept(deal, self.cafe_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACTIVE)
        self.assertEqual(deal.current_version.discount_percent, 15)

    def test_only_the_shop_whose_turn_it_is_can_counter(self):
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.counter(deal, self.cafe_owner, make_terms())

    def test_decline_closes_the_deal(self):
        deal = self.proposed_deal()
        services.decline(deal, self.books_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.DECLINED)
        self.assertIsNone(deal.turn)

    def test_only_the_proposer_can_withdraw_and_only_while_open(self):
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.withdraw(deal, self.books_owner)
        services.withdraw(deal, self.cafe_owner)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.WITHDRAWN)

    def test_cannot_withdraw_an_accepted_deal(self):
        deal = self.active_deal()
        with self.assertRaises(DealError):
            services.withdraw(deal, self.cafe_owner)

    def test_staff_cannot_negotiate(self):
        staff = make_user('books_staff')
        ShopMembership.objects.create(user=staff, shop=self.books, role=ShopMembership.Role.STAFF)
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.accept(deal, staff)

    def test_an_unrelated_shop_owner_cannot_act(self):
        other = make_user('other_owner')
        make_shop('Elsewhere', other)
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.decline(deal, other)

    def test_only_the_proposing_owner_can_start_a_deal(self):
        with self.assertRaises(DealError):
            services.create_draft(self.cafe, self.books, self.books_owner, make_terms())

    def test_a_pair_of_shops_cannot_have_two_live_deals(self):
        self.proposed_deal()
        with self.assertRaises(DealError):
            services.create_draft(self.books, self.cafe, self.books_owner, make_terms())

    def test_unapproved_shops_cannot_make_deals(self):
        pending_owner = make_user('pending_owner')
        pending = make_shop('Pending', pending_owner, status='pending')
        with self.assertRaises(DealError):
            services.create_draft(pending, self.books, pending_owner, make_terms())

    def test_cannot_accept_terms_that_already_ended(self):
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.accept(deal, self.books_owner, today=timezone.localdate() + timedelta(days=60))

    def test_every_transition_is_recorded(self):
        deal = self.proposed_deal()
        services.accept(deal, self.books_owner)
        actions = list(deal.events.values_list('action', flat=True))
        self.assertEqual(actions[:3], ['created', 'sent', 'accepted'])


class TimeTransitionTests(DealTestCase):
    def test_unanswered_proposals_expire(self):
        deal = self.proposed_deal()
        Deal.objects.filter(pk=deal.pk).update(response_deadline=timezone.now() - timedelta(hours=1))
        deal.refresh_from_db()
        services.sync_status(deal)
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.EXPIRED)
        with self.assertRaises(DealError):
            services.accept(deal, self.books_owner)

    def test_deal_completes_after_the_end_date(self):
        deal = self.active_deal()
        services.sync_status(deal, now=timezone.now() + timedelta(days=45))
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.COMPLETED)

    def test_deal_completes_when_both_shops_reach_their_cap(self):
        deal = self.active_deal(redemption_cap=1)
        self.redeem_once(deal, self.cafe, self.books_owner)   # honored at books
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.ACTIVE)               # cafe has not honored any yet
        self.redeem_once(deal, self.books, self.cafe_owner)   # honored at cafe
        deal.refresh_from_db()
        self.assertEqual(deal.status, S.COMPLETED)
