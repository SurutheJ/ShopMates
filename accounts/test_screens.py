import json
import re

from django.conf import settings
from django.templatetags.static import static
from django.test import override_settings
from django.urls import reverse

from deals.tests.helpers import DealTestCase, make_shop


class DiscoverScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.cafe.latitude, self.cafe.longitude = 40.1100, -88.2300
        self.cafe.save()
        self.books.latitude, self.books.longitude = 40.1110, -88.2310
        self.books.save()
        self.client.force_login(self.cafe_owner)

    def html(self, **params):
        return self.client.get(reverse('accounts:discover'), params).content.decode()

    def test_head_search_and_sort_button_follow_the_design(self):
        html = self.html()
        self.assertIn('<h1>Find a neighbor</h1>', html)
        self.assertIn('placeholder="Search name or street"', html)
        self.assertIn('data-sheet="sheet-sort"', html)

    def test_header_actions_sit_side_by_side(self):
        self.assertIn('<div class="head-actions"><a class="icon-btn"', self.html())

    def test_tile_shows_keywords_and_opens_to_the_full_reasons_and_a_view_button(self):
        html = self.html()
        tile = html[html.index('<details class="tile">'):html.index('</details>')]
        self.assertIn('<summary class="row">', tile)
        self.assertRegex(tile, r'<p class="sm reason"[^>]*>[^<]*Readers \+ coffee')      # short keywords on the closed tile
        more = tile[tile.index('class="more"'):]
        self.assertIn('Readers linger over coffee', more)                                # the full sentence inside
        self.assertIn('<a class="btn ghost sm" href="%s">View shop</a>' % self.books.get_absolute_url(), more)
        self.assertNotIn('<a class="row"', html)                                         # the tile is no longer one big link

    def test_radar_is_a_small_icon_button_not_a_text_button(self):
        html = self.html()
        radar_url = reverse('accounts:radar')
        self.assertRegex(html, r'<a class="icon-btn" href="%s" aria-label="Deal Radar"[^>]*><svg class="i" aria-hidden="true"><use href="#i-radar"/></svg></a>' % radar_url)
        self.assertNotIn('>Radar</a>', html)
        self.assertIn('id="i-radar"', html)

    def test_category_chips_start_with_all_and_mark_the_current_one(self):
        html = self.html(category='bookstore')
        chips = re.findall(r'<a class="chip"([^>]*)>([^<]+)</a>', html)
        self.assertEqual(chips[0][1], 'All')
        current = [label for attrs, label in chips if 'aria-current="true"' in attrs]
        self.assertEqual(current, ['Bookstore'])
        self.assertIn('Flowers', [label for _, label in chips])   # not "Flowers and gifts"

    def test_chips_keep_the_search_and_sort(self):
        html = self.html(q='page', sort='distance')
        self.assertRegex(html, r'href="\?category=cafe&amp;q=page&amp;sort=distance"')

    def test_sort_sheet_has_a_radio_per_sort_and_keeps_the_filters(self):
        html = self.html(q='page', category='bookstore', sort='distance')
        sheet = html[html.index('id="sheet-sort"'):]
        self.assertRegex(sheet, r'<input type="radio" name="sort" value="distance" checked>')
        self.assertRegex(sheet, r'<input type="radio" name="sort" value="match">')
        self.assertIn('name="q" value="page"', sheet)
        self.assertIn('name="category" value="bookstore"', sheet)

    def test_result_is_a_design_row_with_tinted_avatar_tag_distance_and_score_badge(self):
        html = self.html()
        self.assertIn('class="row"', html)
        self.assertIn('avatar cat--bookstore', html)
        self.assertIn('tag cat--bookstore">Bookstore<', html)
        self.assertRegex(html, r'\d\.\d mi')
        self.assertRegex(html, r'class="badge [a-z]*">\d+ &middot; (Great|Good|Possible)<')

    def test_card_line_has_no_spend_it_is_on_the_shop_page(self):
        """Name, category, distance, score and one reason are enough on a card; spend wrapped badly on narrow cards."""
        self.assertNotIn('&middot; spend $', self.html())

    def test_distance_stays_in_one_piece_so_it_wraps_instead_of_being_cut(self):
        self.assertRegex(self.html(), r'<span class="nowrap">\d\.\d mi</span>')

    def test_results_sit_in_the_one_scroll_region_two_per_row(self):
        self.assertIn('class="scroll cols-2 discover"', self.html())

    def test_no_match_shows_the_empty_state_with_a_way_back(self):
        html = self.html(q='zzzz')
        self.assertIn('class="empty"', html)
        self.assertIn('No shops found', html)

    def test_unapproved_shop_gets_a_banner_but_can_browse(self):
        self.cafe.status = self.cafe.Status.PENDING
        self.cafe.save()
        html = self.html()
        self.assertIn('class="banner', html)
        self.assertIn('waiting for approval', html)


class ShopScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.cafe.latitude, self.cafe.longitude = 40.1100, -88.2300
        self.cafe.save()
        self.books.latitude, self.books.longitude = 40.1110, -88.2310
        self.books.save()
        self.client.force_login(self.cafe_owner)

    def html(self, shop):
        return self.client.get(shop.get_absolute_url()).content.decode()

    def test_back_button_and_report_marked_coming_soon(self):
        html = self.html(self.books)
        self.assertRegex(html, r'<a class="btn back" href="%s">' % reverse('accounts:discover'))
        self.assertIn('data-soon="Report and block"', html)

    def test_header_has_avatar_name_tag_and_address(self):
        html = self.html(self.books)
        self.assertIn('avatar lg cat--bookstore', html)
        self.assertIn('<h1>Pageturner</h1>', html)
        self.assertIn('tag cat--bookstore">Bookstore<', html)
        self.assertIn('1 Pageturner St', html)

    def test_three_stat_tiles_match_miles_and_spend(self):
        html = self.html(self.books)
        tiles = re.findall(r'<div class="stat[^"]*"><b>([^<]+)</b><span>([^<]+)</span>', html)
        self.assertEqual([label for _, label in tiles], ['match', 'miles', 'typical spend'])
        self.assertEqual(tiles[2][0], '$20')

    def test_why_this_match_card_lists_the_reasons(self):
        html = self.html(self.books)
        self.assertIn('<h3>Why this match</h3>', html)
        self.assertIn('Computed from your shop profiles, no AI involved', html)

    def test_propose_a_deal_is_in_the_pinned_action_bar(self):
        html = self.html(self.books)
        self.assertRegex(html, r'<div class="actionbar">\s*<a class="btn block" href="%s">Propose a deal</a>' % reverse('deals:new', args=[self.books.pk]))

    def test_your_own_shop_has_no_report_and_no_propose(self):
        html = self.html(self.cafe)
        self.assertNotIn('Report and block', html)
        self.assertNotIn('Propose a deal', html)
        self.assertIn('this is your shop', html)

    def test_distance_unknown_shows_a_dash_not_a_number(self):
        far = make_shop('No Coords', category='retail')
        html = self.html(far)
        tiles = re.findall(r'<div class="stat[^"]*"><b>([^<]+)</b><span>([^<]+)</span>', html)
        self.assertEqual(dict((label, value) for value, label in tiles)['miles'], '–')


