"""My shop and Staff screens in the designv2 look."""
import re

from django.urls import reverse

from accounts.models import ShopMembership
from deals.tests.helpers import DealTestCase, make_user


class FormStyleTests(DealTestCase):
    def test_shop_and_staff_fields_use_the_design_input_class(self):
        from accounts.forms import ShopForm, StaffAddForm
        for form in (ShopForm(), StaffAddForm()):
            for name, field in form.fields.items():
                self.assertIn('input', field.widget.attrs.get('class', '').split(), name)


class MyShopScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cafe_owner)

    def html(self):
        return self.client.get(reverse('accounts:shop_edit')).content.decode()

    def test_head_has_the_status_badge_and_three_tabs(self):
        html = self.html()
        self.assertEqual(html.count('<h1>'), 1)
        self.assertIn('<h1>My shop</h1>', html)
        self.assertIn('class="badge ok"', html)
        tabs = re.findall(r'<button role="tab"[^>]*>([^<]+)</button>', html)
        self.assertEqual(tabs, ['Profile', 'Team', 'Account'])

    def test_profile_pane_shows_the_shop_facts_and_pitch_tags_coming_soon(self):
        html = self.html()
        self.assertIn('class="kv"', html)
        self.assertIn(self.cafe.address, html)
        self.assertIn('data-soon="Pitch and tags"', html)
        self.assertIn('data-sheet="sheet-edit"', html)

    def test_edit_sheet_holds_the_real_form_with_save(self):
        html = self.html()
        sheet = html[html.index('id="sheet-edit"'):]
        self.assertIn('csrfmiddlewaretoken', sheet)
        self.assertIn('name="name"', sheet)
        self.assertIn('name="margin_pct"', sheet)
        self.assertRegex(sheet, r'<button class="btn" type="submit" form="shop-form">Save changes</button>')
        self.assertNotIn('sheet-backdrop open', html)

    def test_invalid_save_reopens_the_sheet_with_the_error(self):
        response = self.client.post(reverse('accounts:shop_edit'), {'name': '', 'category': 'cafe', 'address': 'x', 'city': 'x', 'typical_order_value': '9'})
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('sheet-backdrop open', html)
        self.assertIn('class="error"', html)

    def test_valid_save_still_updates_and_redirects(self):
        data = {'name': 'Green Cafe 2', 'category': 'cafe', 'address': '1 Main', 'city': 'Champaign', 'typical_order_value': '9'}
        self.assertRedirects(self.client.post(reverse('accounts:shop_edit'), data), reverse('accounts:shop_edit'))
        self.cafe.refresh_from_db()
        self.assertEqual(self.cafe.name, 'Green Cafe 2')

    def test_team_pane_links_to_the_staff_page(self):
        self.assertIn(f'href="{reverse("accounts:shop_staff")}"', self.html())

    def test_account_pane_has_stats_log_out_and_the_missing_features_as_coming_soon(self):
        html = self.html()
        self.assertIn(f'href="{reverse("deals:stats")}"', html)
        self.assertIn(f'<form method="post" action="{reverse("account_logout")}"', html)
        for label in ('Download my data', 'Delete account', 'Terms and Privacy', 'Email notifications'):
            self.assertIn(label, html)
        self.assertEqual(html.count('data-soon="Email notifications"'), 2)

    def test_setup_page_is_one_form_with_a_pinned_create_button(self):
        self.client.force_login(make_user('fresh3'))
        html = self.client.get(reverse('accounts:shop_create')).content.decode()
        self.assertIn('<h1>Set up your shop</h1>', html)
        bar = html[html.index('class="actionbar"'):]
        self.assertRegex(bar, r'<button class="btn" type="submit" form="shop-form">Create shop</button>')
        self.assertNotIn('role="tab"', html)


class StaffScreenTests(DealTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cafe_owner)

    def html(self):
        return self.client.get(reverse('accounts:shop_staff')).content.decode()

    def test_head_and_back_link(self):
        html = self.html()
        self.assertIn('<h1>Staff</h1>', html)
        self.assertIn(f'href="{reverse("accounts:shop_edit")}"', html)

    def test_owner_row_has_no_remove_and_staff_row_has_a_remove_post_form(self):
        staff = make_user('cafe_staff2')
        membership = ShopMembership.objects.create(user=staff, shop=self.cafe, role=ShopMembership.Role.STAFF)
        html = self.html()
        self.assertEqual(html.count('class="row"'), 2)
        self.assertIn('cafe_staff2', html)
        self.assertEqual(html.count('Remove</button>'), 1)
        self.assertIn(f'action="{reverse("accounts:shop_staff_remove", args=[membership.pk])}"', html)

    def test_add_form_and_pinned_add_button(self):
        html = self.html()
        self.assertIn('name="identifier"', html)
        bar = html[html.index('class="actionbar"'):]
        self.assertRegex(bar, r'<button class="btn" type="submit" form="staff-form">Add staff</button>')
        self.assertIn('id="staff-form"', html)
