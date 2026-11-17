from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import Shop
from deals.tests.helpers import TEST_PASSWORD, make_shop, make_user

User = get_user_model()


class ShopApprovalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_user('new_owner')
        self.shop = make_shop('New Shop', self.owner, status=Shop.Status.PENDING)
        self.partner = make_shop('Partner', make_user('partner_owner'))
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', TEST_PASSWORD)

    def admin_action(self, action):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:accounts_shop_changelist'),
                                    {'action': action, '_selected_action': [self.shop.pk]}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.shop.refresh_from_db()

    def test_pending_shop_gets_403_and_the_waiting_page_on_owner_pages(self):
        self.client.force_login(self.owner)
        for name, args in (('deals:playbook', []), ('deals:redeem', []), ('deals:new', [self.partner.pk])):
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 403, name)
            self.assertContains(response, 'Waiting for approval', status_code=403)

    def test_pending_shop_cannot_use_the_ai_draft_endpoint(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('deals:ai_draft'), {'recipient_id': self.partner.pk})
        self.assertEqual(response.status_code, 403)

    def test_pending_shop_cannot_post_a_proposal(self):
        from deals.models import Deal
        self.client.force_login(self.owner)
        response = self.client.post(reverse('deals:new', args=[self.partner.pk]), {'action': 'send'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Deal.objects.count(), 0)

    def test_admin_approve_action_opens_the_pages(self):
        self.admin_action('approve')
        self.assertEqual(self.shop.status, Shop.Status.APPROVED)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('deals:playbook')).status_code, 200)
        self.assertEqual(self.client.get(reverse('deals:redeem')).status_code, 200)

    def test_admin_suspend_action_closes_them_again(self):
        self.admin_action('approve')
        self.admin_action('suspend')
        self.assertEqual(self.shop.status, Shop.Status.SUSPENDED)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('deals:playbook')).status_code, 403)

    def test_suspended_shop_is_told_it_was_suspended_not_that_it_is_waiting(self):
        self.admin_action('suspend')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('deals:playbook'))
        self.assertContains(response, 'was suspended', status_code=403)
        self.assertNotContains(response, 'needs to approve new shops', status_code=403)

    def test_non_admin_cannot_use_the_admin_action(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('admin:accounts_shop_changelist'),
                         {'action': 'approve', '_selected_action': [self.shop.pk]})
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.status, Shop.Status.PENDING)
