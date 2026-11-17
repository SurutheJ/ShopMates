from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from .helpers import DealTestCase


@override_settings(AI_API_KEY='')
class AiDraftViewTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cafe_owner)
        self.url = reverse('deals:ai_draft')

    def test_without_a_key_the_view_returns_a_valid_fallback_draft(self):
        response = self.client.post(self.url, {'recipient_id': self.books.pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['source'], 'fallback')
        self.assertEqual(data['terms']['discount_percent'], 10)
        self.assertIn('Pageturner', data['message'])

    def test_requires_login_and_post(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'recipient_id': self.books.pk}).status_code, 302)
        self.client.force_login(self.cafe_owner)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_rejects_a_missing_or_own_recipient(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'recipient_id': self.cafe.pk}).status_code, 400)

    def test_calls_are_rate_limited_per_user(self):
        cache.clear()
        with override_settings(AI_DRAFT_LIMIT_PER_HOUR=2):
            statuses = [self.client.post(self.url, {'recipient_id': self.books.pk}).status_code for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])
