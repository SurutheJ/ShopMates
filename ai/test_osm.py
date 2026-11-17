"""OpenStreetMap lookups. No test here uses the network: `ai.osm.requests.post` is always replaced by a fake."""
import json
import re
from datetime import timedelta
from unittest import mock

import requests
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import OsmQueryCache, Shop
from ai import osm
from ai.radar import radar
from deals.tests.helpers import DealTestCase

LAT, LON = 40.1100, -88.2300
KEY = 'overpass:40.110,-88.230:600'

# A cut-down Overpass reply: a node, a way (its position is under "center"), and two entries to skip.
REPLY = {'elements': [
    {'type': 'node', 'id': 11, 'lat': 40.1120, 'lon': -88.2300, 'tags': {'name': 'Corner Books', 'shop': 'books'}},
    {'type': 'way', 'id': 22, 'center': {'lat': 40.1110, 'lon': -88.2300},
     'tags': {'name': 'Slice House', 'amenity': 'fast_food'}},
    {'type': 'node', 'id': 33, 'lat': 40.1105, 'lon': -88.2300, 'tags': {'shop': 'bakery'}},       # no name
    {'type': 'way', 'id': 44, 'tags': {'name': 'No Position', 'shop': 'florist'}},                 # no coordinates
]}
PLACES = [
    {'name': 'Corner Books', 'lat': 40.1120, 'lon': -88.2300, 'category': 'bookstore', 'osm_type': 'node', 'osm_id': 11},
    {'name': 'Slice House', 'lat': 40.1110, 'lon': -88.2300, 'category': 'restaurant', 'osm_type': 'way', 'osm_id': 22},
]


def reply(data=REPLY):
    response = mock.Mock()
    response.json.return_value = data
    return response


def cached(places, days_old):
    return OsmQueryCache.objects.create(key=KEY, payload=places, fetched_at=timezone.now() - timedelta(days=days_old))


class NearbyTests(TestCase):
    def test_one_polite_request_then_the_result_is_cached(self):
        with mock.patch('ai.osm.requests.post', return_value=reply()) as post:
            places, unavailable = osm.nearby(LAT, LON, 600)
        self.assertEqual(places, PLACES)
        self.assertFalse(unavailable)
        post.assert_called_once()
        (url,), kwargs = post.call_args
        self.assertEqual(url, 'https://overpass-api.de/api/interpreter')
        self.assertEqual(kwargs['timeout'], 8)
        self.assertEqual(kwargs['headers'], {'User-Agent': 'ShopMates-CoursePilot/1.0 (INFO 490 class project)'})
        query = kwargs['data']['data']
        self.assertIn('node(around:600,40.11,-88.23)["shop"]["name"];', query)
        self.assertIn('way(around:600,40.11,-88.23)["shop"]["name"];', query)
        self.assertIn('["amenity"~"^(cafe|restaurant|fast_food|bar|ice_cream)$"]["name"];', query)
        self.assertTrue(query.rstrip().endswith('out center tags 60;'))
        self.assertEqual(OsmQueryCache.objects.get(key=KEY).payload, PLACES)

    def test_cache_hit_makes_no_call(self):
        cached(PLACES, days_old=6)
        with mock.patch('ai.osm.requests.post') as post:
            self.assertEqual(osm.nearby(LAT, LON, 600), (PLACES, False))
        post.assert_not_called()

    def test_nearby_points_share_one_cache_entry(self):
        cached(PLACES, days_old=1)
        with mock.patch('ai.osm.requests.post') as post:
            self.assertEqual(osm.nearby(40.1102, -88.2298, 600), (PLACES, False))
        post.assert_not_called()

    def test_cache_older_than_7_days_is_fetched_again(self):
        cached([], days_old=8)
        with mock.patch('ai.osm.requests.post', return_value=reply()) as post:
            self.assertEqual(osm.nearby(LAT, LON, 600), (PLACES, False))
        post.assert_called_once()
        entry = OsmQueryCache.objects.get(key=KEY)
        self.assertEqual(entry.payload, PLACES)
        self.assertLess(timezone.now() - entry.fetched_at, timedelta(minutes=1))

    def test_stale_cache_is_used_when_the_request_fails(self):
        cached(PLACES, days_old=30)
        with mock.patch('ai.osm.requests.post', side_effect=requests.Timeout):
            self.assertEqual(osm.nearby(LAT, LON, 600), (PLACES, False))

    def test_no_cache_and_a_failed_request_gives_nothing_and_the_flag(self):
        bad_status = reply()
        bad_status.raise_for_status.side_effect = requests.HTTPError('504')
        bad_json = reply()
        bad_json.json.side_effect = ValueError('not json')
        for failure in ({'side_effect': requests.ConnectionError}, {'side_effect': requests.Timeout},
                        {'return_value': bad_status}, {'return_value': bad_json},
                        {'return_value': reply({'remark': 'runtime error'})}):
            with mock.patch('ai.osm.requests.post', **failure):
                self.assertEqual(osm.nearby(LAT, LON, 600), ([], True), failure)
        self.assertFalse(OsmQueryCache.objects.exists())


