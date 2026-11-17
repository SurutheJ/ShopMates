"""Public, error, voucher, stats, summary and counter-card pages in the designv2 layout (no .legacy wrapper)."""
import re
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Shop
from accounts.test_public_screens import PortedScreenMixin, visible_scrolls
from deals import services
from deals.tests.helpers import DealTestCase, make_shop, make_user


class VoucherScreenTests(PortedScreenMixin, DealTestCase):
    def start_url(self, deal):
        return reverse('deals:voucher_start', args=[deal.proposer_token])

    def test_start_page_has_the_shop_name_and_a_pinned_get_my_code_button(self):
        deal = self.active_deal()
        html = self.page(self.start_url(deal))
        self.assert_ported(html)
        self.assertIn('class="app bare"', html)
        self.assertIn(f'<h1>{self.books.name}</h1>', html)
        self.assertIn('<button class="btn block big" type="submit" form="voucher-form">Get my code</button>', html)
        self.assertIn('id="voucher-form"', html)

    def test_start_page_for_a_deal_that_is_not_running_is_an_empty_state_without_the_button(self):
        deal = self.proposed_deal()
        html = self.page(self.start_url(deal))
        self.assert_ported(html)
        self.assertIn('class="empty"', html)
        self.assertNotIn('Get my code', html)

    def test_ready_code_is_shown_large_with_the_offer(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        html = self.page(reverse('deals:voucher_show', args=[voucher.code]))
        self.assert_ported(html)
        self.assertIn('class="code"', html)
        self.assertIn(voucher.code, html)
        self.assertIn(f'<h1>', html)
        self.assertIn(self.books.name, html)

    def test_used_code_is_an_already_used_empty_state(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        services.redeem_voucher(voucher.code, self.books_owner)
        html = self.page(reverse('deals:voucher_show', args=[voucher.code]))
        self.assert_ported(html)
        self.assertIn('Already used', html)
        self.assertNotIn('class="code"', html)

    def test_expired_code_is_an_expired_empty_state(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        voucher.expires_at = timezone.now() - timedelta(minutes=1)
        voucher.save()
        html = self.page(reverse('deals:voucher_show', args=[voucher.code]))
        self.assert_ported(html)
        self.assertIn('This code expired', html)
        self.assertNotIn('class="code"', html)


class PendingAndErrorScreenTests(PortedScreenMixin, TestCase):
    def test_pending_page_is_an_empty_state_with_a_clock(self):
        owner = make_user('newbie')
        make_shop('Newcomer', owner, status=Shop.Status.PENDING)
        self.client.force_login(owner)
        response = self.client.get(reverse('deals:playbook'))
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assert_ported(html)
        self.assertIn('Waiting for approval', html)
        self.assertIn('#i-clock', html)

    def test_suspended_page_says_suspended(self):
        owner = make_user('banned')
        make_shop('Oops', owner, status=Shop.Status.SUSPENDED)
        self.client.force_login(owner)
        html = self.client.get(reverse('deals:playbook')).content.decode()
        self.assert_ported(html)
        self.assertIn('was suspended', html)

    def test_404_is_an_empty_state_with_a_go_home_button(self):
        response = self.client.get('/no-such-page/')
        html = response.content.decode()
        self.assertEqual(response.status_code, 404)
        self.assert_ported(html)
        self.assertIn('class="empty"', html)
        self.assertIn(f'<a class="btn" href="{reverse("home")}">Go home</a>', html)

    def test_csrf_failure_page_is_ported(self):
        response = Client(enforce_csrf_checks=True).post(reverse('account_login'), {'login': 'x', 'password': 'y'})
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assert_ported(html)
        self.assertIn('reload', html)

    def test_forbidden_page_for_another_shops_deal_is_ported(self):
        owner = make_user('solo')
        make_shop('Solo', owner)
        self.client.force_login(owner)
        response = self.client.get(reverse('accounts:shop_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)
        self.assert_ported(response.content.decode())

    def test_500_page_uses_the_design_colours_and_still_needs_no_static_files(self):
        from django.template.loader import get_template
        source = get_template('500.html').template.source
        self.assertIn('#1A1410', source)
        self.assertNotIn('#0f766e', source)
        self.assertNotIn('{% static', source)


class StatsScreenTests(PortedScreenMixin, DealTestCase):
    def test_totals_are_design_stat_tiles_in_a_ported_screen(self):
        self.active_deal()
        html = self.page(reverse('deals:stats'))
        self.assert_ported(html)
        self.assertEqual(len(re.findall(r'<div class="stat[ "]', html)), 3)


class LandingScreenTests(PortedScreenMixin, TestCase):
    def test_landing_is_a_ported_screen_with_steps_and_pinned_buttons(self):
        html = self.page(reverse('home'))
        self.assert_ported(html)
        self.assertIn('<ol class="steps">', html)
        self.assertEqual(html.count('<li>'), 4)
        bar = re.search(r'<div class="actionbar">(.*?)</div>', html, re.S).group(1)
        self.assertIn(reverse('account_login'), bar)
        self.assertIn(reverse('account_signup'), bar)

    def test_signed_in_user_without_a_shop_gets_set_up_your_shop(self):
        self.client.force_login(make_user('fresh'))
        html = self.page(reverse('home'))
        self.assertIn(reverse('accounts:shop_create'), html)
        self.assertNotIn(reverse('account_signup'), re.search(r'<main.*?</main>', html, re.S).group(0))


class SummaryAndCardScreenTests(DealTestCase):
    def test_summary_is_a_native_screen_with_a_back_link_table_and_coach(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:summary', args=[deal.pk])).content.decode()
        self.assertNotIn('class="legacy"', html)
        self.assertEqual(len(visible_scrolls(html)), 1)
        self.assertIn('class="btn back"', html)
        self.assertIn('class="tbl"', html)
        for ident in ('coach-btn', 'coach-status', 'coach-out', 'coach-text', 'coach-source'):
            self.assertIn(f'id="{ident}"', html)
        self.assertIn('Download CSV', html)
        self.assertIn('<div class="actionbar">', html)
        self.assertEqual(len(re.findall(r'<h1[ >]', html)), 1)

    def test_counter_card_carries_the_logo_and_no_v1_colours(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:card', args=[deal.pk])).content.decode()
        self.assertEqual(html.count('class="cc-logo"'), 2)
        from django.contrib.staticfiles import finders
        css = open(finders.find('css/card.css')).read()
        self.assertIn('var(--coral)', css)
