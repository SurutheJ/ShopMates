"""The app shell in templates/base.html: structure, navigation, toast, one h1 per page."""
import re
from datetime import timedelta

from django.contrib import messages
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import ShopMembership
from deals import services
from deals.models import Deal
from deals.tests.helpers import DealTestCase, make_shop, make_terms, make_user

NAV_LABELS = ['Inbox', 'Discover', 'Redeem', 'Playbook', 'My shop']


def nav_block(html, css_class):
    """The inner HTML of the <nav class="..."> element."""
    match = re.search(rf'<nav class="{css_class}"[^>]*>(.*?)</nav>', html, re.S)
    return match.group(1) if match else ''


def labels(block):
    return re.findall(r'class="nav-item[^"]*"[^>]*>.*?<span>([^<]+)</span>', block, re.S)


class ShellStructureTests(DealTestCase):
    def test_logged_out_page_uses_the_bare_shell(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn('class="app bare"', html)
        self.assertNotIn('class="rail"', html)
        self.assertNotIn('class="bottomnav"', html)
        self.assertIn('width=device-width, initial-scale=1, viewport-fit=cover', html)
        self.assertIn('<meta name="theme-color" content="#FF7A59">', html)
        self.assertIn('img/favicon-64.png', html)
        self.assertIn('img/app-icon-192.png', html)
        self.assertIn(reverse('account_login'), html)
        self.assertIn(reverse('account_signup'), html)
        self.assertNotIn('topnav', html)

    def test_shell_loads_tokens_app_css_and_one_small_script(self):
        html = self.client.get(reverse('home')).content.decode()
        for name in ('css/tokens.css', 'css/app.css', 'css/base.css', 'js/app.js'):
            self.assertIn(name, html)

    def test_page_content_sits_in_exactly_one_scroll_region(self):
        self.client.force_login(self.cafe_owner)
        for name in ('deals:inbox', 'accounts:discover', 'deals:playbook', 'deals:redeem'):
            html = self.client.get(reverse(name)).content.decode()
            # Tab panes (designv2) are all .scroll, but only the open one is visible: the rest carry `hidden`.
            visible = [tag for tag in re.findall(r'<div[^>]*class="scroll\b[^>]*>', html) if ' hidden' not in tag]
            self.assertEqual(len(visible), 1, name)
            self.assertEqual(len(re.findall(r'class="screen[ "]', html)), 1, name)   # not .screen-head

    def test_owner_sees_five_nav_items_in_rail_and_bottom_bar(self):
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:inbox')).content.decode()
        self.assertIn('class="app"', html)
        self.assertEqual(labels(nav_block(html, 'rail')), NAV_LABELS)
        self.assertEqual(labels(nav_block(html, 'bottomnav')), NAV_LABELS)

    def test_staff_see_only_inbox_and_redeem(self):
        staff = make_user('books_staff')
        ShopMembership.objects.create(user=staff, shop=self.books, role=ShopMembership.Role.STAFF)
        self.client.force_login(staff)
        html = self.client.get(reverse('deals:redeem')).content.decode()
        self.assertEqual(labels(nav_block(html, 'bottomnav')), ['Inbox', 'Redeem'])

    def test_user_without_a_shop_gets_the_bare_shell_with_log_out(self):
        self.client.force_login(make_user('no_shop_yet'))
        html = self.client.get(reverse('accounts:shop_create')).content.decode()
        self.assertIn('class="app bare"', html)
        self.assertIn(f'action="{reverse("account_logout")}"', html)

    def top_bar(self, html):
        return re.search(r'<header class="topbar">(.*?)</header>', html, re.S).group(1)

    def test_owner_top_bar_has_no_account_links_because_they_are_on_my_shop(self):
        self.client.force_login(self.cafe_owner)
        top = self.top_bar(self.client.get(reverse('deals:inbox')).content.decode())
        self.assertNotIn(reverse('account_logout'), top)
        self.assertNotIn(reverse('deals:stats'), top)

    def test_owner_top_bar_has_the_bell_marked_coming_soon(self):
        """The design shows a notifications bell. There is no notifications feature yet, so it says so when tapped."""
        self.client.force_login(self.cafe_owner)
        top = self.top_bar(self.client.get(reverse('deals:inbox')).content.decode())
        self.assertIn('class="icon-btn"', top)
        self.assertIn('data-soon="Notifications"', top)
        self.assertIn('aria-label="Notifications (coming soon)"', top)
        self.assertIn('#i-bell', top)

    def test_staff_and_visitors_get_no_bell(self):
        self.assertNotIn('data-soon', self.top_bar(self.client.get(reverse('home')).content.decode()))

    def test_my_shop_is_a_plain_link_in_the_fifth_slot_and_there_is_no_menu_sheet(self):
        """The design's fifth item is My shop (a link), not a hamburger menu."""
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('deals:inbox')).content.decode()
        for css_class in ('rail', 'bottomnav'):
            block = nav_block(html, css_class)
            self.assertIn(f'href="{reverse("accounts:shop_edit")}"', block)
            self.assertIn('#i-shop', block)
            self.assertNotIn('data-sheet-toggle', block)
        self.assertNotIn('menu-sheet', html)

    def test_owner_finds_stats_and_log_out_on_the_my_shop_page(self):
        self.client.force_login(self.cafe_owner)
        html = self.client.get(reverse('accounts:shop_edit')).content.decode()
        self.assertIn(f'href="{reverse("deals:stats")}"', html)
        self.assertIn(f'<form method="post" action="{reverse("account_logout")}"', html)
        self.assertIn('csrfmiddlewaretoken', html)

    def test_the_shop_setup_page_has_no_log_out_block_of_its_own(self):
        """A user without a shop already has Log out in the top bar; the Account block belongs to an existing shop."""
        self.client.force_login(make_user('fresh2'))
        html = self.client.get(reverse('accounts:shop_create')).content.decode()
        self.assertEqual(html.count(f'action="{reverse("account_logout")}"'), 1)

    def test_staff_keep_stats_and_log_out_in_the_top_bar(self):
        staff = make_user('books_staff')
        ShopMembership.objects.create(user=staff, shop=self.books, role=ShopMembership.Role.STAFF)
        self.client.force_login(staff)
        html = self.client.get(reverse('deals:redeem')).content.decode()
        self.assertNotIn('menu-sheet', html)
        top = self.top_bar(html)
        self.assertIn(f'<form method="post" action="{reverse("account_logout")}"', top)
        self.assertIn(reverse('deals:stats'), top)

    def test_voucher_pages_are_bare_and_have_no_account_links(self):
        deal = self.active_deal()
        self.client.force_login(self.cafe_owner)  # even a signed-in owner sees the customer view
        html = self.client.get(reverse('deals:voucher_start', args=[deal.proposer_token])).content.decode()
        self.assertIn('class="app bare"', html)
        self.assertNotIn(reverse('account_logout'), html)


