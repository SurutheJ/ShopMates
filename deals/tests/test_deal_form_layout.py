"""The send buttons are pinned in an action bar below the one scroll region (design rule 2), not at the end of a long form."""
import re

from django.urls import reverse

from .helpers import DealTestCase


class PinnedActionBarTests(DealTestCase):
    def bar(self, html):
        match = re.search(r'<div class="actionbar">(.*?)</div>', html, re.S)
        self.assertIsNotNone(match, 'no action bar')
        return match.group(1)

    def test_send_is_pinned_in_the_bar_and_save_as_draft_is_in_the_review_step(self):
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:new', args=[self.books.pk])).content.decode()
        bar = self.bar(html)
        self.assertIn('form="deal-form" name="action" value="send"', bar)
        self.assertGreater(html.index('class="actionbar"'), html.index('</form>'))   # the bar is outside the form and its scroll panes
        form = html[html.index('<form'):html.index('</form>')]
        self.assertIn('name="action" value="save"', form)

    def test_counter_button_is_in_the_action_bar(self):
        deal = self.proposed_deal()
        self.client.force_login(self.books_owner)
        html = self.client.get(reverse('deals:counter', args=[deal.pk])).content.decode()
        self.assertIn('Send counter<', self.bar(html))
        self.assertIn('form="deal-form"', self.bar(html))

    def test_page_still_has_one_visible_scroll_region_and_one_visible_h1(self):
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:new', args=[self.books.pk])).content.decode()
        panes = re.split(r'(?=<div class="scroll")', html)[1:]
        visible = [p for p in panes if ' hidden' not in p[:p.index('>')]]
        self.assertEqual(len(visible), 1)
        self.assertEqual(len(re.findall(r'<h1[ >]', visible[0])), 1)

    def test_posting_the_form_with_the_bar_button_value_sends_the_proposal(self):
        from deals.models import Deal
        from .helpers import make_terms
        self.client.force_login(self.cafe_owner)
        data = {k: v for k, v in make_terms().items()}
        data['action'] = 'send'
        response = self.client.post(reverse('deals:new', args=[self.books.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Deal.objects.get().status, Deal.Status.PROPOSED)


class FieldLayoutTests(DealTestCase):
    """The deal forms follow the phone layout: the AI helper first, the whole offer visible, a real Back button."""

    def pages(self):
        deal = self.proposed_deal()
        self.client.force_login(self.cafe_owner)
        new = self.client.get(reverse('deals:new', args=[self.books.pk])).content.decode()
        self.client.force_login(self.books_owner)
        counter = self.client.get(reverse('deals:counter', args=[deal.pk])).content.decode()
        return new, counter

    def test_the_offer_box_is_tall_enough_for_the_default_text(self):
        new, counter = self.pages()
        for html in (new, counter):
            self.assertRegex(html, r'<textarea name="offer_text"[^>]*rows="3"')

    def test_draft_with_ai_comes_before_the_offer_field(self):
        new, counter = self.pages()
        self.assertLess(new.index('id="ai-draft"'), new.index('id="id_offer_text"'))
        self.assertNotIn('id="ai-draft"', counter)

    def test_draft_with_ai_is_a_full_width_button_with_a_status_line(self):
        new, _ = self.pages()
        self.assertRegex(new, r'<button[^>]*id="ai-draft"[^>]*class="[^"]*\bblock\b')
        self.assertIn('id="ai-status"', new)

    def test_back_is_a_design_back_button(self):
        new, counter = self.pages()
        for html in (new, counter):
            self.assertRegex(html, r'<a class="btn back" href="[^"]*">')

    def test_every_term_field_uses_the_design_input_class(self):
        new, counter = self.pages()
        for html in (new, counter):
            for name in ('offer_text', 'discount_percent', 'redemption_cap', 'start_date', 'end_date', 'terms'):
                self.assertRegex(html, r'<(input|textarea)[^>]*name="%s"[^>]*class="input"' % name)


class WizardTests(DealTestCase):
    """New and edit proposals are the design's four steps; the counter-offer is one screen with a diff."""

    def new_html(self, **post):
        self.client.force_login(self.cafe_owner)
        url = reverse('deals:new', args=[self.books.pk])
        response = self.client.post(url, post) if post else self.client.get(url)
        return response.content.decode()

    def test_four_steps_with_a_stepper_and_only_the_first_visible(self):
        html = self.new_html()
        self.assertIn('data-wizard', html)
        panes = re.findall(r'<div class="scroll" data-step="(\d)"([^>]*)>', html)
        self.assertEqual([n for n, _ in panes], ['1', '2', '3', '4'])
        self.assertEqual([' hidden' in rest for _, rest in panes], [False, True, True, True])
        for label in ('Partner', 'Offer', 'Terms', 'Send'):
            self.assertIn('<span>%s</span>' % label, html)

    def test_bar_has_back_next_and_send(self):
        bar = re.search(r'<div class="actionbar">(.*?)</div>', self.new_html(), re.S).group(1)
        self.assertIn('data-prev', bar)
        self.assertIn('data-next', bar)
        self.assertIn('value="send"', bar)

    def test_first_step_shows_the_partner_and_both_typical_spends(self):
        html = self.new_html()
        step1 = html[html.index('data-step="1"'):html.index('data-step="2"')]
        self.assertIn('Pageturner', step1)
        self.assertIn('Your typical spend', step1)
        self.assertIn('$10.00', step1)
        self.assertIn('$20.00', step1)

    def test_a_big_spend_gap_gets_a_warning_and_equal_spends_do_not(self):
        self.assertIn('class="callout warn"', self.new_html())
        self.books.typical_order_value = self.cafe.typical_order_value
        self.books.save()
        self.assertNotIn('class="callout warn"', self.new_html())

    def test_an_invalid_form_reopens_on_the_step_with_the_error(self):
        from .helpers import make_terms
        good = make_terms()
        self.assertIn('data-start="3"', self.new_html(**dict(good, redemption_cap=0, action='send')))
        self.assertIn('data-start="2"', self.new_html(**dict(good, offer_text='', action='send')))
        self.assertIn('data-start="1"', self.new_html())

    def test_the_review_step_has_the_note_and_save_as_draft(self):
        html = self.new_html()
        step4 = html[html.index('data-step="4"'):]
        self.assertIn('name="message"', step4)
        self.assertIn('value="save"', step4)

    def test_counter_is_one_screen_with_a_diff_against_their_offer(self):
        deal = self.proposed_deal(discount_percent=15, redemption_cap=40)
        self.client.force_login(self.books_owner)
        html = self.client.get(reverse('deals:counter', args=[deal.pk])).content.decode()
        self.assertNotIn('data-wizard', html)
        self.assertIn('class="diff"', html)
        self.assertRegex(html, r'data-diff="id_discount_percent" data-orig="15"')
        self.assertRegex(html, r'data-diff="id_redemption_cap" data-orig="40"')
        self.assertIn('Counter Green Cafe', html)
