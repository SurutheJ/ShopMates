from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.geo import haversine_miles
from accounts.models import Shop, ShopMembership

User = get_user_model()
PASSWORD = 'test-pass-12345'

SHOP_FORM = {
    'name': 'Green Cafe', 'category': 'cafe', 'address': '1 Green St', 'city': 'Champaign',
    'hours': 'Mon-Fri 7-6', 'typical_order_value': '9.50', 'latitude': '', 'longitude': '',
}


def user(name):
    return User.objects.create_user(name, f'{name}@example.com', PASSWORD)


class GeoTests(SimpleTestCase):
    def test_known_distance(self):
        # Champaign to Urbana city centers are roughly 2 miles apart.
        miles = haversine_miles(40.1164, -88.2434, 40.1106, -88.2073)
        self.assertTrue(1.5 < miles < 3.0, miles)

    def test_same_point_is_zero(self):
        self.assertAlmostEqual(haversine_miles(40, -88, 40, -88), 0)


class ShopSetupTests(TestCase):
    def setUp(self):
        self.owner = user('owner')
        self.client.force_login(self.owner)

    @override_settings(SHOPS_AUTO_APPROVE=True)
    def test_creating_a_shop_makes_the_user_its_owner(self):
        response = self.client.post(reverse('accounts:shop_create'), SHOP_FORM)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        shop = Shop.objects.get()
        self.assertEqual(shop.status, Shop.Status.APPROVED)
        membership = ShopMembership.objects.get()
        self.assertEqual((membership.user, membership.role), (self.owner, ShopMembership.Role.OWNER))

    @override_settings(SHOPS_AUTO_APPROVE=False)
    def test_new_shops_wait_for_admin_approval_when_auto_approve_is_off(self):
        self.client.post(reverse('accounts:shop_create'), SHOP_FORM)
        self.assertEqual(Shop.objects.get().status, Shop.Status.PENDING)

    def test_one_coordinate_without_the_other_is_rejected(self):
        response = self.client.post(reverse('accounts:shop_create'), {**SHOP_FORM, 'latitude': '40.1'})
        self.assertEqual(Shop.objects.count(), 0)
        self.assertContains(response, 'both latitude and longitude')

    def test_a_user_with_a_shop_is_sent_to_edit_instead(self):
        self.client.post(reverse('accounts:shop_create'), SHOP_FORM)
        response = self.client.get(reverse('accounts:shop_create'))
        self.assertRedirects(response, reverse('accounts:shop_edit'))

    def test_owner_can_edit_but_staff_cannot(self):
        self.client.post(reverse('accounts:shop_create'), SHOP_FORM)
        self.client.post(reverse('accounts:shop_edit'), {**SHOP_FORM, 'name': 'Renamed Cafe'})
        self.assertEqual(Shop.objects.get().name, 'Renamed Cafe')
        staff = user('staff')
        ShopMembership.objects.create(user=staff, shop=Shop.objects.get(), role=ShopMembership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('accounts:shop_edit')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:shop_staff')).status_code, 403)


class StaffManagementTests(TestCase):
    def setUp(self):
        self.owner = user('owner')
        self.shop = Shop.objects.create(name='Cafe', address='1 St', status=Shop.Status.APPROVED)
        ShopMembership.objects.create(user=self.owner, shop=self.shop, role=ShopMembership.Role.OWNER)
        self.client.force_login(self.owner)

    def test_add_existing_user_as_staff_by_username_or_email(self):
        user('alice')
        user('bob')
        self.client.post(reverse('accounts:shop_staff'), {'identifier': 'alice'})
        self.client.post(reverse('accounts:shop_staff'), {'identifier': 'BOB@example.com'})
        staff = ShopMembership.objects.filter(shop=self.shop, role=ShopMembership.Role.STAFF)
        self.assertEqual(sorted(m.user.username for m in staff), ['alice', 'bob'])

    def test_unknown_account_is_rejected(self):
        response = self.client.post(reverse('accounts:shop_staff'), {'identifier': 'ghost'})
        self.assertContains(response, 'No account found')

    def test_a_user_cannot_belong_to_two_shops(self):
        alice = user('alice')
        other = Shop.objects.create(name='Other', address='2 St', status=Shop.Status.APPROVED)
        ShopMembership.objects.create(user=alice, shop=other, role=ShopMembership.Role.OWNER)
        response = self.client.post(reverse('accounts:shop_staff'), {'identifier': 'alice'})
        self.assertContains(response, 'already belongs to a shop')

    def test_remove_staff_but_never_another_shops_membership(self):
        alice = user('alice')
        mine = ShopMembership.objects.create(user=alice, shop=self.shop, role=ShopMembership.Role.STAFF)
        stranger = ShopMembership.objects.create(
            user=user('carol'), shop=Shop.objects.create(name='Other', address='x'), role=ShopMembership.Role.STAFF)
        self.client.post(reverse('accounts:shop_staff_remove', args=[stranger.pk]))
        self.assertTrue(ShopMembership.objects.filter(pk=stranger.pk).exists())
        self.client.post(reverse('accounts:shop_staff_remove', args=[mine.pk]))
        self.assertFalse(ShopMembership.objects.filter(pk=mine.pk).exists())


class DiscoverTests(TestCase):
    def setUp(self):
        self.owner = user('owner')
        self.mine = Shop.objects.create(name='Mine', address='1 St', status=Shop.Status.APPROVED,
                                        latitude=40.110, longitude=-88.230)
        ShopMembership.objects.create(user=self.owner, shop=self.mine, role=ShopMembership.Role.OWNER)
        self.near = Shop.objects.create(name='Near Books', category='bookstore', address='2 St',
                                        status=Shop.Status.APPROVED, latitude=40.111, longitude=-88.231)
        self.far = Shop.objects.create(name='Far Bakery', category='bakery', address='3 St',
                                       status=Shop.Status.APPROVED, latitude=40.200, longitude=-88.300)
        self.pending = Shop.objects.create(name='Pending Shop', address='4 St', status=Shop.Status.PENDING)
        self.client.force_login(self.owner)

    def names(self, response):
        return [r['shop'].name for r in response.context['results']]

    def test_lists_approved_shops_nearest_first_and_hides_own_and_pending(self):
        self.assertEqual(self.names(self.client.get(reverse('accounts:discover'))), ['Near Books', 'Far Bakery'])

    def test_filters_by_category_and_search(self):
        self.assertEqual(self.names(self.client.get(reverse('accounts:discover'), {'category': 'bakery'})), ['Far Bakery'])
        self.assertEqual(self.names(self.client.get(reverse('accounts:discover'), {'q': 'near'})), ['Near Books'])

    def test_shop_detail_hides_unapproved_shops_from_others(self):
        self.assertEqual(self.client.get(self.near.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.pending.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.mine.get_absolute_url()).status_code, 200)