class CategoryTests(SimpleTestCase):
    def test_osm_tags_map_to_our_categories(self):
        cases = [
            ({'amenity': 'cafe'}, 'cafe'),
            ({'amenity': 'restaurant'}, 'restaurant'), ({'amenity': 'fast_food'}, 'restaurant'),
            ({'amenity': 'bar'}, 'restaurant'), ({'amenity': 'ice_cream'}, 'restaurant'),
            ({'shop': 'bakery'}, 'bakery'), ({'shop': 'books'}, 'bookstore'), ({'shop': 'florist'}, 'flowers'),
            ({'shop': 'hairdresser'}, 'salon'), ({'shop': 'beauty'}, 'salon'),
            ({'leisure': 'fitness_centre'}, 'fitness'), ({'leisure': 'sports_centre'}, 'fitness'),
            ({'shop': 'clothes'}, 'retail'), ({'shop': 'bicycle'}, 'retail'),
            ({'amenity': 'bank'}, 'other'), ({}, 'other'),
        ]
        for tags, expected in cases:
            self.assertEqual(osm.category_for(tags), expected, tags)


class DropRegisteredTests(SimpleTestCase):
    def test_same_name_within_50_m_is_dropped(self):
        registered = [Shop(name='Corner Books', latitude=40.1123, longitude=-88.2300)]     # 33 m from the OSM point
        self.assertEqual(osm.drop_registered(PLACES, registered), PLACES[1:])

    def test_name_match_ignores_case_spaces_and_punctuation(self):
        registered = [Shop(name="corner-books!", latitude=40.1120, longitude=-88.2300)]
        self.assertEqual(osm.drop_registered(PLACES, registered), PLACES[1:])

    def test_same_name_further_away_is_kept(self):
        registered = [Shop(name='Corner Books', latitude=40.1130, longitude=-88.2300)]     # 111 m
        self.assertEqual(osm.drop_registered(PLACES, registered), PLACES)

    def test_other_name_at_the_same_spot_is_kept(self):
        registered = [Shop(name='Corner Cafe', latitude=40.1120, longitude=-88.2300)]
        self.assertEqual(osm.drop_registered(PLACES, registered), PLACES)


class RadarWithPlacesTests(SimpleTestCase):
    def test_osm_place_is_scored_like_a_shop_with_no_description_or_hours(self):
        mine = Shop(name='Green Cafe', category='cafe', latitude=LAT, longitude=LON,
                    description='Students and study groups.', hours='Mon-Fri 7am-6pm')
        (r,) = radar(mine, [], 1000, places=PLACES[:1])
        # Same 222 m cafe + bookstore pair as the first pinned test in test_radar.py: 64.
        self.assertEqual(r['score'], 64)
        self.assertFalse(r['registered'])
        self.assertEqual(r['place'], PLACES[0])
        self.assertEqual(r['shop'].name, 'Corner Books')
        self.assertEqual(r['hours_note'], 'hours unknown')
        self.assertEqual(r['audience_note'], 'not enough info')

    def test_registered_shops_are_marked_registered(self):
        mine = Shop(name='Green Cafe', category='cafe', latitude=LAT, longitude=LON)
        other = Shop(name='Pageturner', category='bookstore', latitude=40.1120, longitude=LON)
        (r,) = radar(mine, [other], 1000)
        self.assertTrue(r['registered'])
        self.assertIsNone(r['place'])


