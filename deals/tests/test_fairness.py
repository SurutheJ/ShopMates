"""The fairness calculator (plain Decimal math, no AI), its JSON endpoint, and the margin field it reads."""
from datetime import timedelta
from decimal import Decimal as D

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ShopForm
from accounts.models import Shop
from deals.fairness import fairness

from .helpers import DealTestCase, make_shop, make_user


def shop(name, ticket, margin, discount, cap=50):
    return {'name': name, 'ticket': D(ticket), 'margin_pct': D(margin), 'discount_percent': D(discount), 'cap': cap}


class WorkedExampleTests(SimpleTestCase):
    """The example in section 6 of the build spec, to the cent."""

    def setUp(self):
        self.result = fairness(shop('Cafe', 6, 65, 10), shop('Bookstore', 24, 35, 10), months=2)

    def test_per_shop_numbers(self):
        a, b = self.result['a'], self.result['b']
        self.assertEqual((a['redemptions'], b['redemptions']), (40, 40))
        self.assertEqual((a['discount'], b['discount']), (D('0.60'), D('2.40')))
        self.assertEqual((a['profit_per_redemption'], b['profit_per_redemption']), (D('3.30'), D('6.00')))
        self.assertEqual((a['profit'], b['profit']), (D('132.00'), D('240.00')))

    def test_imbalance_and_label(self):
        self.assertEqual(self.result['imbalance'], D('0.45'))
        self.assertEqual(self.result['label'], 'lopsided')
        self.assertEqual(self.result['better_off'], 'Bookstore')
        self.assertEqual(self.result['blockers'], [])

    def test_suggestion_raises_the_bookstore_to_17_percent(self):
        s = self.result['suggestion']
        self.assertEqual(s['shop'], 'Bookstore')
        self.assertEqual(s['discount_percent'], 17)
        self.assertEqual(s['profit_per_redemption'], D('4.32'))
        self.assertEqual(s['profit'], D('172.80'))
        self.assertEqual(s['imbalance'], D('0.236'))

    def test_explanation_uses_the_real_numbers(self):
        self.assertEqual(
            self.result['explanation'],
            'At these terms, Cafe is estimated to earn $132.00 and Bookstore $240.00 over 2 months (45% apart). '
            "Raising Bookstore's discount to 17% brings them within 24%.")


class FairnessRuleTests(SimpleTestCase):
    def test_balanced_deal_has_no_suggestion_and_one_sentence(self):
        result = fairness(shop('A', 10, 50, 10), shop('B', 11, 50, 10), months=1)
        self.assertEqual(result['label'], 'balanced')
        self.assertIsNone(result['suggestion'])
        self.assertEqual(result['note'], '')
        self.assertEqual(result['explanation'],
                         'At these terms, A is estimated to earn $80.00 and B $88.00 over 1 month (9% apart).')

    def test_cap_limits_redemptions(self):
        result = fairness(shop('A', 10, 50, 10, cap=5), shop('B', 10, 50, 10, cap=5), months=3)
        self.assertEqual(result['a']['redemptions'], 5)
        self.assertEqual(result['a']['profit'], D('20.00'))

    def test_above_half_is_very_lopsided(self):
        result = fairness(shop('A', 5, 50, 10), shop('B', 50, 50, 10), months=1)
        self.assertEqual(result['label'], 'very lopsided')

    def test_negative_profit_per_redemption_is_a_blocker(self):
        result = fairness(shop('A', 10, 20, 30), shop('B', 10, 50, 30), months=1)
        self.assertEqual(result['a']['profit_per_redemption'], D('-1.00'))
        self.assertEqual(result['blockers'], ['A loses money on every redemption'])

    def test_unreachable_balance_gives_no_suggestion_and_a_note_about_caps(self):
        # A breaks even exactly, so B cannot come within 25% of A while still earning anything.
        result = fairness(shop('A', 10, 10, 10), shop('B', 10, 50, 10), months=1)
        self.assertEqual(result['label'], 'very lopsided')
        self.assertIsNone(result['suggestion'])
        self.assertIn('unequal caps', result['note'])
        self.assertNotIn('Raising', result['explanation'])