class NavStateTests(DealTestCase):
    def current(self, html, css_class='bottomnav'):
        found = re.findall(r'aria-current="page"[^>]*>.*?<span>([^<]+)</span>', nav_block(html, css_class), re.S)
        return found

    def page(self, url, user=None):
        self.client.force_login(user or self.cafe_owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response.content.decode()

    def test_inbox_and_deal_pages_highlight_inbox(self):
        deal = self.active_deal()
        for url in (reverse('deals:inbox'), deal.get_absolute_url(), reverse('deals:summary', args=[deal.pk])):
            self.assertEqual(self.current(self.page(url)), ['Inbox'], url)

    def test_discover_and_shop_pages_highlight_discover(self):
        for url in (reverse('accounts:discover'), self.books.get_absolute_url()):
            self.assertEqual(self.current(self.page(url)), ['Discover'], url)

    def test_other_tabs(self):
        self.assertEqual(self.current(self.page(reverse('deals:redeem'))), ['Redeem'])
        self.assertEqual(self.current(self.page(reverse('deals:playbook'))), ['Playbook'])
        self.assertEqual(self.current(self.page(reverse('accounts:shop_edit'))), ['My shop'])
        self.assertEqual(self.current(self.page(reverse('accounts:shop_staff'))), ['My shop'])

    def test_rail_marks_the_same_item_as_the_bottom_bar(self):
        html = self.page(reverse('deals:playbook'))
        self.assertEqual(self.current(html, 'rail'), ['Playbook'])


class InboxBadgeTests(DealTestCase):
    def badge(self, user):
        self.client.force_login(user)
        html = self.client.get(reverse('deals:redeem')).content.decode()
        found = re.search(r'<span class="dot">(\d+)</span>', nav_block(html, 'bottomnav'))
        return found.group(1) if found else None

    def test_no_badge_when_nothing_waits_on_you(self):
        self.assertIsNone(self.badge(self.cafe_owner))

    def test_badge_counts_deals_waiting_on_my_shop(self):
        self.proposed_deal()                                   # cafe proposed; books must answer
        self.assertEqual(self.badge(self.books_owner), '1')
        self.assertIsNone(self.badge(self.cafe_owner))         # the proposer is not the one waiting

    def test_badge_counts_each_deal_once_and_ignores_finished_ones(self):
        deal = self.proposed_deal()
        owner = make_user('third_owner')
        third = make_shop('Third', owner, category='bakery')
        services.create_draft(third, self.books, owner, make_terms(), send=True)
        self.assertEqual(self.badge(self.books_owner), '2')
        services.accept(deal, self.books_owner)
        self.assertEqual(self.badge(self.books_owner), '1')

    def test_badge_ignores_a_proposal_past_its_response_deadline(self):
        deal = self.proposed_deal()
        self.assertEqual(self.badge(self.books_owner), '1')
        Deal.objects.filter(pk=deal.pk).update(response_deadline=timezone.now() - timedelta(minutes=1))
        self.assertIsNone(self.badge(self.books_owner))
        deal.refresh_from_db()
        self.assertEqual(deal.status, Deal.Status.PROPOSED)    # counting does not change the deal


class ToastTests(DealTestCase):
    def test_flash_messages_render_as_a_status_toast(self):
        self.client.force_login(self.books_owner)
        response = self.client.post(reverse('deals:redeem'), {'code': 'NOPE1234'}, follow=True)
        html = response.content.decode()
        self.assertRegex(html, r'<div class="toast"[^>]*role="status"')
        self.assertIn('Code not found', html)
        self.assertNotIn('flash-list', html)

    def test_no_toast_element_without_messages(self):
        self.client.force_login(self.books_owner)
        self.assertNotIn('class="toast"', self.client.get(reverse('deals:redeem')).content.decode())


class OneH1PerPageTests(DealTestCase):
    def count_h1(self, url, user=None):
        if user:
            self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        # Tab panes and wizard steps are .scroll blocks and the closed ones carry `hidden`: only visible headings count.
        parts = re.split(r'(?=<div class="scroll)', response.content.decode())
        shown = [p for p in parts if not (p.startswith('<div class="scroll') and ' hidden' in p[:p.index('>')])]
        return len(re.findall(r'<h1[ >]', ''.join(shown)))

    def test_public_pages(self):
        deal = self.active_deal()
        voucher = services.issue_voucher(deal, self.cafe)
        for url in (reverse('home'), reverse('deals:stats'), reverse('account_login'), reverse('account_signup'),
                    reverse('deals:voucher_start', args=[deal.proposer_token]),
                    reverse('deals:voucher_show', args=[voucher.code])):
            self.assertEqual(self.count_h1(url), 1, url)

    def test_signed_in_pages(self):
        deal = self.active_deal()
        urls = [reverse('deals:inbox'), reverse('accounts:discover'), self.books.get_absolute_url(),
                deal.get_absolute_url(), reverse('deals:summary', args=[deal.pk]), reverse('deals:playbook'),
                reverse('deals:redeem'), reverse('accounts:shop_edit'), reverse('accounts:shop_staff')]
        self.client.force_login(self.cafe_owner)
        for url in urls:
            self.assertEqual(self.count_h1(url), 1, url)

    def test_new_deal_form_and_shop_setup(self):
        self.client.force_login(self.cafe_owner)
        self.assertEqual(self.count_h1(reverse('deals:new', args=[self.books.pk])), 1)
        self.client.force_login(make_user('fresh'))
        self.assertEqual(self.count_h1(reverse('accounts:shop_create')), 1)
