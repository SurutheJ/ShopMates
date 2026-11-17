from django.test import SimpleTestCase

from ai.hours import open_minutes, overlap_minutes, parse_hours

MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


class ParseHoursTests(SimpleTestCase):
    def test_day_range(self):
        self.assertEqual(parse_hours('Mon-Fri 7am-6pm'), {d: [(420, 1080)] for d in range(MON, SAT)})

    def test_whole_week(self):
        self.assertEqual(parse_hours('Mon-Sun 7am-8pm'), {d: [(420, 1200)] for d in range(7)})

    def test_single_day_with_half_hours(self):
        self.assertEqual(parse_hours('Sat 7:30am-12:15pm'), {SAT: [(450, 735)]})

    def test_comma_list_of_days(self):
        self.assertEqual(parse_hours('Mon, Wed, Fri 9am-5pm'), {d: [(540, 1020)] for d in (MON, WED, FRI)})

    def test_24_hour_times_and_the_word_to(self):
        self.assertEqual(parse_hours('Tue 09:00 to 18:00'), {TUE: [(540, 1080)]})

    def test_segments_split_by_semicolon_or_comma(self):
        expected = {d: [(420, 1080)] for d in range(MON, SAT)}
        expected[SAT] = [(540, 840)]
        self.assertEqual(parse_hours('Mon-Fri 7am-6pm; Sat 9am-2pm'), expected)
        self.assertEqual(parse_hours('Mon-Fri 7am-6pm, Sat 9am-2pm'), expected)

    def test_full_day_names_capitals_and_extra_spaces(self):
        self.assertEqual(parse_hours('  MONDAY - friday   7 AM - 6 PM '), {d: [(420, 1080)] for d in range(MON, SAT)})

    def test_noon_and_midnight(self):
        self.assertEqual(parse_hours('Sun 12am-12pm'), {SUN: [(0, 720)]})

    def test_same_day_twice_keeps_both_spans(self):
        self.assertEqual(parse_hours('Mon 9am-12pm; Mon 1pm-5pm'), {MON: [(540, 720), (780, 1020)]})

    def test_empty_text_is_none(self):
        self.assertIsNone(parse_hours(''))
        self.assertIsNone(parse_hours('   '))

    def test_time_without_am_or_pm_is_none(self):
        self.assertIsNone(parse_hours('Mon-Fri 7-6'))

    def test_words_it_does_not_know_are_none(self):
        self.assertIsNone(parse_hours('Open daily'))
        self.assertIsNone(parse_hours('Mon-Fri 7am-6pm, closed weekends'))
        self.assertIsNone(parse_hours('7am-6pm'))

    def test_impossible_times_are_none(self):
        self.assertIsNone(parse_hours('Mon 13pm-5pm'))
        self.assertIsNone(parse_hours('Mon 9:75am-5pm'))
        self.assertIsNone(parse_hours('Mon 25:00-26:00'))

    def test_closing_before_opening_is_none(self):
        self.assertIsNone(parse_hours('Fri 6pm-2am'))


class OverlapTests(SimpleTestCase):
    def test_weekday_shop_inside_an_all_week_shop(self):
        # A: Mon-Fri 7am-6pm = 5 x 11 h = 55 h. B: Mon-Sun 7am-8pm = 7 x 13 h = 91 h.
        # Open together: all of A's hours = 55 h = 3,300 minutes.
        a, b = parse_hours('Mon-Fri 7am-6pm'), parse_hours('Mon-Sun 7am-8pm')
        self.assertEqual((open_minutes(a), open_minutes(b)), (3300, 5460))
        self.assertEqual(overlap_minutes(a, b), 3300)

    def test_shops_that_share_three_afternoons(self):
        # A: Mon-Fri 9am-5pm = 40 h. B: Wed-Sun 12pm-8pm = 40 h.
        # Open together: Wed, Thu, Fri from 12pm to 5pm = 3 x 5 h = 15 h = 900 minutes.
        a, b = parse_hours('Mon-Fri 9am-5pm'), parse_hours('Wed-Sun 12pm-8pm')
        self.assertEqual(overlap_minutes(a, b), 900)
        self.assertEqual(overlap_minutes(b, a), 900)
