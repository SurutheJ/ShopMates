"""An unsent draft is private to the shop that wrote it. The other shop sees nothing until it is sent."""
from django.urls import reverse

from deals import services

from .helpers import DealTestCase, make_terms


class DraftPrivacyTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms())

    def test_the_other_shop_cannot_open_the_draft_or_anything_on_it(self):
        self.client.force_login(self.books_owner)
        for name in ('detail', 'summary', 'counter', 'export_csv', 'export_json'):
            self.assertEqual(self.client.get(reverse(f'deals:{name}', args=[self.deal.pk])).status_code, 404, name)
        self.assertEqual(self.client.get(reverse('deals:api_redemptions', args=[self.deal.pk])).status_code, 404)

    def test_the_inbox_and_the_api_list_do_not_show_it_to_the_other_shop(self):
        self.client.force_login(self.books_owner)
        inbox = self.client.get(reverse('deals:inbox'))
        self.assertNotContains(inbox, 'Green Cafe')
        self.assertEqual(self.client.get(reverse('deals:api_deals')).json()['results'], [])

    def test_the_proposer_still_sees_it_everywhere(self):
        self.client.force_login(self.cafe_owner)
        self.assertEqual(self.client.get(self.deal.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get(reverse('deals:inbox')), 'Pageturner')
        self.assertEqual(len(self.client.get(reverse('deals:api_deals')).json()['results']), 1)

    def test_it_appears_for_the_other_shop_once_sent(self):
        services.send_proposal(self.deal, self.cafe_owner)
        self.client.force_login(self.books_owner)
        self.assertEqual(self.client.get(self.deal.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get(reverse('deals:inbox')), 'Green Cafe')
        self.assertEqual(len(self.client.get(reverse('deals:api_deals')).json()['results']), 1)
