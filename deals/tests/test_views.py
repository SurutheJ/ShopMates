import csv
import io
import json

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from accounts.models import Shop, ShopMembership
from deals import services
from deals.models import Deal, Redemption, Voucher

from .helpers import DealTestCase, TEST_PASSWORD, make_shop, make_terms, make_user


class PublicPageTests(DealTestCase):
    def test_public_pages_load_logged_out(self):
        for name in ('home', 'deals:stats', 'account_login', 'account_signup'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_private_pages_redirect_to_login(self):
        for name in ('deals:inbox', 'accounts:discover', 'deals:redeem'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/accounts/login/', response['Location'])

    def test_unknown_offer_token_is_a_404(self):
        self.assertEqual(self.client.get('/v/00000000-0000-0000-0000-000000000000/').status_code, 404)

    def test_navbar_shows_logged_in_links_only_when_logged_in(self):
        redeem_link = f'href="{reverse("deals:redeem")}"'
        inbox_link = f'href="{reverse("deals:inbox")}"'
        logged_out = self.client.get(reverse('home'))
        self.assertNotContains(logged_out, redeem_link)
        self.assertNotContains(logged_out, inbox_link)
        self.client.force_login(self.cafe_owner)
        logged_in = self.client.get(reverse('deals:inbox'))
        self.assertContains(logged_in, redeem_link)
        self.assertContains(logged_in, inbox_link)


class EndToEndFlowTests(DealTestCase):
    """The whole story through the real URLs: propose, accept, scan, redeem, summarize, export."""

    def test_full_flow(self):
        # The cafe owner proposes to the bookstore.
        self.client.force_login(self.cafe_owner)
        self.assertContains(self.client.get(reverse('accounts:discover')), 'Pageturner')
        form = {
            'offer_text': '10% off any book', 'discount_percent': 10, 'redemption_cap': 5,
            'start_date': make_terms()['start_date'].isoformat(),
            'end_date': make_terms()['end_date'].isoformat(),
            'terms': '', 'message': 'Hi neighbor!', 'action': 'send',
        }
        response = self.client.post(reverse('deals:new', args=[self.books.pk]), form)
        deal = Deal.objects.get()
        self.assertRedirects(response, deal.get_absolute_url())
        self.assertEqual(deal.status, Deal.Status.PROPOSED)
        self.assertEqual(deal.messages.count(), 1)

        # The bookstore owner sees it waiting, then accepts.
        self.client.force_login(self.books_owner)
        self.assertContains(self.client.get(reverse('deals:inbox')), 'Cafe')
        self.client.post(reverse('deals:action', args=[deal.pk, 'accept']))
        deal.refresh_from_db()
        self.assertEqual(deal.status, Deal.Status.ACTIVE)

        # A customer (no login) scans the cafe's QR and gets a code.
        self.client.logout()
        start_url = reverse('deals:voucher_start', args=[deal.proposer_token])
        self.assertContains(self.client.get(start_url), 'Get my code')
        response = self.client.post(start_url)
        voucher = Voucher.objects.get()
        self.assertRedirects(response, reverse('deals:voucher_show', args=[voucher.code]))
        self.assertContains(self.client.get(response['Location']), voucher.code)

        # The bookstore confirms it; a second try is rejected.
        self.client.force_login(self.books_owner)
        self.client.post(reverse('deals:redeem'), {'code': voucher.code})
        self.assertEqual(Redemption.objects.count(), 1)
        self.client.post(reverse('deals:redeem'), {'code': voucher.code})
        self.assertEqual(Redemption.objects.count(), 1)

        # Summary and exports.
        self.assertContains(self.client.get(reverse('deals:summary', args=[deal.pk])), 'Download CSV')
        csv_response = self.client.get(reverse('deals:export_csv', args=[deal.pk]))
        self.assertEqual(csv_response['Content-Type'], 'text/csv')
        self.assertRegex(csv_response['Content-Disposition'],
                         rf'attachment; filename="shopmates_deal-{deal.pk}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}\.csv"')
        rows = list(csv.reader(io.StringIO(csv_response.content.decode())))
        self.assertEqual(rows[0][:3], ['redemption_id', 'deal_id', 'referred_by'])
        self.assertEqual(len(rows), 2)

        json_response = self.client.get(reverse('deals:export_json', args=[deal.pk]))
        self.assertRegex(json_response['Content-Disposition'], r'\.json"$')
        self.assertTrue(json_response.content.decode().startswith('{\n  "generated_at"'))
        data = json.loads(json_response.content)
        self.assertEqual(data['record_count'], 1)


class AuthorizationTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = self.active_deal()
        self.outsider = make_user('outsider')
        make_shop('Outsider Shop', self.outsider, category='flowers')
        self.staff = make_user('books_staff')
        ShopMembership.objects.create(user=self.staff, shop=self.books, role=ShopMembership.Role.STAFF)

    def test_an_unrelated_shop_gets_404_everywhere_on_someone_elses_deal(self):
        self.client.force_login(self.outsider)
        for name in ('deals:detail', 'deals:summary', 'deals:export_csv', 'deals:export_json', 'deals:counter'):
            self.assertEqual(self.client.get(reverse(name, args=[self.deal.pk])).status_code, 404, name)
        response = self.client.post(reverse('deals:action', args=[self.deal.pk, 'decline']))
        self.assertEqual(response.status_code, 404)

    def test_staff_cannot_see_deals_or_exports(self):
        self.client.force_login(self.staff)
        for name in ('deals:detail', 'deals:summary', 'deals:export_csv'):
            self.assertEqual(self.client.get(reverse(name, args=[self.deal.pk])).status_code, 403, name)

    def test_staff_can_use_the_redeem_page_and_sees_a_redeem_inbox(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('deals:inbox')), 'Confirm a customer')
        self.client.post(reverse('deals:redeem'), {'code': voucher.code})
        self.assertEqual(Redemption.objects.get().confirmed_by, self.staff)

    def test_actions_require_post(self):
        self.client.force_login(self.books_owner)
        self.assertEqual(self.client.get(reverse('deals:action', args=[self.deal.pk, 'decline'])).status_code, 405)

    def test_unknown_action_is_a_404(self):
        self.client.force_login(self.books_owner)
        self.assertEqual(self.client.post(reverse('deals:action', args=[self.deal.pk, 'explode'])).status_code, 404)

    def test_pending_shop_cannot_redeem(self):
        owner = make_user('pending_owner')
        make_shop('Pending', owner, status=Shop.Status.PENDING)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(reverse('deals:redeem')).status_code, 403)

    def test_user_without_a_shop_is_sent_to_set_one_up(self):
        lonely = make_user('lonely')
        self.client.force_login(lonely)
        response = self.client.get(reverse('deals:inbox'))
        self.assertRedirects(response, reverse('accounts:shop_create'))


class CustomerFlowTests(DealTestCase):
    def test_voucher_page_for_an_inactive_deal_offers_nothing(self):
        deal = self.proposed_deal()
        response = self.client.get(reverse('deals:voucher_start', args=[deal.proposer_token]))
        self.assertNotContains(response, 'Get my code')

    def test_voucher_issuing_is_rate_limited_per_ip(self):
        deal = self.active_deal(redemption_cap=50)
        url = reverse('deals:voucher_start', args=[deal.proposer_token])
        with override_settings(VOUCHER_ISSUE_LIMIT_PER_HOUR=2):
            cache.clear()
            codes = [self.client.post(url).status_code for _ in range(3)]
        self.assertEqual(codes, [302, 302, 429])

    def test_used_voucher_page_says_so(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        services.redeem_voucher(voucher.code, self.books_owner)
        self.assertContains(self.client.get(reverse('deals:voucher_show', args=[voucher.code])), 'already used')

