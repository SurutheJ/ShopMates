import importlib
import os
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from deals import services
from deals.tests.helpers import DealTestCase


class SecurityHeaderTests(TestCase):
    def test_csp_is_enforced_and_scripts_must_be_from_this_site(self):
        response = self.client.get('/')
        self.assertNotIn('Content-Security-Policy-Report-Only', response)
        policy = response['Content-Security-Policy']
        for part in ("default-src 'self'", "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'"):
            self.assertIn(part, policy)
        script_src = [p for p in policy.split('; ') if p.startswith('script-src')][0]
        self.assertEqual(script_src, "script-src 'self'")   # no 'unsafe-inline', no 'unsafe-eval'

    def test_forms_may_be_sent_on_to_google_sign_in(self):
        # The Google button posts to this site, which redirects to Google. Browsers check that
        # redirect against form-action, so Google must be allowed there or the click does nothing.
        policy = self.client.get('/')['Content-Security-Policy']
        form_action = [p for p in policy.split('; ') if p.startswith('form-action')][0]
        self.assertEqual(form_action, "form-action 'self' https://accounts.google.com")

    def test_csp_header_is_on_error_pages_too(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('Content-Security-Policy', response)


class NoInlineScriptTests(DealTestCase):
    """An enforced CSP blocks inline scripts, so no page may rely on one."""
    INLINE_SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>', re.I)

    def assert_no_inline_script(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        self.assertIsNone(self.INLINE_SCRIPT.search(response.content.decode()), f'inline <script> on {url}')
        return response.content.decode()

    def test_public_pages(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        for url in (reverse('home'), reverse('deals:stats'), reverse('account_login'), reverse('account_signup'),
                    reverse('deals:voucher_start', args=[deal.proposer_token]),
                    reverse('deals:voucher_show', args=[voucher.code])):
            self.assert_no_inline_script(url)

    def test_signed_in_pages_including_the_two_that_had_scripts(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        for url in (reverse('deals:inbox'), reverse('accounts:discover'), self.books.get_absolute_url(),
                    deal.get_absolute_url(), reverse('deals:summary', args=[deal.pk]), reverse('deals:playbook'),
                    reverse('deals:redeem'), reverse('accounts:shop_edit'), reverse('accounts:shop_staff'),
                    reverse('deals:new', args=[self.books.pk])):
            self.assert_no_inline_script(url)

    def test_the_buttons_carry_what_app_js_needs(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        form = self.assert_no_inline_script(reverse('deals:new', args=[self.books.pk]))
        self.assertIn(f'data-url="{reverse("deals:ai_draft")}"', form)
        self.assertIn(f'data-recipient="{self.books.pk}"', form)
        summary = self.assert_no_inline_script(reverse('deals:summary', args=[deal.pk]))
        self.assertRegex(summary, r'id="coach-btn"[^>]*data-csrf="[^"]+"')


class ProductionSettingsTests(SimpleTestCase):
    def load_prod(self):
        with mock.patch.dict(os.environ, {'ALLOWED_HOSTS': 'shop.example.com'}):
            return importlib.import_module('shopmates_project.settings.prod')

    def test_hsts_is_on_with_a_short_start_value(self):
        prod = self.load_prod()
        self.assertEqual(prod.SECURE_HSTS_SECONDS, 3600)
        self.assertFalse(prod.SECURE_HSTS_PRELOAD)

    def test_framing_and_referrer_are_locked_down(self):
        prod = self.load_prod()
        self.assertEqual(prod.X_FRAME_OPTIONS, 'DENY')
        self.assertEqual(prod.SECURE_REFERRER_POLICY, 'same-origin')
        self.assertTrue(prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE)
