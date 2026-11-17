"""Sign-in pages in the designv2 layout: login, sign up, log out, password reset, Google button."""
import re

from django.test import TestCase
from django.urls import reverse

from deals.tests.helpers import make_user


def visible_scrolls(html):
    return [tag for tag in re.findall(r'<div[^>]*class="scroll\b[^>]*>', html) if ' hidden' not in tag]


class PortedScreenMixin:
    """What every ported public page must have: narrow screen, one scroll, no .legacy wrapper, one h1."""

    def page(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response.content.decode()

    def assert_ported(self, html):
        self.assertNotIn('class="legacy"', html)
        self.assertIn('class="screen narrow active"', html)
        self.assertEqual(len(visible_scrolls(html)), 1)
        self.assertEqual(len(re.findall(r'<h1[ >]', html)), 1)


class LoginScreenTests(PortedScreenMixin, TestCase):
    def test_login_is_a_ported_screen_with_a_pinned_log_in_button(self):
        html = self.page(reverse('account_login'))
        self.assert_ported(html)
        self.assertIn('<h1>Welcome back</h1>', html)
        self.assertIn('<div class="actionbar">', html)
        self.assertRegex(html, r'<button class="btn block" type="submit" form="login-form">Log in</button>')
        self.assertIn('id="login-form"', html)

    def test_login_fields_use_the_input_class_and_forgot_password_links_to_reset(self):
        html = self.page(reverse('account_login'))
        for field_id in ('id_login', 'id_password'):
            self.assertRegex(html, rf'<input[^>]*class="input"[^>]*id="{field_id}"|<input[^>]*id="{field_id}"[^>]*class="input"')
        self.assertEqual(html.count(f'href="{reverse("account_reset_password")}"'), 1)   # allauth's own hint under the password
        self.assertIn(f'href="{reverse("account_signup")}', html)

    def test_the_first_field_is_labelled_username_or_email_as_in_the_design(self):
        html = self.page(reverse('account_login'))
        self.assertIn('<label for="id_login">Username or email</label>', html)

    def test_wrong_password_shows_a_banner_not_a_legacy_error_box(self):
        make_user('sam')
        response = self.client.post(reverse('account_login'), {'login': 'sam', 'password': 'nope'})
        html = response.content.decode()
        self.assertIn('class="banner bad" role="alert"', html)
        self.assertNotIn('error--box', html)


class SignupScreenTests(PortedScreenMixin, TestCase):
    def test_signup_is_a_ported_screen_with_a_pinned_button(self):
        html = self.page(reverse('account_signup'))
        self.assert_ported(html)
        self.assertIn('<h1>Create your account</h1>', html)
        self.assertRegex(html, r'<button class="btn block" type="submit" form="signup-form">Create account</button>')
        self.assertIn(f'href="{reverse("account_login")}', html)

    def test_signup_fields_use_the_input_class(self):
        html = self.page(reverse('account_signup'))
        for field_id in ('id_username', 'id_email', 'id_password1', 'id_password2'):
            self.assertRegex(html, rf'<input[^>]*class="input"[^>]*id="{field_id}"|<input[^>]*id="{field_id}"[^>]*class="input"')

    def test_terms_and_privacy_are_marked_coming_soon_because_no_such_pages_exist(self):
        html = self.page(reverse('account_signup'))
        self.assertIn('data-soon="Terms and Privacy"', html)

    def test_a_bad_signup_shows_the_field_error_in_the_design_style(self):
        make_user('taken')
        response = self.client.post(reverse('account_signup'), {
            'username': 'taken', 'email': 'a@example.com', 'password1': 'Xk29-plum-river', 'password2': 'Xk29-plum-river'})
        self.assertContains(response, 'class="err"')
        self.assertNotContains(response, 'class="error"')


class LogoutScreenTests(PortedScreenMixin, TestCase):
    def test_logout_is_a_ported_screen_with_a_pinned_button_and_a_cancel(self):
        self.client.force_login(make_user('lee'))
        html = self.page(reverse('account_logout'))
        self.assert_ported(html)
        self.assertIn('<button class="btn" type="submit" form="logout-form">Log out</button>', html)
        self.assertIn(f'href="{reverse("home")}"', html)


class PasswordResetScreenTests(PortedScreenMixin, TestCase):
    def test_reset_page_has_back_link_email_field_and_send_link_button(self):
        html = self.page(reverse('account_reset_password'))
        self.assert_ported(html)
        self.assertIn('<h1>Reset your password</h1>', html)
        self.assertIn('class="btn back"', html)
        self.assertIn(f'href="{reverse("account_login")}"', html)
        self.assertRegex(html, r'<input[^>]*type="email"[^>]*class="input"|<input[^>]*class="input"[^>]*type="email"')
        self.assertRegex(html, r'<button class="btn block" type="submit" form="reset-form">Send link</button>')

    def test_reset_does_not_promise_a_one_hour_link(self):
        self.assertNotIn('one hour', self.page(reverse('account_reset_password')))

    def test_reset_done_page_is_ported(self):
        response = self.client.post(reverse('account_reset_password'), {'email': 'nobody@example.com'}, follow=True)
        html = response.content.decode()
        self.assert_ported(html)
        self.assertIn('Check your email', html)

    def test_a_bad_reset_link_page_is_ported_and_offers_a_new_link(self):
        html = self.page(reverse('account_reset_password_from_key', args=['1', 'bad-key']))
        self.assert_ported(html)
        self.assertIn(reverse('account_reset_password'), html)


class PasswordChangeScreenTests(PortedScreenMixin, TestCase):
    def test_change_password_is_a_ported_screen_with_input_fields_and_a_pinned_button(self):
        self.client.force_login(make_user('pat'))
        html = self.page(reverse('account_change_password'))
        self.assert_ported(html)
        self.assertRegex(html, r'<button class="btn block" type="submit" form="change-form">Change password</button>')
        for field_id in ('id_oldpassword', 'id_password1', 'id_password2'):
            self.assertRegex(html, rf'<input[^>]*class="input"[^>]*id="{field_id}"|<input[^>]*id="{field_id}"[^>]*class="input"')


class GoogleButtonTests(TestCase):
    GOOGLE = {'google': {'APP': {'client_id': 'test-id', 'secret': 'test-secret', 'key': ''}}}

    def test_the_button_is_a_design_ghost_block_button_with_the_google_logo(self):
        with self.settings(SOCIALACCOUNT_PROVIDERS=self.GOOGLE):
            html = self.client.get(reverse('account_login')).content.decode()
        self.assertIn('class="btn ghost block"', html)
        self.assertIn('Continue with Google', html)
        self.assertNotIn('btn-google', html)
        self.assertIn('class="muted sm or"', html)

    def test_no_button_when_google_is_not_configured(self):
        with self.settings(SOCIALACCOUNT_PROVIDERS={}):
            html = self.client.get(reverse('account_login')).content.decode()
        self.assertNotIn('Continue with Google', html)
