from django.test import SimpleTestCase

from accounts.models import Shop


class CategoryShortTests(SimpleTestCase):
    def test_long_labels_are_cut_to_the_first_word_for_tags_and_chips(self):
        self.assertEqual(Shop(category='flowers').category_short, 'Flowers')
        self.assertEqual(Shop(category='salon').category_short, 'Salon')

    def test_short_labels_stay_as_they_are(self):
        self.assertEqual(Shop(category='cafe').category_short, 'Cafe')
        self.assertEqual(Shop(category='bookstore').category_short, 'Bookstore')


class ShopInitialsTests(SimpleTestCase):
    def test_two_words_give_two_letters(self):
        self.assertEqual(Shop(name='Rise Bakery').initials, 'RB')

    def test_more_words_use_the_first_two(self):
        self.assertEqual(Shop(name='Green Street Cafe').initials, 'GS')

    def test_one_word_gives_its_first_two_letters(self):
        self.assertEqual(Shop(name='Pageturner').initials, 'PA')

    def test_letters_are_upper_case_and_punctuation_is_skipped(self):
        self.assertEqual(Shop(name="& joe's diner").initials, 'JD')

    def test_a_blank_name_gives_a_question_mark(self):
        self.assertEqual(Shop(name='').initials, '?')