@override_settings(RADAR_OSM_ENABLED=False)    # no test here may reach OpenStreetMap; ai/test_osm.py covers that part with a fake
class RadarScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.cafe.latitude, self.cafe.longitude = 40.1100, -88.2300
        self.cafe.save()
        self.books.latitude, self.books.longitude = 40.1120, -88.2300   # 222 m north
        self.books.save()
        self.client.force_login(self.cafe_owner)

    def get(self, **params):
        return self.client.get(reverse('accounts:radar'), params)

    def test_walk_time_is_said_once_per_card_in_the_reason_line(self):
        html = self.get().content.decode()
        self.assertEqual(html.count('4 min walk'), 1)

    def test_owner_sees_a_scored_card_with_view_and_propose_buttons(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<h1>Deal Radar</h1>', html)
        self.assertIn('Pageturner', html)
        self.assertIn('64 &middot; Good', html)
        self.assertIn('4 min walk, cafe + books are complementary', html)
        # Touch targets: the name is plain text; the two actions are 44px ghost buttons.
        self.assertIn('<h3>Pageturner</h3>', html)
        self.assertIn('<a class="btn ghost sm" href="%s">View</a>' % self.books.get_absolute_url(), html)
        self.assertIn('<a class="btn ghost sm" href="%s">Propose a deal</a>'
                      % reverse('deals:new', args=[self.books.pk]), html)

    def test_view_and_propose_share_one_line_spanning_the_whole_tile(self):
        """The button row is a child of the tile (full width), not of the narrow text column."""
        html = self.get().content.decode()
        row = html[html.index('<div class="row"'):]
        self.assertRegex(row, r'</div>\s*<span class="badge[^>]*>[^<]*</span>\s*<div class="radar-actions">\s*<a class="btn ghost sm" href="[^"]*">View</a>\s*<a class="btn ghost sm" href="[^"]*">Propose a deal</a>\s*</div>')

    def test_card_shows_hours_together_and_shared_words(self):
        self.cafe.hours, self.cafe.description = 'Mon-Fri 7am-6pm', 'Students and study groups, mostly students.'
        self.cafe.save()
        self.books.hours, self.books.description = 'Mon-Sun 7am-8pm', 'Study groups of students.'
        self.books.save()
        html = self.get().content.decode()
        # fit 0.7358 (see ai/test_radar.py), walk 0.6988, hours 1.0: 33.109 + 20.965 + 25.0 = 79.07 -> 79
        self.assertIn('79 &middot; Good', html)
        self.assertIn('4 min walk, open together 55 h/week, cafe + books are complementary, both mention students', html)
        self.assertNotIn('not enough info', html)

    def test_missing_description_is_marked_not_enough_info(self):
        html = self.get().content.decode()
        self.assertIn('hours unknown', html)
        self.assertIn('audience: not enough info', html)

    def test_category_filter_does_not_change_a_score(self):
        self.cafe.description = 'Students and study groups.'
        self.cafe.save()
        self.books.description = 'Study groups of students.'
        self.books.save()
        make_shop('Trim', category='salon', latitude=40.1110, longitude=-88.2300, description='Students welcome.')
        score = r'\d+ &middot; \w+</span>'
        every = dict(zip(re.findall(r'<h3>([^<]+)</h3>', self.get().content.decode()),
                         re.findall(score, self.get().content.decode())))
        only_books = self.get(category='bookstore').content.decode()
        self.assertEqual(re.findall(score, only_books), [every['Pageturner']])

    def test_anonymous_user_is_sent_to_login(self):
        self.client.logout()
        response = self.get()
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response.url)

    def test_radius_chips_default_to_600_and_mark_the_chosen_one(self):
        self.assertRegex(self.get().content.decode(), r'radius=600[^>]*aria-current="true"')
        self.assertRegex(self.get(radius='300').content.decode(), r'radius=300[^>]*aria-current="true"')
        self.assertRegex(self.get(radius='9999').content.decode(), r'radius=600[^>]*aria-current="true"')

    def test_radius_leaves_out_shops_that_are_too_far(self):
        self.books.latitude = 40.1150   # 556 m
        self.books.save()
        self.assertNotIn('Pageturner', self.get(radius='300').content.decode())
        self.assertIn('Pageturner', self.get(radius='600').content.decode())

    def test_category_filter(self):
        self.assertNotIn('Pageturner', self.get(category='salon').content.decode())
        self.assertIn('Pageturner', self.get(category='bookstore').content.decode())

    def test_few_results_suggest_a_larger_radius(self):
        self.assertIn('Try a larger radius', self.get().content.decode())

    def test_no_location_shows_a_message_instead_of_results(self):
        self.cafe.latitude = self.cafe.longitude = None
        self.cafe.save()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Add your shop location', html)
        self.assertIn('href="%s"' % reverse('accounts:shop_edit'), html)
        self.assertNotIn('Pageturner', html)

    def test_unapproved_shop_gets_a_banner_and_no_propose_link_like_discover(self):
        self.cafe.status = self.cafe.Status.PENDING
        self.cafe.save()
        html = self.get().content.decode()
        self.assertIn('waiting for approval', html)
        self.assertIn('Pageturner', html)
        self.assertNotIn('Propose a deal', html)
        self.assertIn('>View</a>', html)

    def test_map_files_load_from_this_site_with_no_inline_script(self):
        html = self.get().content.decode()
        self.assertIn('<link rel="stylesheet" href="%s">' % static('vendor/leaflet/leaflet.css'), html)
        self.assertIn('<script src="%s" defer></script>' % static('vendor/leaflet/leaflet.js'), html)
        self.assertIn('<script src="%s" defer></script>' % static('js/radar_map.js'), html)
        self.assertLess(html.index('leaflet.js'), html.index('radar_map.js'))    # Leaflet must run first
        # The only script tag without src is the JSON data block, which a browser never runs.
        self.assertEqual(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>', html),
                         ['<script id="radar-points" type="application/json">'])
        self.assertIn('<div id="radar-map" role="img" '
                      'aria-label="Map of nearby shops. The list shows the same shops."></div>', html)

    def test_map_points_match_the_list(self):
        html = self.get().content.decode()
        points = json.loads(re.search(r'<script id="radar-points" type="application/json">(.*?)</script>', html).group(1))
        self.assertEqual(points, {
            'me': {'name': 'Green Cafe', 'lat': 40.11, 'lon': -88.23},
            'shops': [{'id': self.books.pk, 'name': 'Pageturner', 'lat': 40.112, 'lon': -88.23,
                       'score': 64, 'tier': 'Good', 'registered': True}],
        })

    def test_no_location_means_no_map(self):
        self.cafe.latitude = self.cafe.longitude = None
        self.cafe.save()
        html = self.get().content.decode()
        self.assertNotIn('radar-map', html)
        self.assertNotIn('radar-points', html)

    def test_map_tiles_are_allowed_by_the_content_security_policy(self):
        policy = self.get()['Content-Security-Policy']
        img_src = [p for p in policy.split('; ') if p.startswith('img-src')][0]
        self.assertEqual(img_src, "img-src 'self' data: https://tile.openstreetmap.org")

    def test_map_script_and_styles(self):
        script = (settings.BASE_DIR / 'static/js/radar_map.js').read_text()
        self.assertIn("'https://tile.openstreetmap.org/{z}/{x}/{y}.png'", script)
        self.assertIn('maxZoom: 19', script)
        self.assertIn('\u00a9 OpenStreetMap contributors', script)
        self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', script))      # colours come from tokens.css, not from new hex values
        css = (settings.BASE_DIR / 'static/css/app.css').read_text()
        self.assertEqual(css.count('/* Deal Radar map */'), 1)

    def test_discover_header_links_to_radar(self):
        html = self.client.get(reverse('accounts:discover')).content.decode()
        self.assertIn('href="%s" aria-label="Deal Radar"' % reverse('accounts:radar'), html)   # now an icon button
