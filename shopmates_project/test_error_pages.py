from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse

from deals.tests.helpers import make_shop, make_user


class ErrorPageTests(TestCase):
    def test_404_uses_our_page_and_links_home(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertContains(response, f'href="{reverse("home")}"', status_code=404)

    def test_404_works_for_a_logged_in_user(self):
        owner = make_user('owner')
        make_shop('Cafe', owner)
        self.client.force_login(owner)
        self.assertEqual(self.client.get('/no-such-page/').status_code, 404)
        self.assertTemplateUsed(self.client.get('/no-such-page/'), '404.html')

    def test_500_uses_our_page_and_leaks_nothing(self):
        client = Client(raise_request_exception=False)
        with mock.patch('deals.views.public_stats', side_effect=RuntimeError('secret db detail')):
            response = client.get(reverse('deals:stats'))
        self.assertEqual(response.status_code, 500)
        self.assertTemplateUsed(response, '500.html')
        self.assertContains(response, 'Something went wrong', status_code=500)
        self.assertNotContains(response, 'secret db detail', status_code=500)
        self.assertNotContains(response, 'Traceback', status_code=500)

    def test_500_page_does_not_depend_on_static_files_or_the_database(self):
        from django.template.loader import get_template
        source = get_template('500.html').template.source
        self.assertNotIn('{% static', source)
        self.assertNotIn('{% extends', source)
        self.assertNotIn('{% url', source)  # url reversing is fine in theory, but keep the page inert

    def test_403_uses_our_page(self):
        from django.core.exceptions import PermissionDenied
        with mock.patch('deals.views.public_stats', side_effect=PermissionDenied):
            response = self.client.get(reverse('deals:stats'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')
        self.assertContains(response, 'Not allowed', status_code=403)

    def test_csrf_failure_explains_what_to_do(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('account_login'), {'login': 'x', 'password': 'y'})
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403_csrf.html')
        self.assertContains(response, 'reload', status_code=403)
