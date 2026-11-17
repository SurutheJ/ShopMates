from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from deals.tests.helpers import DealTestCase
from shopmates_project.links import absolute_url


class AbsoluteUrlTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/', HTTP_HOST='localhost:8000')

    @override_settings(SITE_URL='')
    def test_without_site_url_the_request_host_is_used(self):
        self.assertEqual(absolute_url(self.request, '/v/abc/'), 'http://localhost:8000/v/abc/')

    @override_settings(SITE_URL='https://shop.example.com')
    def test_site_url_wins_over_the_request_host(self):
        self.assertEqual(absolute_url(self.request, '/v/abc/'), 'https://shop.example.com/v/abc/')

    @override_settings(SITE_URL='https://shop.example.com/')
    def test_a_trailing_slash_on_site_url_is_fine(self):
        self.assertEqual(absolute_url(self.request, '/v/abc/'), 'https://shop.example.com/v/abc/')


@override_settings(SITE_URL='https://shop.example.com')
class SiteUrlInPagesTests(DealTestCase):
    def test_qr_link_uses_site_url(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        response = self.client.get(reverse('deals:summary', args=[deal.pk]))
        self.assertEqual(response.context['qr_url'],
                         f'https://shop.example.com/v/{deal.proposer_token}/')

    def test_api_401_login_url_uses_site_url(self):
        response = self.client.get(reverse('deals:api_deals'))
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()['login_url'].startswith('https://shop.example.com/'))
