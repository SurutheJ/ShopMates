import re

from django.urls import reverse

from deals import services
from deals.models import DealMessage

from .helpers import DealTestCase, make_terms


class DealScreenTests(DealTestCase):
    """The deal page is the design's deal room: Terms, Chat and History tabs, with the actions pinned below."""

    def html(self, deal, user):
        self.client.force_login(user)
        return self.client.get(deal.get_absolute_url()).content.decode()

    def bar(self, html, tabs):
        """The pinned bar for these tabs (the mock's data-bar="a c"), or None: the text from its marker to the next bar or the end of the screen."""
        marker = 'data-bar="%s"' % tabs
        if marker not in html:
            return None
        rest = html[html.index(marker) + len(marker):]
        return re.split(r'data-bar=|</section>', rest)[0]

    def test_head_has_back_the_partner_name_and_three_tabs(self):
        deal = self.proposed_deal()
        html = self.html(deal, self.books_owner)
        self.assertRegex(html, r'<a class="btn back" href="%s">' % reverse('deals:inbox'))
        self.assertIn('<h1>Green Cafe</h1>', html)
        for label, name in (('Terms', 'terms'), ('Chat', 'chat'), ('History', 'history')):
            self.assertIn('data-tab="%s"' % name, html)
            self.assertIn('>%s</button>' % label, html)

    def test_it_is_your_turn_badge_and_the_three_answer_buttons(self):
        deal = self.proposed_deal()
        html = self.html(deal, self.books_owner)
        self.assertIn('class="badge turn">Your turn<', html)
        bar = self.bar(html, 'a c')
        self.assertIn(reverse('deals:action', args=[deal.pk, 'decline']), bar)
        self.assertIn(reverse('deals:counter', args=[deal.pk]), bar)
        self.assertIn(reverse('deals:action', args=[deal.pk, 'accept']), bar)

    def test_the_proposer_waiting_on_them_gets_no_answer_buttons_but_can_withdraw(self):
        deal = self.proposed_deal()
        html = self.html(deal, self.cafe_owner)
        self.assertIsNone(self.bar(html, 'a c'))
        self.assertIn(reverse('deals:action', args=[deal.pk, 'withdraw']), html)
        self.assertIn('Waiting on Pageturner', html)

    def test_a_draft_has_send_in_the_bar_and_edit_and_withdraw_buttons(self):
        deal = services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms(), send=False)
        html = self.html(deal, self.cafe_owner)
        self.assertIn(reverse('deals:action', args=[deal.pk, 'send']), self.bar(html, 'a c'))
        self.assertIn(reverse('deals:edit', args=[deal.pk]), html)
        self.assertIn(reverse('deals:action', args=[deal.pk, 'withdraw']), html)
        self.assertIn('class="badge draft"', html)

    def test_a_running_deal_offers_qr_card_and_summary_buttons(self):
        deal = self.active_deal()
        html = self.html(deal, self.cafe_owner)
        for name in ('deals:qr', 'deals:card', 'deals:summary'):
            self.assertIn(reverse(name, args=[deal.pk]), html)

    def test_terms_pane_shows_the_offer_and_the_key_values(self):
        deal = self.proposed_deal(discount_percent=15, redemption_cap=40)
        html = self.html(deal, self.books_owner)
        pane = html[html.index('data-pane="a"'):html.index('data-pane="b"')]
        self.assertIn('10% off one purchase', pane)
        for label in ('Discount', 'Cap per shop', 'Dates', 'Proposed by'):
            self.assertIn('<dt>%s</dt>' % label, pane)
        self.assertIn('<dd>15%</dd>', pane)

    def test_chat_shows_bubbles_mine_on_the_right_and_a_message_bar(self):
        deal = self.proposed_deal()
        DealMessage.objects.create(deal=deal, author=self.cafe_owner, shop=self.cafe, body='Hello neighbor')
        DealMessage.objects.create(deal=deal, author=self.books_owner, shop=self.books, body='Hi back')
        html = self.html(deal, self.books_owner)
        self.assertRegex(html, r'<div class="bubble">Hello neighbor')
        self.assertRegex(html, r'<div class="bubble me">Hi back')
        bar = self.bar(html, 'b')
        self.assertIn('name="body"', bar)
        self.assertIn(reverse('deals:message', args=[deal.pk]), html)

    def test_an_empty_chat_says_so(self):
        html = self.html(self.proposed_deal(), self.books_owner)
        pane = html[html.index('data-pane="b"'):html.index('data-pane="c"')]
        self.assertIn('No messages yet', pane)

    def test_history_lists_versions_and_activity_as_rows(self):
        deal = self.proposed_deal()
        html = self.html(deal, self.books_owner)
        pane = html[html.index('data-pane="c"'):]
        self.assertIn('v1', pane)
        self.assertIn('Green Cafe', pane)
        self.assertIn('class="row"', pane)

    def test_a_completed_deal_offers_renew(self):
        deal = self.active_deal(redemption_cap=1)
        voucher = services.issue_voucher(deal, self.cafe)
        services.redeem_voucher(voucher.code, self.books_owner)
        voucher = services.issue_voucher(deal, self.books)
        services.redeem_voucher(voucher.code, self.cafe_owner)
        deal.refresh_from_db()
        html = self.html(deal, self.cafe_owner)
        self.assertIn('Renew with a higher cap', html)

    def test_sending_a_message_comes_back_to_the_chat_tab(self):
        deal = self.proposed_deal()
        self.client.force_login(self.books_owner)
        response = self.client.post(reverse('deals:message', args=[deal.pk]), {'body': 'Hi'})
        self.assertRedirects(response, deal.get_absolute_url() + '?tab=chat')
