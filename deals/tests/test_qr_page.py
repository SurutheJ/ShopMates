"""The QR page: one big, high-contrast code with a caption saying whose it is and what it gives."""
import io
import re
from datetime import timedelta

import segno
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ShopMembership
from deals import services, views
from deals.models import Deal, DealVersion

from .helpers import DealTestCase, make_shop, make_terms, make_user


@override_settings(SITE_URL='https://shop.example')
class QrPageTests(DealTestCase):
    def url(self, deal):
        return reverse('deals:qr', args=[deal.pk])

    def code_for(self, token):
        """The exact QR image the app draws for a scan link."""
        return views._qr_svg(f'https://shop.example/v/{token}/')

    def test_the_owner_sees_their_own_qr_with_a_caption(self):
        deal = self.active_deal(offer_text='Free cookie with any coffee', discount_percent=15)
        self.client.force_login(self.cafe_owner)
        response = self.client.get(self.url(deal))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(self.code_for(deal.proposer_token), html)       # the cafe's own code
        self.assertNotIn(self.code_for(deal.recipient_token), html)   # never the partner's
        self.assertIn('<svg', html)
        self.assertContains(response, 'Green Cafe')             # which shop it is for
        self.assertContains(response, 'one-time code for <b>Pageturner</b>')
        self.assertContains(response, 'Free cookie with any coffee')
        self.assertContains(response, '15% off')

    def test_the_other_shop_gets_its_own_code(self):
        deal = self.active_deal()
        self.client.force_login(self.books_owner)
        html = self.client.get(self.url(deal)).content.decode()
        self.assertIn(self.code_for(deal.recipient_token), html)
        self.assertNotIn(self.code_for(deal.proposer_token), html)

    def test_black_on_white_with_the_full_four_module_quiet_zone(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        html = self.client.get(self.url(deal)).content.decode()
        svg = re.search(r'<svg[^>]*class="segno".*?</svg>', html, re.S).group(0)
        self.assertIn('#000', svg)
        self.assertIn('#fff', svg)
        width = int(re.search(r'viewBox="0 0 (\d+) \d+"', svg).group(1))
        url = f'https://shop.example/v/{deal.proposer_token}/'
        modules = segno.make(url, error='q').symbol_size(scale=1, border=0)[0]
        self.assertEqual(width, modules + 8)

    def test_an_accepted_deal_that_has_not_started_says_when_it_starts(self):
        start = timezone.localdate() + timedelta(days=5)
        deal = self.active_deal(start_date=start, end_date=start + timedelta(days=10))
        self.assertEqual(deal.status, 'accepted')
        self.client.force_login(self.cafe_owner)
        self.assertContains(self.client.get(self.url(deal)), 'Starts working on')

    def test_no_code_before_acceptance_or_after_completion(self):
        proposed = self.proposed_deal()
        self.client.force_login(self.cafe_owner)
        self.assertRedirects(self.client.get(self.url(proposed)), proposed.get_absolute_url())
        Deal.objects.all().delete()
        done = self.active_deal(redemption_cap=4)
        today = timezone.localdate()
        DealVersion.objects.filter(deal=done).update(start_date=today - timedelta(days=30),
                                                     end_date=today - timedelta(days=1))
        self.assertRedirects(self.client.get(self.url(done)), done.get_absolute_url())

    def test_outsiders_and_staff_are_kept_out(self):
        deal = self.active_deal()
        outsider = make_user('outsider')
        make_shop('Other Shop', outsider, category='bakery')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url(deal)).status_code, 404)
        staff = make_user('cafe_staff')
        ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url(deal)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(deal)).status_code, 302)   # to sign in

    def test_the_deal_page_and_summary_link_to_it_instead_of_inlining_the_code(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        for page in (deal.get_absolute_url(), reverse('deals:summary', args=[deal.pk])):
            response = self.client.get(page)
            self.assertContains(response, self.url(deal))
            self.assertNotContains(response, 'class="segno"')


@override_settings(SITE_URL='https://shop.example')
class QrDownloadTests(DealTestCase):
    def link(self, token):
        return f'https://shop.example/v/{token}/'

    def expected(self, token, kind):
        buf = io.BytesIO()
        code = segno.make(self.link(token), error='q')
        options = {'scale': views.qr_png_scale(code), 'border': 4, 'dark': '#000', 'light': '#fff'}
        if kind == 'svg':
            options.update(scale=10, xmldecl=True, title='Green Cafe QR code')
        if kind == 'pdf':
            options.update(scale=10)
        code.save(buf, kind=kind, **options)
        return buf.getvalue()

    def get(self, deal, kind):
        return self.client.get(reverse(f'deals:qr_{kind}', args=[deal.pk]))

    def test_png_is_an_attachment_of_the_shops_own_code(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        response = self.get(deal, 'png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="shopmates-green-cafe-qr.png"')
        self.assertEqual(response.content, self.expected(deal.proposer_token, 'png'))
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_svg_is_an_attachment_of_the_shops_own_code(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        response = self.get(deal, 'svg')
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="shopmates-green-cafe-qr.svg"')
        self.assertEqual(response.content, self.expected(deal.proposer_token, 'svg'))
        self.assertTrue(response.content.startswith(b'<?xml'))

    def test_pdf_is_an_attachment_of_the_shops_own_code(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        response = self.get(deal, 'pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="shopmates-green-cafe-qr.pdf"')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertEqual(response.content, self.expected(deal.proposer_token, 'pdf'))

    def test_the_other_shop_downloads_its_own_code(self):
        deal = self.active_deal()
        self.client.force_login(self.books_owner)
        for kind in ('png', 'svg', 'pdf'):
            body = self.get(deal, kind).content
            self.assertNotEqual(body, self.expected(deal.proposer_token, kind))
        self.assertIn('shopmates-pageturner-qr.png', self.get(deal, 'png')['Content-Disposition'])

    def test_png_is_big_enough_to_print_and_every_square_is_a_whole_number_of_pixels(self):
        """At least 1200 px wide (4 inches at 300 dpi). A whole-number scale keeps the squares sharp, never blurred."""
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        data = self.get(deal, 'png').content
        width = int.from_bytes(data[16:20], 'big')
        self.assertGreaterEqual(width, 1200)
        modules = segno.make(self.link(deal.proposer_token), error='q').symbol_size(border=4)[0]
        self.assertEqual(width % modules, 0)
        self.assertLess(width, 1200 + modules)   # no larger than the smallest whole scale that reaches 1200

    def test_the_same_rules_as_the_page(self):
        proposed = self.proposed_deal()
        self.client.force_login(self.cafe_owner)
        for kind in ('png', 'svg', 'pdf'):
            self.assertRedirects(self.get(proposed, kind), proposed.get_absolute_url())
        Deal.objects.all().delete()
        deal = self.active_deal()
        staff = make_user('cafe_staff')
        ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        outsider = make_user('outsider')
        make_shop('Other Shop', outsider, category='bakery')
        for kind in ('png', 'svg', 'pdf'):
            self.client.force_login(staff)
            self.assertEqual(self.get(deal, kind).status_code, 403)
            self.client.force_login(outsider)
            self.assertEqual(self.get(deal, kind).status_code, 404)
            self.client.logout()
            self.assertEqual(self.get(deal, kind).status_code, 302)

    def test_the_page_offers_both_downloads_and_a_copy_button_with_the_link(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:qr', args=[deal.pk])).content.decode()
        self.assertIn(reverse('deals:qr_png', args=[deal.pk]), html)
        self.assertIn(reverse('deals:qr_svg', args=[deal.pk]), html)
        self.assertIn(reverse('deals:qr_pdf', args=[deal.pk]), html)
        self.assertIn(f'data-copy="{self.link(deal.proposer_token)}"', html)
        self.assertNotIn(self.link(deal.recipient_token), html)


@override_settings(SITE_URL='https://shop.example')
class CounterCardTests(DealTestCase):
    def url(self, deal):
        return reverse('deals:card', args=[deal.pk])

    def code_for(self, token):
        return views._qr_svg(f'https://shop.example/v/{token}/')

    def test_the_card_names_both_shops_the_offer_and_the_dates(self):
        end = timezone.localdate() + timedelta(days=30)
        deal = self.active_deal(offer_text='Free cookie with any coffee', discount_percent=15, redemption_cap=30,
                                end_date=end)
        self.client.force_login(self.cafe_owner)
        response = self.client.get(self.url(deal))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Green Cafe + Pageturner')
        self.assertContains(response, 'Take 15% off at Pageturner')
        self.assertContains(response, f'before {end:%b} {end.day}')
        self.assertContains(response, 'Free cookie with any coffee')
        self.assertContains(response, 'first 30 redemptions')
        self.assertContains(response, 'One use per code')
        self.assertContains(response, 'Codes expire after 24 hours')
        self.assertContains(response, f'Deal #{deal.pk}')

    def test_two_copies_of_the_shops_own_code_and_a_link_to_type_in(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        html = self.client.get(self.url(deal)).content.decode()
        self.assertEqual(html.count('class="counter-card'), 2)
        self.assertEqual(html.count(self.code_for(deal.proposer_token)), 2)
        self.assertNotIn(self.code_for(deal.recipient_token), html)
        self.assertEqual(html.count(f'shop.example/v/{deal.proposer_token}/'), 2)

    def test_the_other_shop_gets_its_own_card(self):
        deal = self.active_deal()
        self.client.force_login(self.books_owner)
        html = self.client.get(self.url(deal)).content.decode()
        self.assertIn(self.code_for(deal.recipient_token), html)
        self.assertNotIn(self.code_for(deal.proposer_token), html)
        self.assertIn('Pageturner + Green Cafe', html)

    def test_the_same_rules_as_the_qr_page(self):
        proposed = self.proposed_deal()
        self.client.force_login(self.cafe_owner)
        self.assertRedirects(self.client.get(self.url(proposed)), proposed.get_absolute_url())
        Deal.objects.all().delete()
        deal = self.active_deal()
        staff = make_user('cafe_staff')
        ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        outsider = make_user('outsider')
        make_shop('Other Shop', outsider, category='bakery')
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url(deal)).status_code, 403)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url(deal)).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(deal)).status_code, 302)

    def test_the_deal_page_and_summary_link_to_the_card(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        for page in (deal.get_absolute_url(), reverse('deals:summary', args=[deal.pk])):
            self.assertContains(self.client.get(page), self.url(deal))

    def test_the_print_stylesheet_sets_letter_paper(self):
        from django.contrib.staticfiles import finders
        css = open(finders.find('css/card.css')).read()
        self.assertIn('size:Letter', css.replace(' ', ''))
