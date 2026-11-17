"""
Load a realistic demo scenario for recording the product video. Development only.

Unlike `seed_demo` (small, for manual testing) this wipes shops, users and
deals first, then builds a neighborhood with:
  - an active deal with ~2 weeks of redemption history that is lopsided
    (so the fairness view and deal coach have something to say)
  - a proposal waiting on Green Street Cafe, a counter-offer in progress,
    and a draft
All demo accounts share the password printed at the end.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Shop, ShopMembership
from deals import services
from deals.models import Deal, DealMessage, Redemption, Voucher

PASSWORD = 'shopmates-demo-1'

# username, name, category, address, typical spend, lat, lon, hours
SHOPS = [
    ('demo_cafe', 'Green Street Cafe', 'cafe', '610 E Green St', 9, 40.1103, -88.2290, 'Mon-Sun 7am-8pm'),
    ('demo_books', 'Pageturner Books', 'bookstore', '612 E Green St', 24, 40.1104, -88.2285, 'Mon-Sat 10am-7pm'),
    ('demo_bakery', 'Rise Bakery', 'bakery', '104 N Walnut St', 8, 40.1169, -88.2434, 'Tue-Sun 7am-3pm'),
    ('demo_flowers', 'Petal and Stem', 'flowers', '210 W Main St', 30, 40.1175, -88.2440, 'Mon-Sat 9am-6pm'),
    ('demo_fit', 'Prairie Yoga', 'fitness', '55 E Church St', 15, 40.1150, -88.2400, 'Daily 6am-9pm'),
    ('demo_coffee2', 'Daily Grind Coffee', 'cafe', '33 E Springfield Ave', 7, 40.1135, -88.2360, 'Mon-Fri 6:30am-5pm'),
    ('demo_salon', 'Studio Twelve Salon', 'salon', '12 E University Ave', 45, 40.1160, -88.2420, 'Tue-Sat 9am-7pm'),
    ('demo_resto', 'Prairie Table', 'restaurant', '120 W Main St', 22, 40.1172, -88.2446, 'Daily 11am-10pm'),
]

# (days ago, who referred) for the cafe/books deal: the cafe sends many more customers.
HISTORY = [(13, 'cafe'), (12, 'cafe'), (12, 'books'), (11, 'cafe'), (10, 'cafe'), (9, 'books'), (9, 'cafe'),
           (8, 'cafe'), (7, 'cafe'), (6, 'books'), (6, 'cafe'), (5, 'cafe'), (4, 'cafe'), (3, 'books'),
           (2, 'cafe'), (1, 'cafe'), (1, 'cafe'), (0, 'cafe')]


class Command(BaseCommand):
    help = 'Wipe and load the showcase demo scenario (development only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_showcase only runs with DEBUG=True.')
        User = get_user_model()

        Redemption.objects.all().delete()
        Deal.objects.all().delete()
        Shop.objects.all().delete()
        User.objects.filter(username__startswith='demo_').delete()

        users, shops = {}, {}
        for username, name, category, address, spend, lat, lon, hours in SHOPS:
            user = User.objects.create_user(username, f'{username}@example.com', PASSWORD)
            shop = Shop.objects.create(name=name, category=category, address=address, typical_order_value=spend,
                                       latitude=lat, longitude=lon, hours=hours, status=Shop.Status.APPROVED)
            ShopMembership.objects.create(user=user, shop=shop, role=ShopMembership.Role.OWNER)
            users[username], shops[username] = user, shop
        staff = User.objects.create_user('demo_staff', 'demo_staff@example.com', PASSWORD)
        ShopMembership.objects.create(user=staff, shop=shops['demo_books'], role=ShopMembership.Role.STAFF)

        today = timezone.localdate()
        base = {'discount_percent': 10, 'redemption_cap': 30, 'terms': ''}

        # 1. Active, lopsided deal with history (cafe <-> books).
        deal = services.create_draft(
            shops['demo_cafe'], shops['demo_books'], users['demo_cafe'],
            {**base, 'offer_text': '10% off any drink or book with a receipt from next door',
             'start_date': today - timedelta(days=14), 'end_date': today + timedelta(days=16)}, send=True)
        DealMessage.objects.create(deal=deal, author=users['demo_cafe'], shop=shops['demo_cafe'],
                                   body='Hi! We keep sending people to your shelves. Want to make it official?')
        services.accept(deal, users['demo_books'], today=today)
        deal.refresh_from_db()
        for days_ago, who in HISTORY:
            referring, honoring_user = ((shops['demo_cafe'], users['demo_books']) if who == 'cafe'
                                        else (shops['demo_books'], users['demo_cafe']))
            voucher = services.issue_voucher(deal, referring)
            redemption = services.redeem_voucher(voucher.code, honoring_user)
            when = timezone.now() - timedelta(days=days_ago, hours=(days_ago * 3) % 7)
            Voucher.objects.filter(pk=voucher.pk).update(created_at=when)
            Redemption.objects.filter(pk=redemption.pk).update(confirmed_at=when)

        # 2. A proposal waiting on the cafe (bakery -> cafe).
        services.create_draft(
            shops['demo_bakery'], shops['demo_cafe'], users['demo_bakery'],
            {**base, 'offer_text': 'Free cookie with any coffee, free coffee refill with any pastry',
             'discount_percent': 15, 'redemption_cap': 40,
             'start_date': today, 'end_date': today + timedelta(days=30)}, send=True)

        # 3. A counter-offer in progress (yoga -> daily grind, countered by the coffee shop).
        d3 = services.create_draft(
            shops['demo_fit'], shops['demo_coffee2'], users['demo_fit'],
            {**base, 'offer_text': '20% off a smoothie or coffee after class', 'discount_percent': 20,
             'redemption_cap': 100, 'start_date': today, 'end_date': today + timedelta(days=45)}, send=True)
        services.counter(d3, users['demo_coffee2'],
                         {**base, 'offer_text': '15% off a coffee after class', 'discount_percent': 15,
                          'redemption_cap': 50, 'start_date': today, 'end_date': today + timedelta(days=30)})

        # 4. A draft not yet sent (flowers -> bakery).
        services.create_draft(
            shops['demo_flowers'], shops['demo_bakery'], users['demo_flowers'],
            {**base, 'offer_text': '10% off a cake with a flower purchase', 'redemption_cap': 25,
             'start_date': today, 'end_date': today + timedelta(days=30)})

        self.stdout.write(self.style.SUCCESS(
            f'Showcase data ready ({Redemption.objects.count()} redemptions). '
            f'Log in as demo_cafe, demo_books, demo_bakery, demo_staff... Password: {PASSWORD}'))