@override_settings(RADAR_OSM_ENABLED=True, SITE_URL='https://shop.example.com')
class RadarScreenOsmTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.cafe.latitude, self.cafe.longitude = LAT, LON
        self.cafe.save()
        self.books.latitude, self.books.longitude = 40.1120, LON
        self.books.save()
        self.client.force_login(self.cafe_owner)

    def html(self, post_kwargs, **params):
        with mock.patch('ai.osm.requests.post', **post_kwargs) as self.post:
            return self.client.get(reverse('accounts:radar'), params).content.decode()

    def test_unregistered_shop_gets_an_invite_button_and_no_propose_link(self):
        html = self.html({'return_value': reply({'elements': REPLY['elements'][1:2]})})
        self.assertIn('Slice House', html)
        self.assertIn('data-copy="Hi Slice House, I run Green Cafe nearby. I would like to set up a '
                      'customer-sharing deal with you through ShopMates. Join here: https://shop.example.com/"', html)
        self.assertIn('data-copy-status="radar-copy-status"', html)
        self.assertIn('id="radar-copy-status"', html)
        self.assertEqual(html.count('>Invite</button>'), 1)
        self.assertEqual(html.count('Propose a deal</a>'), 1)      # only the registered Pageturner
        self.assertEqual(html.count('>View</a>'), 1)
        self.assertIn('Not on ShopMates yet', html)
        points = json.loads(re.search(r'<script id="radar-points" type="application/json">(.*?)</script>', html).group(1))
        # cafe + restaurant ("other") prior 0.50, 111 m away: 16.875 + 25.483 + 12.5 = 54.86 -> 55
        self.assertIn({'id': 'way/22', 'name': 'Slice House', 'lat': 40.111, 'lon': -88.23,
                       'score': 55, 'tier': 'Possible', 'registered': False}, points['shops'])
        self.assertNotIn('Showing ShopMates shops only', html)

    def test_overpass_down_and_nothing_cached_shows_the_banner(self):
        html = self.html({'side_effect': requests.Timeout})
        self.assertIn('Showing ShopMates shops only', html)
        self.assertIn('Pageturner', html)
        self.assertNotIn('>Invite</button>', html)

    def test_osm_copy_of_a_registered_shop_is_not_shown_twice(self):
        twin = {'type': 'node', 'id': 55, 'lat': 40.1121, 'lon': LON, 'tags': {'name': 'Pageturner', 'shop': 'books'}}
        me = {'type': 'node', 'id': 66, 'lat': LAT, 'lon': LON, 'tags': {'name': 'Green Cafe', 'amenity': 'cafe'}}
        html = self.html({'return_value': reply({'elements': [twin, me]})})
        self.assertEqual(html.count('<h3>Pageturner</h3>'), 1)
        self.assertNotIn('<h3>Green Cafe</h3>', html)
        self.assertNotIn('>Invite</button>', html)

    def test_category_filter_applies_to_osm_shops_too(self):
        html = self.html({'return_value': reply()}, category='restaurant')
        self.assertIn('Slice House', html)
        self.assertNotIn('Corner Books', html)
        self.assertNotIn('Pageturner', html)

    def test_no_location_makes_no_outside_call(self):
        self.cafe.latitude = self.cafe.longitude = None
        self.cafe.save()
        self.html({'return_value': reply()})
        self.post.assert_not_called()

    @override_settings(RADAR_OSM_ENABLED=False)
    def test_switched_off_makes_no_outside_call_and_shows_no_banner(self):
        html = self.html({'return_value': reply()})
        self.post.assert_not_called()
        self.assertNotIn('Showing ShopMates shops only', html)
        self.assertNotIn('Slice House', html)


class SettingTests(SimpleTestCase):
    def test_setting_exists_and_is_listed_in_env_example(self):
        self.assertIsInstance(settings.RADAR_OSM_ENABLED, bool)
        with open(settings.BASE_DIR / '.env.example') as f:
            self.assertIn('RADAR_OSM_ENABLED=', f.read())
