from datetime import date

from django.conf import settings
from django.test import SimpleTestCase

from accounts.models import Shop
from ai.client import AIError
from ai.services import answer_playbook, draft_deal, explain_balance
from deals import services
from deals.tests.helpers import DealTestCase

TODAY = date(2026, 11, 15)
SECRET_WORDS = 'ZEBRA-PASSPHRASE-123'


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error

    def generate_json(self, prompt):
        if self.error:
            raise self.error
        return self.response


def shops():
    a = Shop(name=f'Cafe {SECRET_WORDS}', category='cafe', address='1 A St', typical_order_value=9)
    b = Shop(name='Books', category='bookstore', address='2 B St', typical_order_value=24)
    return a, b


class AIFallbackLoggingTests(SimpleTestCase):
    def test_draft_fallback_after_api_error_is_logged_with_reason(self):
        a, b = shops()
        with self.assertLogs('ai', 'WARNING') as logs:
            result = draft_deal(a, b, client=FakeClient(error=AIError('The AI service could not be reached (Timeout).')),
                                today=TODAY)
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(len(logs.records), 1)
        self.assertIn('draft', logs.output[0])
        self.assertIn('Timeout', logs.output[0])

    def test_rejected_model_output_is_logged(self):
        a, b = shops()
        with self.assertLogs('ai', 'WARNING') as logs:
            draft_deal(a, b, client=FakeClient({'offer_text': 'x'}), today=TODAY)
        self.assertIn('not valid', logs.output[0])

    def test_playbook_fallback_is_logged_without_the_question(self):
        with self.assertLogs('ai', 'WARNING') as logs:
            answer_playbook(f'bakery flowers {SECRET_WORDS}',
                            client=FakeClient({'answer': 'ok', 'used': ['made-up-id']}))
        self.assertIn('playbook', logs.output[0])
        self.assertNotIn(SECRET_WORDS, logs.output[0])

    def test_no_warning_when_ai_is_simply_not_configured(self):
        a, b = shops()
        with self.assertNoLogs('ai', 'WARNING'):
            draft_deal(a, b, client=None, today=TODAY)
            answer_playbook('bakery flowers', client=None)

    def test_logged_text_never_contains_shop_names(self):
        a, b = shops()
        with self.assertLogs('ai', 'WARNING') as logs:
            draft_deal(a, b, client=FakeClient(error=AIError('down')), today=TODAY)
        self.assertNotIn(SECRET_WORDS, ' '.join(logs.output))


class CoachLoggingTests(DealTestCase):
    def test_coach_fallback_is_logged(self):
        summary = services.summary(self.active_deal())
        with self.assertLogs('ai', 'WARNING') as logs:
            explain_balance(summary, client=FakeClient(error=AIError('down')))
        self.assertIn('coach', logs.output[0])


class LoggingConfigTests(SimpleTestCase):
    def test_ai_logger_writes_to_console_and_file(self):
        handlers = settings.LOGGING['loggers']['ai']['handlers']
        self.assertEqual(set(handlers), {'console', 'file'})

    def test_server_errors_reach_the_file_log(self):
        self.assertIn('file', settings.LOGGING['loggers']['django']['handlers'])
