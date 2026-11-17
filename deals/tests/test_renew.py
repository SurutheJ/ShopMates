"""Renew a completed deal as a new deal: prefilled form, the other shop accepts as usual, the old deal is untouched."""
from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from deals import services
from deals.models import Deal, DealVersion

from .helpers import DealTestCase, make_shop, make_terms, make_user

S = Deal.Status


class RenewalTermsTests(DealTestCase):
    def test_the_cap_goes_up_by_half_rounded_up(self):
        for old, new in ((1, 2), (5, 8), (50, 75)):
            deal = self.active_deal(redemption_cap=old)
            self.assertEqual(services.renewal_terms(deal)['redemption_cap'], new, old)
            Deal.objects.all().delete()

    @override_settings(REDEMPTION_CAP_MAX=10)
    def test_the_cap_never_goes_past_the_site_maximum(self):
        deal = self.active_deal(redemption_cap=9)
        self.assertEqual(services.renewal_terms(deal)['redemption_cap'], 10)

    def test_other_terms_carry_over_and_the_dates_start_today_with_the_same_length(self):
        today = timezone.localdate()
        deal = self.active_deal(offer_text='15% off a coffee', discount_percent=15, terms='Mon to Fri only',
                                start_date=today, end_date=today + timedelta(days=20))
        DealVersion.objects.filter(deal=deal).update(start_date=today - timedelta(days=40),
                                                     end_date=today - timedelta(days=20))
        terms = services.renewal_terms(deal)
        self.assertEqual(terms['offer_text'], '15% off a coffee')
        self.assertEqual(terms['discount_percent'], 15)
        self.assertEqual(terms['terms'], 'Mon to Fri only')
        self.assertEqual(terms['start_date'], today)
        self.assertEqual(terms['end_date'], today + timedelta(days=20))


