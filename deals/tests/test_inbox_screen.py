from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from deals import services
from deals.models import Deal, Redemption

from .helpers import DealTestCase, make_shop, make_terms, make_user

S = Deal.Status


class StatusToneTests(DealTestCase):
    """Which badge colour a deal's status gets (ok, warn, bad, draft, or none)."""

    def tone(self, status):
        return Deal(status=status).status_tone

    def test_live_deals_are_ok(self):
        self.assertEqual(self.tone(S.ACTIVE), 'ok')
        self.assertEqual(self.tone(S.ACCEPTED), 'ok')

    def test_open_negotiation_is_warn(self):
        self.assertEqual(self.tone(S.PROPOSED), 'warn')
        self.assertEqual(self.tone(S.COUNTERED), 'warn')

    def test_draft_has_its_own_tone(self):
        self.assertEqual(self.tone(S.DRAFT), 'draft')

    def test_declined_and_expired_are_bad(self):
        self.assertEqual(self.tone(S.DECLINED), 'bad')
        self.assertEqual(self.tone(S.EXPIRED), 'bad')

    def test_completed_and_withdrawn_have_no_colour(self):
        self.assertEqual(self.tone(S.COMPLETED), '')
        self.assertEqual(self.tone(S.WITHDRAWN), '')


class SentThisMonthTests(DealTestCase):
    def redeem_one(self):
        voucher = services.issue_voucher(self.deal, self.cafe)
        return services.redeem_voucher(voucher.code, self.books_owner)

    def setUp(self):
        super().setUp()
        self.deal = self.active_deal(redemption_cap=5)

    def test_counts_this_months_redemptions_of_customers_the_shop_sent(self):
        self.redeem_one()
        self.redeem_one()
        self.assertEqual(services.customers_sent_this_month(self.cafe), 2)

    def test_the_partner_did_not_send_them(self):
        self.redeem_one()
        self.assertEqual(services.customers_sent_this_month(self.books), 0)

    def test_last_months_redemptions_do_not_count(self):
        redemption = self.redeem_one()
        Redemption.objects.filter(pk=redemption.pk).update(confirmed_at=timezone.now() - timedelta(days=40))
        self.assertEqual(services.customers_sent_this_month(self.cafe), 0)


class InboxScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.bakery_owner = make_user('bakery_owner')
        self.bakery = make_shop('Rise Bakery', self.bakery_owner, category='bakery')
        # Rise Bakery proposes to the cafe: it is the cafe's turn.
        self.deal = services.create_draft(self.bakery, self.cafe, self.bakery_owner, make_terms(), send=True)
        self.client.force_login(self.cafe_owner)

    def html(self):
        return self.client.get(reverse('deals:inbox')).content.decode()

    def test_three_tabs_with_counts(self):
        html = self.html()
        self.assertIn('data-tabs', html)
        self.assertIn('Your turn · 1', html)
        self.assertIn('Running · 0', html)
        self.assertIn('Waiting', html)

    def test_waiting_tab_counts_drafts_and_proposals_sent(self):
        self.assertNotIn('Waiting ·', self.html())
        services.create_draft(self.cafe, self.books, self.cafe_owner, make_terms(), send=False)
        self.assertIn('Waiting · 1', self.html())
        other_owner = make_user('flower_owner')
        flowers = make_shop('Petal Shop', other_owner, category='flowers')
        services.create_draft(self.cafe, flowers, self.cafe_owner, make_terms(), send=True)
        self.assertIn('Waiting · 2', self.html())

    def test_waiting_on_you_row_is_highlighted_with_a_tinted_initials_avatar(self):
        html = self.html()
        self.assertIn('class="row turn"', html)
        self.assertIn('avatar cat--bakery', html)
        self.assertIn('>RB<', html)

    def test_the_two_tiles_show_how_many_need_an_answer_and_customers_sent(self):
        response = self.client.get(reverse('deals:inbox'))
        html = response.content.decode()
        self.assertIn('stat coral', html)
        self.assertIn('need your answer', html)
        self.assertIn('customers sent this month', html)
        self.assertEqual(response.context['sent_this_month'], 0)

    def test_find_a_neighbor_is_in_the_pinned_action_bar(self):
        html = self.html()
        self.assertRegex(html, r'<div class="actionbar">\s*<a class="btn block" href="%s"' % reverse('accounts:discover'))

    def test_wide_screens_get_a_preview_of_the_first_waiting_deal(self):
        response = self.client.get(reverse('deals:inbox'))
        self.assertEqual(response.context['selected'], self.deal)
        html = response.content.decode()
        self.assertIn('class="detail-pane"', html)
        self.assertIn(reverse('deals:action', args=[self.deal.pk, 'accept']), html)
        self.assertIn(reverse('deals:action', args=[self.deal.pk, 'decline']), html)
        self.assertIn(reverse('deals:counter', args=[self.deal.pk]), html)

    def test_no_preview_when_nothing_is_waiting(self):
        services.decline(self.deal, self.cafe_owner)
        response = self.client.get(reverse('deals:inbox'))
        self.assertIsNone(response.context['selected'])
        self.assertNotIn('class="detail-pane"', response.content.decode())

    def test_an_empty_tab_says_so_and_points_to_discover(self):
        services.decline(self.deal, self.cafe_owner)
        html = self.html()
        self.assertIn('Nothing needs your answer', html)
        self.assertIn('class="empty"', html)

    def test_past_tab_only_appears_when_there_are_past_deals(self):
        self.assertNotIn('>Past', self.html())
        services.decline(self.deal, self.cafe_owner)
        self.assertIn('Past · 1', self.html())

    def test_unapproved_shop_sees_a_banner(self):
        self.cafe.status = self.cafe.Status.PENDING
        self.cafe.save()
        html = self.html()
        self.assertIn('class="banner', html)
        self.assertIn('An admin will approve it', html)
