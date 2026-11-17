"""A draft can be edited by the proposing shop's owner until it is sent."""
from django.urls import reverse

from deals import services
from deals.models import Deal, DealMessage
from deals.services import DealError

from .helpers import DealTestCase, make_shop, make_terms, make_user


class EditDraftServiceTests(DealTestCase):
    def draft(self, **terms):
        return services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms(**terms))

    def test_the_proposer_changes_the_terms_in_place(self):
        deal = self.draft()
        services.edit_draft(deal, self.cafe_owner, make_terms(redemption_cap=40, offer_text='20% off a coffee'))
        self.assertEqual(deal.versions.count(), 1)          # never sent, so no new version
        version = deal.current_version
        self.assertEqual((version.redemption_cap, version.offer_text), (40, '20% off a coffee'))
        self.assertEqual(deal.status, Deal.Status.DRAFT)
        self.assertTrue(deal.events.filter(action='edited').exists())

    def test_only_a_draft_can_be_edited(self):
        deal = self.proposed_deal()
        with self.assertRaises(DealError):
            services.edit_draft(deal, self.cafe_owner, make_terms(redemption_cap=40))
        self.assertEqual(deal.current_version.redemption_cap, 5)

    def test_the_other_shop_and_non_owners_cannot_edit(self):
        deal = self.draft()
        staff = make_user('cafe_staff')
        from accounts.models import ShopMembership
        ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        for user in (self.books_owner, staff, make_user('outsider')):
            with self.assertRaises(DealError):
                services.edit_draft(deal, user, make_terms(redemption_cap=40))
        self.assertEqual(deal.current_version.redemption_cap, 5)


class EditDraftViewTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms(redemption_cap=7))
        self.url = reverse('deals:edit', args=[self.deal.pk])

    def post(self, action='save', **terms):
        data = {**{k: v for k, v in make_terms(**terms).items()}, 'action': action}
        return self.client.post(self.url, data)

    def test_the_form_opens_filled_with_the_draft(self):
        self.client.force_login(self.cafe_owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit draft')
        self.assertContains(response, 'value="7"')
        self.assertContains(response, 'value="save"')
        self.assertContains(response, 'value="send"')

    def test_saving_keeps_it_a_draft_with_the_new_terms(self):
        self.client.force_login(self.cafe_owner)
        response = self.post('save', redemption_cap=25)
        self.assertRedirects(response, self.deal.get_absolute_url())
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status, Deal.Status.DRAFT)
        self.assertEqual(self.deal.current_version.redemption_cap, 25)

    def test_sending_from_the_edit_form_sends_the_edited_terms(self):
        self.client.force_login(self.cafe_owner)
        self.post('send', redemption_cap=25)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status, Deal.Status.PROPOSED)
        self.assertEqual(self.deal.current_version.redemption_cap, 25)

    def test_invalid_terms_show_the_error_and_change_nothing(self):
        self.client.force_login(self.cafe_owner)
        response = self.post('save', redemption_cap=0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.deal.current_version.redemption_cap, 7)

    def test_the_note_is_prefilled_updated_and_removed_when_emptied(self):
        DealMessage.objects.create(deal=self.deal, author=self.cafe_owner, shop=self.cafe, body='first note')
        self.client.force_login(self.cafe_owner)
        self.assertContains(self.client.get(self.url), 'first note')
        self.client.post(self.url, {**make_terms(), 'action': 'save', 'message': 'second note'})
        self.assertEqual(list(self.deal.messages.values_list('body', flat=True)), ['second note'])
        self.client.post(self.url, {**make_terms(), 'action': 'save', 'message': ''})
        self.assertEqual(self.deal.messages.count(), 0)

    def test_a_sent_deal_cannot_be_edited_through_the_url(self):
        services.send_proposal(self.deal, self.cafe_owner)
        self.client.force_login(self.cafe_owner)
        response = self.post('save', redemption_cap=99)
        self.assertEqual(response.status_code, 302)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.current_version.redemption_cap, 7)

    def test_the_other_shop_and_outsiders_get_404(self):
        outsider = make_user('outsider')
        make_shop('Other Shop', outsider, category='bakery')
        for user in (self.books_owner, outsider):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.post('save', redemption_cap=99).status_code, 404)
        self.assertEqual(self.deal.current_version.redemption_cap, 7)

    def test_the_edit_button_shows_to_the_proposer_on_a_draft_only(self):
        self.client.force_login(self.cafe_owner)
        self.assertContains(self.client.get(self.deal.get_absolute_url()), self.url)
        services.send_proposal(self.deal, self.cafe_owner)
        self.assertNotContains(self.client.get(self.deal.get_absolute_url()), self.url)

    def test_the_other_shop_cannot_open_a_draft_that_was_not_sent(self):
        self.client.force_login(self.books_owner)
        self.assertEqual(self.client.get(self.deal.get_absolute_url()).status_code, 404)


class EditDraftNavTests(DealTestCase):
    def test_the_inbox_nav_item_is_lit_on_the_edit_page(self):
        deal = services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms())
        self.client.force_login(self.cafe_owner)
        response = self.client.get(reverse('deals:edit', args=[deal.pk]))
        self.assertEqual(response.context['nav_active'], 'inbox')