class RenewViewTests(DealTestCase):
    def completed_by_caps(self):
        """Both shops honor their one allowed redemption, so the deal completes."""
        deal = self.active_deal(redemption_cap=1)
        self.redeem_once(deal, self.cafe, self.books_owner)
        self.redeem_once(deal, self.books, self.cafe_owner)
        services.sync_status(deal)
        return deal

    def completed_by_date(self):
        deal = self.active_deal(redemption_cap=4)
        today = timezone.localdate()
        DealVersion.objects.filter(deal=deal).update(start_date=today - timedelta(days=30),
                                                     end_date=today - timedelta(days=1))
        services.sync_status(deal)
        return deal

    def renew_url(self, old, partner):
        return f'{reverse("deals:new", args=[partner.pk])}?renew={old.pk}'

    def test_both_caps_used_counts_as_completed(self):
        self.assertEqual(self.completed_by_caps().status, S.COMPLETED)

    def test_an_end_date_in_the_past_counts_as_completed(self):
        self.assertEqual(self.completed_by_date().status, S.COMPLETED)

    def test_the_button_shows_to_both_owners_on_a_completed_deal(self):
        deal = self.completed_by_caps()
        for user, partner in ((self.cafe_owner, self.books), (self.books_owner, self.cafe)):
            self.client.force_login(user)
            response = self.client.get(deal.get_absolute_url())
            self.assertContains(response, 'Renew with a higher cap')
            self.assertContains(response, self.renew_url(deal, partner).replace('&', '&amp;'))

    def test_no_button_while_only_one_shop_has_used_its_cap(self):
        deal = self.active_deal(redemption_cap=1)
        self.redeem_once(deal, self.cafe, self.books_owner)   # only the books shop has honored one
        services.sync_status(deal)
        self.assertEqual(deal.status, S.ACTIVE)
        self.client.force_login(self.cafe_owner)
        self.assertNotContains(self.client.get(deal.get_absolute_url()), 'Renew with a higher cap')

    def test_no_button_on_a_live_deal(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)
        self.assertNotContains(self.client.get(deal.get_absolute_url()), 'Renew with a higher cap')

    def test_the_form_opens_prefilled_with_the_higher_cap_and_new_dates(self):
        deal = self.completed_by_date()          # cap 4 -> 6
        self.client.force_login(self.books_owner)
        response = self.client.get(self.renew_url(deal, self.cafe))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Renewing')
        form = response.context['form']
        self.assertEqual(form.initial['redemption_cap'], 6)
        self.assertEqual(form.initial['start_date'], timezone.localdate())
        self.assertEqual(form.initial['offer_text'], '10% off one purchase')

    def test_a_renew_link_for_a_deal_that_is_not_completed_is_ignored(self):
        deal = self.active_deal(redemption_cap=4)
        self.client.force_login(self.cafe_owner)
        response = self.client.get(self.renew_url(deal, self.books))
        self.assertNotContains(response, 'Renewing')
        self.assertEqual(response.context['form'].initial['redemption_cap'], 50)

    def test_a_renew_link_for_someone_elses_deal_or_a_wrong_partner_is_ignored(self):
        deal = self.completed_by_date()
        outsider = make_user('outsider')
        other = make_shop('Other Shop', outsider, category='bakery')
        self.client.force_login(outsider)
        response = self.client.get(self.renew_url(deal, self.cafe))
        self.assertNotContains(response, 'Renewing')
        self.assertEqual(response.context['form'].initial['redemption_cap'], 50)
        # A party, but the shop in the URL is not the old partner.
        self.client.force_login(self.cafe_owner)
        response = self.client.get(self.renew_url(deal, other))
        self.assertNotContains(response, 'Renewing')
        # Not a number at all.
        response = self.client.get(f'{reverse("deals:new", args=[self.books.pk])}?renew=abc')
        self.assertEqual(response.status_code, 200)

    def test_sending_the_renewal_makes_a_new_deal_and_leaves_the_old_one_alone(self):
        old = self.completed_by_date()
        before = (old.status, old.updated_at, old.versions.count(), old.events.count(),
                  old.proposer_token, old.recipient_token,
                  list(old.versions.values_list('redemption_cap', 'start_date', 'end_date')))
        self.client.force_login(self.books_owner)
        terms = {**services.renewal_terms(old), 'action': 'send'}
        response = self.client.post(self.renew_url(old, self.cafe), terms)
        new = Deal.objects.exclude(pk=old.pk).get()
        self.assertRedirects(response, new.get_absolute_url())
        self.assertEqual((new.status, new.proposer, new.recipient), (S.PROPOSED, self.books, self.cafe))
        self.assertEqual(new.current_version.redemption_cap, 6)
        old.refresh_from_db()
        after = (old.status, old.updated_at, old.versions.count(), old.events.count(),
                 old.proposer_token, old.recipient_token,
                 list(old.versions.values_list('redemption_cap', 'start_date', 'end_date')))
        self.assertEqual(before, after)

    def test_the_other_shop_accepts_the_renewal_as_usual(self):
        old = self.completed_by_date()
        new = services.create_draft(self.books, self.cafe, self.books_owner,
                                    services.renewal_terms(old), send=True)
        self.client.force_login(self.cafe_owner)
        self.client.post(reverse('deals:action', args=[new.pk, 'accept']))
        new.refresh_from_db()
        self.assertEqual(new.status, S.ACTIVE)
        old.refresh_from_db()
        self.assertEqual(old.status, S.COMPLETED)
        self.assertNotEqual(old.proposer_token, new.proposer_token)

    def test_no_button_once_the_renewal_is_already_running(self):
        old = self.completed_by_date()
        services.create_draft(self.books, self.cafe, self.books_owner, services.renewal_terms(old), send=True)
        for user in (self.cafe_owner, self.books_owner):
            self.client.force_login(user)
            self.assertNotContains(self.client.get(old.get_absolute_url()), 'Renew with a higher cap')


class CompletionRecordedOnceTests(DealTestCase):
    def test_finishing_by_redemptions_records_completed_once(self):
        deal = self.active_deal(redemption_cap=1)
        self.redeem_once(deal, self.cafe, self.books_owner)
        self.redeem_once(deal, self.books, self.cafe_owner)
        fresh = Deal.objects.get(pk=deal.pk)
        services.sync_status(fresh)            # a later page view changes nothing
        self.assertEqual(fresh.status, S.COMPLETED)
        self.assertEqual(fresh.events.filter(action='completed').count(), 1)
