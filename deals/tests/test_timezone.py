"""One timezone everywhere: pages, exports, the API and "today" all use the project's TIME_ZONE (America/Chicago)."""
import csv
import io
from datetime import date, datetime, timezone as utc_zone

from django.urls import reverse

from deals import services
from deals.models import Deal, Redemption

from .helpers import DealTestCase

# 03:00 UTC on 17 Nov is 9:00 pm on 16 Nov in Chicago (CST, UTC-6).
MOMENT = datetime(2026, 11, 17, 3, 0, tzinfo=utc_zone.utc)
LOCAL_ISO = '2026-11-16T21:00:00-06:00'


class TimezoneTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.deal = self.active_deal()
        self.redeem_once(self.deal, self.cafe, self.books_owner)
        Redemption.objects.update(confirmed_at=MOMENT)
        self.client.force_login(self.cafe_owner)

    def test_json_export_uses_chicago_time(self):
        data = self.client.get(reverse('deals:export_json', args=[self.deal.pk])).json()
        self.assertEqual(data['redemptions'][0]['confirmed_at'], LOCAL_ISO)
        self.assertRegex(data['generated_at'], r'-0[56]:00$')

    def test_csv_export_uses_chicago_time(self):
        body = self.client.get(reverse('deals:export_csv', args=[self.deal.pk])).content.decode()
        rows = list(csv.DictReader(io.StringIO(body)))
        self.assertEqual(rows[0]['confirmed_at'], LOCAL_ISO)

    def test_redemptions_api_uses_chicago_time(self):
        data = self.client.get(reverse('deals:api_redemptions', args=[self.deal.pk])).json()
        self.assertEqual(data['results'][0]['confirmed_at'], LOCAL_ISO)

    def test_public_stats_api_timestamp_has_a_chicago_offset(self):
        data = self.client.get(reverse('deals:api_stats')).json()
        self.assertRegex(data['generated_at'], r'-0[56]:00$')

    def test_pages_show_the_chicago_clock_time(self):
        self.client.force_login(self.books_owner)
        html = self.client.get(reverse('deals:redeem')).content.decode()
        self.assertIn('Nov 16, 9:00 p.m.', html)
        self.assertNotIn('Nov 17, 3:00 a.m.', html)


class TodayIsChicagoToday(DealTestCase):
    """Evening in Chicago is already tomorrow in UTC; a deal must start on the Chicago date."""

    def test_a_deal_starting_on_the_chicago_date_activates_even_when_utc_is_a_day_ahead(self):
        deal = self.proposed_deal(start_date=date(2026, 11, 16), end_date=date(2026, 12, 16))
        services.accept(deal, self.books_owner)
        deal.refresh_from_db()
        services.sync_status(deal, now=MOMENT)          # Chicago date is 16 Nov
        self.assertEqual(deal.status, Deal.Status.ACTIVE)

    def test_a_deal_starting_on_the_utc_date_is_not_active_yet_in_chicago(self):
        deal = self.proposed_deal(start_date=date(2026, 11, 17), end_date=date(2026, 12, 16))
        services.accept(deal, self.books_owner)
        deal.refresh_from_db()
        services.sync_status(deal, now=MOMENT)          # UTC date is 17 Nov, Chicago date is still 16 Nov
        self.assertEqual(deal.status, Deal.Status.ACCEPTED)
