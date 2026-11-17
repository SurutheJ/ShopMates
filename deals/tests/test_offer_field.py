"""The Offer is a short text area (a long offer stays readable on a phone) but is always stored as one line."""
from django.urls import reverse

from deals.forms import DealTermsForm

from .helpers import DealTestCase, make_terms


class OfferFieldTests(DealTestCase):
    def test_new_deal_form_shows_the_offer_in_a_text_area(self):
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:new', args=[self.books.pk])).content.decode()
        self.assertIn('<textarea name="offer_text"', html)

    def test_line_breaks_and_extra_spaces_in_the_offer_become_single_spaces(self):
        form = DealTermsForm(make_terms(offer_text='10% off\n  any drink\r\nfor guests '))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['offer_text'], '10% off any drink for guests')

    def test_the_200_character_limit_still_applies(self):
        form = DealTermsForm(make_terms(offer_text='x' * 201))
        self.assertFalse(form.is_valid())
        self.assertIn('offer_text', form.errors)
