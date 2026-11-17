from django.test import SimpleTestCase

from accounts.forms import ShopForm
from accounts.models import Shop
from ai.radar import radar, tier

# All test shops share one longitude, so the distance is just the latitude gap:
# 0.001 degrees of latitude = 6,371,071 m (the earth radius in accounts/geo.py)
# x pi / 180,000 = 111.196 m.
LON = -88.2300


def shop(name, category, lat=40.1100, lon=LON, description='', hours=''):
    return Shop(name=name, category=category, latitude=lat, longitude=lon, description=description, hours=hours)


class RadarScoreTests(SimpleTestCase):
    def one(self, mine, other, radius_m=1000):
        return radar(mine, [other], radius_m)[0]

    def test_cafe_and_bookstore_two_blocks_apart(self):
        # distance 0.002 deg = 222.39 m; walk_minutes = 222.39 x 1.3 / 80 = 3.614
        # fit   = 0.90 x (0.5 + 0.5 x 0.5) = 0.675
        # walk  = 1 - 3.614 / 12           = 0.6988
        # hours = 0.5
        # score = 100 x (0.45 x 0.675 + 0.30 x 0.6988 + 0.25 x 0.5)
        #       = 30.375 + 20.965 + 12.5 = 63.84 -> 64
        r = self.one(shop('Green Cafe', 'cafe'), shop('Pageturner', 'bookstore', lat=40.1120))
        self.assertEqual(r['score'], 64)
        self.assertEqual(r['walk_minutes'], 4)
        self.assertEqual(r['tier'], 'Good')
        self.assertEqual(r['reason'], '4 min walk, cafe + books are complementary')
        self.assertEqual(r['hours_note'], 'hours unknown')

    def test_two_cafes_next_door(self):
        # distance 0.001 deg = 111.196 m; walk_minutes = 111.196 x 1.3 / 80 = 1.807
        # fit   = 0.10 x 0.75      = 0.075
        # walk  = 1 - 1.807 / 12   = 0.8494
        # score = 3.375 + 25.483 + 12.5 = 41.36 -> 41
        r = self.one(shop('Green Cafe', 'cafe'), shop('Brew Lab', 'cafe', lat=40.1110))
        self.assertEqual(r['score'], 41)
        self.assertEqual(r['walk_minutes'], 2)
        self.assertEqual(r['tier'], 'Possible')
        self.assertEqual(r['reason'], '2 min walk, cafe + cafe compete for the same customers')

    def test_clothing_and_salon_a_longer_walk(self):
        # distance 0.005 deg = 555.98 m; walk_minutes = 555.98 x 1.3 / 80 = 9.035
        # fit   = 0.80 x 0.75      = 0.600
        # walk  = 1 - 9.035 / 12   = 0.2471
        # score = 27.0 + 7.413 + 12.5 = 46.91 -> 47
        r = self.one(shop('Thread', 'retail'), shop('Shear Joy', 'salon', lat=40.1150))
        self.assertEqual(r['score'], 47)
        self.assertEqual(r['walk_minutes'], 9)
        self.assertEqual(r['tier'], 'Possible')

    def test_restaurant_and_flowers_count_as_other(self):
        # other + other prior is 0.30: 100 x (0.45 x 0.225 + 0.30 x 0.8494 + 0.125) = 48.11 -> 48
        r = self.one(shop('Diner', 'restaurant'), shop('Petals', 'flowers', lat=40.1110))
        self.assertEqual(r['score'], 48)

    def test_cafe_and_bookstore_that_both_describe_students(self):
        # Words kept (3+ letters, stop words such as "and" and "mostly" dropped), category first:
        #   mine   = cafe, students x2, study, groups
        #   theirs = bookstore, study, groups, students
        # idf = ln((1 + 2 shops) / (1 + shops using the word)) + 1
        #   in both shops: ln(3/3) + 1 = 1         in one shop: ln(3/2) + 1 = 1.4055
        # weights (count x idf): mine cafe 1.4055, students 2, study 1, groups 1; theirs bookstore 1.4055, rest 1
        # lengths: mine sqrt(1.9753 + 4 + 1 + 1) = 2.8241; theirs sqrt(1.9753 + 3) = 2.2305
        # similarity = (2 + 1 + 1) / (2.8241 x 2.2305) = 0.6350
        # fit   = 0.90 x (0.5 + 0.5 x 0.6350) = 0.7358
        # walk  = 0.6988 (same 222 m as the first test), hours = 0.5
        # score = 33.109 + 20.965 + 12.5 = 66.57 -> 67
        mine = shop('Green Cafe', 'cafe', description='Students and study groups, mostly students.')
        other = shop('Pageturner', 'bookstore', lat=40.1120, description='Study groups of students.')
        r = self.one(mine, other)
        self.assertEqual(r['score'], 67)
        # "students" has the highest shared weight (2 x 1); "groups" and "study" are 1 x 1.
        self.assertEqual(r['reason'], '4 min walk, cafe + books are complementary, both mention students')
        self.assertEqual(r['audience_note'], '')

    def test_shared_word_ties_go_to_the_first_in_the_alphabet(self):
        mine = shop('Green Cafe', 'cafe', description='Students and study groups.')
        other = shop('Pageturner', 'bookstore', lat=40.1120, description='Study groups of students.')
        self.assertTrue(self.one(mine, other)['reason'].endswith(', both mention groups'))

    def test_different_descriptions_lower_fit_and_add_no_clause(self):
        # No shared word: similarity 0, fit = 0.90 x 0.5 = 0.45
        # score = 20.25 + 20.965 + 12.5 = 53.72 -> 54
        mine = shop('Green Cafe', 'cafe', description='Quiet espresso bar for commuters.')
        other = shop('Pageturner', 'bookstore', lat=40.1120, description='Used novels, families welcome.')
        r = self.one(mine, other)
        self.assertEqual(r['score'], 54)
        self.assertEqual(r['reason'], '4 min walk, cafe + books are complementary')

    def test_one_missing_description_means_not_enough_info(self):
        mine = shop('Green Cafe', 'cafe', description='Students and study groups.')
        r = self.one(mine, shop('Pageturner', 'bookstore', lat=40.1120))
        self.assertEqual(r['score'], 64)                       # same as with no descriptions at all
        self.assertEqual(r['audience_note'], 'not enough info')
        self.assertNotIn('mention', r['reason'])
        self.assertNotIn('audience', r['reason'])

    def test_hours_that_fully_overlap(self):
        # Cafe Mon-Fri 7am-6pm = 55 h; bookstore Mon-Sun 7am-8pm = 91 h; open together 55 h.
        # hours = 55 / min(55, 91) = 1.0
        # score = 30.375 + 20.965 + 25.0 = 76.34 -> 76
        r = self.one(shop('Green Cafe', 'cafe', hours='Mon-Fri 7am-6pm'),
                     shop('Pageturner', 'bookstore', lat=40.1120, hours='Mon-Sun 7am-8pm'))
        self.assertEqual(r['score'], 76)
        self.assertEqual(r['hours_note'], 'open together 55 h/week')
        self.assertEqual(r['reason'], '4 min walk, open together 55 h/week, cafe + books are complementary')

    def test_hours_that_partly_overlap(self):
        # Mon-Fri 9am-5pm and Wed-Sun 12pm-8pm are 40 h each and share 15 h.
        # hours = 15 / 40 = 0.375
        # score = 30.375 + 20.965 + 9.375 = 60.72 -> 61
        r = self.one(shop('Green Cafe', 'cafe', hours='Mon-Fri 9am-5pm'),
                     shop('Pageturner', 'bookstore', lat=40.1120, hours='Wed-Sun 12pm-8pm'))
        self.assertEqual(r['score'], 61)
        self.assertEqual(r['hours_note'], 'open together 15 h/week')

    def test_hours_that_cannot_be_read_count_as_unknown(self):
        r = self.one(shop('Green Cafe', 'cafe', hours='Mon-Fri 7am-6pm'),
                     shop('Pageturner', 'bookstore', lat=40.1120, hours='Mon-Fri 7-6'))
        self.assertEqual(r['score'], 64)
        self.assertEqual(r['hours_note'], 'hours unknown')
        self.assertEqual(r['reason'], '4 min walk, cafe + books are complementary')

    def test_tier_words(self):
        self.assertEqual([tier(s) for s in (80, 79, 60, 59)], ['Great', 'Good', 'Good', 'Possible'])


