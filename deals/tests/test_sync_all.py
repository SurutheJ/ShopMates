from django.urls import reverse

from deals import services
from deals.models import Deal

from .helpers import DealTestCase


class SyncAllTests(DealTestCase):
    """sync_all counts redemptions for many deals at once; it must agree with sync_status."""

    def fill(self, deal, referring, honoring_user, times):
        for _ in range(times):
            self.redeem_once(deal, referring, honoring_user)

    def test_one_full_cap_keeps_the_deal_active(self):
        deal = self.active_deal(redemption_cap=2)
        self.fill(deal, self.cafe, self.books_owner, 2)  # books honored 2 of 2, cafe 0 of 2
        deal = Deal.objects.get(pk=deal.pk)
        services.sync_all([deal])
        self.assertEqual(deal.status, Deal.Status.ACTIVE)

    def test_both_full_caps_complete_the_deal(self):
        deal = self.active_deal(redemption_cap=2)
        self.fill(deal, self.cafe, self.books_owner, 2)
        self.fill(deal, self.books, self.cafe_owner, 2)
        deal = Deal.objects.get(pk=deal.pk)
        deal.status = Deal.Status.ACTIVE
        deal.save()
        services.sync_all([deal])
        self.assertEqual(deal.status, Deal.Status.COMPLETED)

    def test_counts_are_kept_apart_per_deal(self):
        """Two deals in one list: only the one with both caps full completes."""
        full = self.active_deal(redemption_cap=1)
        self.fill(full, self.cafe, self.books_owner, 1)
        self.fill(full, self.books, self.cafe_owner, 1)
        full.status = Deal.Status.ACTIVE
        full.save()
        other_owner = self.cafe_owner.__class__.objects.create_user('o3', 'o3@example.com', 'x-pass-12345')
        from .helpers import make_shop, make_terms
        third = make_shop('Third', other_owner, category='bakery')
        open_deal = services.create_draft(third, self.cafe, other_owner, make_terms(redemption_cap=1), send=True)
        services.accept(open_deal, self.cafe_owner)
        open_deal = Deal.objects.get(pk=open_deal.pk)
        full = Deal.objects.get(pk=full.pk)
        services.sync_all([full, open_deal])
        self.assertEqual(full.status, Deal.Status.COMPLETED)
        self.assertEqual(open_deal.status, Deal.Status.ACTIVE)

    def test_inbox_files_a_finished_deal_under_past(self):
        deal = self.active_deal(redemption_cap=1)
        self.fill(deal, self.cafe, self.books_owner, 1)
        self.fill(deal, self.books, self.cafe_owner, 1)
        self.client.force_login(self.cafe_owner)
        response = self.client.get(reverse('deals:inbox'))
        self.assertEqual([d.pk for d in response.context['past']], [deal.pk])
        self.assertEqual(response.context['running'], [])
