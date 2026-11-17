"""Staff can see their shop's pending deals in the inbox, but only an owner can act on them."""
from django.urls import reverse

from accounts.models import ShopMembership
from deals.models import Deal

from .helpers import DealTestCase, make_shop, make_terms, make_user
from deals import services


class StaffInboxTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user('books_staff')
        ShopMembership.objects.create(user=self.staff, shop=self.books, role=ShopMembership.Role.STAFF)
        self.client.force_login(self.staff)

    def inbox(self):
        response = self.client.get(reverse('deals:inbox'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_staff_see_the_partner_and_offer_of_a_pending_deal(self):
        self.proposed_deal()                       # cafe proposed to books; books must answer
        html = self.inbox()
        self.assertIn('Green Cafe', html)
        self.assertIn('Pending deals', html)

    def test_pending_deal_row_is_not_a_link_and_has_no_approve_control(self):
        deal = self.proposed_deal()
        html = self.inbox()
        self.assertNotIn(deal.get_absolute_url(), html)
        self.assertNotIn(reverse('deals:action', args=[deal.pk, 'accept']), html)
        self.assertIn('Only the shop owner can approve', html)

    def test_staff_still_cannot_open_or_accept_the_deal(self):
        deal = self.proposed_deal()
        self.assertEqual(self.client.get(deal.get_absolute_url()).status_code, 403)
        response = self.client.post(reverse('deals:action', args=[deal.pk, 'accept']))
        self.assertEqual(response.status_code, 403)
        deal.refresh_from_db()
        self.assertEqual(deal.status, Deal.Status.PROPOSED)

    def test_only_pending_deals_are_listed_not_running_ones(self):
        self.active_deal()                         # accepted by the books owner, so not pending
        self.assertNotIn('Green Cafe', self.inbox())

    def test_staff_of_another_shop_do_not_see_the_deal(self):
        self.proposed_deal()
        owner = make_user('third_owner')
        third = make_shop('Third', owner, category='bakery')
        other_staff = make_user('third_staff')
        ShopMembership.objects.create(user=other_staff, shop=third, role=ShopMembership.Role.STAFF)
        self.client.force_login(other_staff)
        html = self.inbox()
        self.assertNotIn('Green Cafe', html)
        self.assertNotIn('Pageturner', html)

    def test_owner_inbox_still_links_to_the_deal(self):
        deal = self.proposed_deal()
        self.client.force_login(self.books_owner)
        self.assertIn(deal.get_absolute_url(), self.inbox())
