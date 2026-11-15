import json

from django.test import override_settings
from django.urls import reverse

from accounts.models import ShopMembership
from deals import services

from .helpers import DealTestCase, make_shop, make_terms, make_user


class PublicStatsApiTests(DealTestCase):
    def test_stats_is_public_json_with_cors(self):
        response = self.client.get(reverse('deals:api_stats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        self.assertEqual(response.json()['totals']['shops'], 2)

    def test_small_categories_are_hidden_by_default(self):
        data = self.client.get(reverse('deals:api_stats')).json()
        self.assertEqual(data['by_category'], [])
        self.assertEqual(data['hidden_categories'], 2)

    def test_a_category_appears_once_it_is_big_enough(self):
        make_shop('Second Cafe', make_user('c2'), category='cafe')
        with override_settings(STATS_MIN_GROUP=2):
            data = self.client.get(reverse('deals:api_stats')).json()
        self.assertEqual([g['category'] for g in data['by_category']], ['Cafe'])
        self.assertEqual(data['hidden_categories'], 1)

    def test_no_shop_names_or_codes_ever_leak(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        services.redeem_voucher(voucher.code, self.books_owner)
        make_shop('Second Cafe', make_user('c2'), category='cafe')
        with override_settings(STATS_MIN_GROUP=1):
            body = self.client.get(reverse('deals:api_stats')).content.decode()
        for secret in ('Green Cafe', 'Pageturner', 'Second Cafe', voucher.code, 'cafe_owner'):
            self.assertNotIn(secret, body)
        self.assertEqual(json.loads(body)['totals']['redemptions'], 1)


class ProtectedApiTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = self.active_deal()
        services.redeem_voucher(services.issue_voucher(self.deal, self.cafe).code, self.books_owner)
        self.outsider = make_user('outsider')
        make_shop('Outsider Shop', self.outsider, category='flowers')

    def test_logged_out_gets_401_json_not_a_redirect(self):
        for url in (reverse('deals:api_deals'), reverse('deals:api_redemptions', args=[self.deal.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 401, url)
            self.assertEqual(response['Content-Type'], 'application/json')
            self.assertIn('error', response.json())

    def test_owner_sees_only_their_own_deals(self):
        self.client.force_login(self.cafe_owner)
        data = self.client.get(reverse('deals:api_deals')).json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['partner'], 'Pageturner')
        self.assertEqual(data['results'][0]['redemptions_honored_here'], 0)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('deals:api_deals')).json()['count'], 0)

    def test_party_can_list_redemptions(self):
        self.client.force_login(self.books_owner)
        data = self.client.get(reverse('deals:api_redemptions', args=[self.deal.pk])).json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['referred_by'], 'Green Cafe')
        self.assertNotIn('code', data['results'][0])

    def test_non_party_gets_404_not_403(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('deals:api_redemptions', args=[self.deal.pk]))
        self.assertEqual(response.status_code, 404)
        missing = self.client.get(reverse('deals:api_redemptions', args=[99999]))
        self.assertEqual(missing.content, response.content)   # same answer as "does not exist"

    def test_staff_and_shopless_users_are_refused(self):
        staff = make_user('books_staff')
        ShopMembership.objects.create(user=staff, shop=self.books, role=ShopMembership.Role.STAFF)
        shopless = make_user('shopless')
        for user in (staff, shopless):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('deals:api_deals')).status_code, 403)
            self.assertEqual(self.client.get(reverse('deals:api_redemptions', args=[self.deal.pk])).status_code, 403)