class RadarListTests(SimpleTestCase):
    def setUp(self):
        self.mine = shop('Green Cafe', 'cafe')
        self.near = shop('Pageturner', 'bookstore', lat=40.1120)    # 222 m
        self.far = shop('Far Books', 'bookstore', lat=40.1150)      # 556 m

    def test_same_inputs_give_the_same_output(self):
        candidates = [self.far, self.near]
        self.assertEqual(radar(self.mine, candidates, 1000), radar(self.mine, candidates, 1000))

    def test_sorted_by_score_then_name(self):
        twin = shop('Alpha Books', 'bookstore', lat=40.1120)
        names = [r['shop'].name for r in radar(self.mine, [self.far, self.near, twin], 1000)]
        self.assertEqual(names, ['Alpha Books', 'Pageturner', 'Far Books'])

    def test_candidate_without_coordinates_is_left_out(self):
        nowhere = shop('Nowhere', 'bookstore', lat=None, lon=None)
        self.assertEqual([r['shop'] for r in radar(self.mine, [nowhere, self.near], 1000)], [self.near])

    def test_my_shop_without_coordinates_gives_nothing(self):
        self.assertEqual(radar(shop('Me', 'cafe', lat=None, lon=None), [self.near], 1000), [])

    def test_radius_keeps_only_shops_inside_it(self):
        self.assertEqual([r['shop'] for r in radar(self.mine, [self.near, self.far], 300)], [self.near])
        self.assertEqual(len(radar(self.mine, [self.near, self.far], 600)), 2)


class ShopDescriptionTests(SimpleTestCase):
    def test_shop_form_has_an_optional_description(self):
        field = ShopForm().fields['description']
        self.assertFalse(field.required)
        self.assertEqual(field.max_length, 300)
