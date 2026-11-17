"""Redeem and Playbook screens in the designv2 look. Behaviour (codes, throttle, answers) is tested elsewhere."""
import re
from unittest import mock

from django.urls import reverse

from deals.forms import RedeemForm
from deals.tests.helpers import DealTestCase


def visible_panes(html):
    return [tag for tag in re.findall(r'<div class="scroll[^"]*"[^>]*>', html) if ' hidden' not in tag]


class RedeemFormTests(DealTestCase):
    def test_code_field_uses_the_big_monospace_input_style(self):
        attrs = RedeemForm().fields['code'].widget.attrs
        self.assertEqual(attrs['class'], 'input code big')
        self.assertEqual(attrs['autocapitalize'], 'characters')


class RedeemScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.books_owner)

    def html(self):
        return self.client.get(reverse('deals:redeem')).content.decode()

    def test_head_names_the_shop(self):
        html = self.html()
        self.assertEqual(html.count('<h1>'), 1)
        self.assertIn('<h1>Confirm a customer</h1>', html)
        self.assertIn(self.books.name, html[html.index('<h1>'):html.index('</form>')])

    def test_code_field_is_the_design_input(self):
        self.assertRegex(self.html(), r'<input[^>]*name="code"[^>]*class="input code big"|<input[^>]*class="input code big"[^>]*name="code"')

    def test_pinned_bar_has_scan_qr_coming_soon_and_a_submit_confirm_for_the_form(self):
        html = self.html()
        bar = html[html.index('class="actionbar"'):]
        self.assertIn('data-soon="Camera scan"', bar)
        self.assertRegex(bar, r'<button class="btn big" type="submit" form="redeem-form"[^>]*>Confirm</button>')
        self.assertIn('id="redeem-form"', html)
        self.assertIn('csrfmiddlewaretoken', html)

    def test_the_page_has_one_scroll_region(self):
        self.assertEqual(len(visible_panes(self.html())), 1)

    def test_empty_state_when_nothing_was_confirmed(self):
        html = self.html()
        self.assertIn('class="empty"', html)
        self.assertIn('No confirmations yet', html)

    def test_recent_confirmations_are_design_rows(self):
        deal = self.active_deal()
        self.redeem_once(deal, self.cafe, self.books_owner)
        html = self.html()
        self.assertNotIn('No confirmations yet', html)
        self.assertIn('class="row"', html)
        self.assertIn(f'Sent by {self.cafe.name}', html)
        self.assertRegex(html, r'<b>Sent by [^<]+</b><p class="muted sm">[A-Z][a-z]{2} \d')   # the time sits under the name, not squeezed beside it

    def test_a_wrong_code_still_shows_the_error_toast_after_the_redirect(self):
        response = self.client.post(reverse('deals:redeem'), {'code': 'ZZZZZZZZ'}, follow=True)
        self.assertContains(response, 'class="toast"')


class PlaybookScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cafe_owner)

    def html(self, result=None, q='bakery?'):
        if result is None:
            return self.client.get(reverse('deals:playbook')).content.decode()
        with mock.patch('deals.views.answer_playbook', return_value=result):
            return self.client.get(reverse('deals:playbook'), {'q': q}).content.decode()

    PASSAGE = {'title': 'Bakery and flower shop pairing', 'text': 'Both sell gifts for the same occasions.', 'score': 0.5}

    def test_head_and_search_follow_the_design(self):
        html = self.html()
        self.assertIn('<h1>Deal playbook</h1>', html)
        self.assertIn('Answers cite their sources', html)
        self.assertRegex(html, r'<input[^>]*type="search"[^>]*name="q"')
        self.assertIn('class="input"', html)

    def test_examples_are_full_width_rows_before_a_question(self):
        """The example questions are long, so they are rows that wrap, not chips that run off the screen."""
        html = self.html()
        self.assertEqual(len(re.findall(r'<a class="row" href="\?q=', html)), 3)
        self.assertNotIn('class="chip"', html)

    def test_one_scroll_region(self):
        self.assertEqual(len(visible_panes(self.html())), 1)
        self.assertEqual(len(visible_panes(self.html({'source': 'ai', 'reason': '', 'answer': 'A.', 'passages': [self.PASSAGE]}))), 1)

    def test_ai_answer_is_a_callout_with_sources_and_feedback_coming_soon(self):
        html = self.html({'source': 'ai', 'reason': '', 'answer': 'Offer a pastry discount.', 'passages': [self.PASSAGE]})
        self.assertIn('class="callout"', html)
        self.assertIn('Offer a pastry discount.', html)
        self.assertIn('Bakery and flower shop pairing', html)
        self.assertEqual(html.count('data-soon="Feedback"'), 2)
        self.assertIn('Useful', html)
        self.assertIn('Not useful', html)

    def test_fallback_shows_the_banner_and_the_passages(self):
        html = self.html({'source': 'fallback', 'reason': 'AI is not configured.', 'answer': '', 'passages': [self.PASSAGE]})
        self.assertIn('class="banner"', html)
        self.assertIn('AI is not configured.', html)
        self.assertIn('Bakery and flower shop pairing', html)
        self.assertNotIn('class="callout"', html)

    def test_not_covered_is_the_empty_state(self):
        html = self.html({'source': 'none', 'reason': 'No playbook passage matched that question.', 'answer': '', 'passages': []})
        self.assertIn('class="empty"', html)
        self.assertIn('The playbook does not cover this', html)