class FairnessEndpointTests(DealTestCase):
    def setUp(self):
        super().setUp()
        Shop.objects.filter(pk=self.cafe.pk).update(typical_order_value=6, margin_pct=65)
        Shop.objects.filter(pk=self.books.pk).update(typical_order_value=24, margin_pct=35)
        self.client.force_login(self.cafe_owner)
        self.url = reverse('deals:fairness', args=[self.books.pk])
        today = timezone.localdate()
        self.data = {'discount_percent': 10, 'cap': 50,
                     'start_date': today.isoformat(), 'end_date': (today + timedelta(days=60)).isoformat()}

    def test_owner_gets_json_for_their_shop_against_the_partner(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['months'], 2)
        self.assertEqual((data['a']['name'], data['a']['profit']), ('Green Cafe', '132.00'))
        self.assertEqual((data['b']['name'], data['b']['profit']), ('Pageturner', '240.00'))
        self.assertEqual(data['label'], 'lopsided')
        self.assertEqual(data['suggestion']['discount_percent'], 17)
        self.assertFalse(data['margin_assumed'])

    def test_partner_discount_can_differ(self):
        response = self.client.post(self.url, dict(self.data, partner_discount_percent=17))
        self.assertEqual(response.json()['b']['profit'], '172.80')
        self.assertEqual(response.json()['label'], 'balanced')

    def test_a_shop_without_a_margin_uses_50_and_says_so(self):
        Shop.objects.filter(pk=self.books.pk).update(margin_pct=None)
        data = self.client.post(self.url, self.data).json()
        self.assertTrue(data['margin_assumed'])
        self.assertEqual(data['b']['profit'], '384.00')   # 40 x (50% - 10%) x $24

    def test_a_short_deal_counts_as_one_month(self):
        self.data['end_date'] = self.data['start_date']
        self.assertEqual(self.client.post(self.url, self.data).json()['months'], 1)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_a_post_without_the_csrf_token_is_refused(self):
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.cafe_owner)
        self.assertEqual(strict.post(self.url, self.data).status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_staff_are_forbidden(self):
        from accounts.models import ShopMembership
        staff = make_user('cafe_staff')
        ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)

    def test_own_shop_or_a_shop_that_is_not_approved_is_404(self):
        pending = make_shop('Pending Co', status=Shop.Status.PENDING)
        suspended = make_shop('Suspended Co', status=Shop.Status.SUSPENDED)
        for pk in (self.cafe.pk, pending.pk, suspended.pk, 99999):
            self.assertEqual(self.client.post(reverse('deals:fairness', args=[pk]), self.data).status_code, 404, pk)

    def test_bad_numbers_are_rejected(self):
        bad = [{'discount_percent': 'abc'}, {'discount_percent': 0}, {'discount_percent': 101},
               {'partner_discount_percent': 0}, {'cap': 0}, {'cap': ''}, {'start_date': 'soon'},
               {'end_date': (timezone.localdate() - timedelta(days=1)).isoformat()}]
        for change in bad:
            response = self.client.post(self.url, dict(self.data, **change))
            self.assertEqual(response.status_code, 400, change)
            self.assertIn('error', response.json())

    def test_the_review_step_has_the_card(self):
        html = self.client.get(reverse('deals:new', args=[self.books.pk])).content.decode()
        self.assertIn('Is it balanced?', html)
        self.assertIn(f'data-fairness="{self.url}"', html)


class ShopMarginFormTests(SimpleTestCase):
    def form(self, margin):
        return ShopForm({'name': 'Green Cafe', 'category': 'cafe', 'address': '1 Green St', 'city': 'Champaign',
                         'hours': '', 'typical_order_value': '9.50', 'latitude': '', 'longitude': '',
                         'margin_pct': margin})

    def test_accepts_a_margin_or_none(self):
        for value in ('', '0', '65', '37.5', '100'):
            self.assertTrue(self.form(value).is_valid(), value)

    def test_rejects_a_margin_outside_0_to_100(self):
        for value in ('101', '-1', 'lots'):
            form = self.form(value)
            self.assertFalse(form.is_valid(), value)
            self.assertIn('margin_pct', form.errors)
