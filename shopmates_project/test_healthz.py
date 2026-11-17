from unittest.mock import patch

from django.test import TestCase


class HealthzTests(TestCase):
    def test_it_answers_ok_without_a_login(self):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_a_database_failure_gives_503_and_no_detail(self):
        with patch('shopmates_project.health.connection.cursor', side_effect=RuntimeError('db path /private/x')):
            with self.assertLogs('django', level='ERROR'):
                response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'error'})
        self.assertNotIn('private', response.content.decode())
