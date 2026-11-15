"""
Create demo shops, users and deals for local development.

Refuses to run unless DEBUG is on. All demo accounts share DEMO_PASSWORD below,
which is a development-only value; never use it anywhere real.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Shop, ShopMembership
from deals import services
from deals.models import Deal

DEMO_PASSWORD = 'shopmates-demo-1'

SHOPS = [
    # username, name, category, address, order value, lat, lon
    ('demo_cafe', 'Green Street Cafe', 'cafe', '610 E Green St', 9, 40.1103, -88.2290),
    ('demo_books', 'Pageturner Books', 'bookstore', '612 E Green St', 24, 40.1104, -88.2285),
    ('demo_bakery', 'Rise Bakery', 'bakery', '104 N Walnut St', 8, 40.1169, -88.2434),
    ('demo_flowers', 'Petal and Stem', 'flowers', '210 W Main St', 30, 40.1175, -88.2440),
    ('demo_fit', 'Prairie Yoga', 'fitness', '55 E Church St', 15, 40.1150, -88.2400),
    ('demo_coffee2', 'Daily Grind Coffee', 'cafe', '33 E Springfield Ave', 7, 40.1135, -88.2360),
]


class Command(BaseCommand):
    help = 'Create demo shops, users and deals (development only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_demo only runs with DEBUG=True.')
        User = get_user_model()
        users, shops = {}, {}
        for username, name, category, address, order_value, lat, lon in SHOPS:
            user, _ = User.objects.get_or_create(
                username=username, defaults={'email': f'{username}@example.com'})
            user.set_password(DEMO_PASSWORD)
            user.save()
            shop, _ = Shop.objects.get_or_create(
                name=name,
                defaults={'category': category, 'address': address, 'typical_order_value': order_value,
                          'latitude': lat, 'longitude': lon, 'hours': 'Mon-Sat 8am-6pm',
                          'status': Shop.Status.APPROVED})
            ShopMembership.objects.get_or_create(
                user=user, shop=shop, defaults={'role': ShopMembership.Role.OWNER})
            users[username], shops[username] = user, shop

        staff, _ = User.objects.get_or_create(
            username='demo_staff', defaults={'email': 'demo_staff@example.com'})
        staff.set_password(DEMO_PASSWORD)
        staff.save()
        ShopMembership.objects.get_or_create(
            user=staff, shop=shops['demo_books'], defaults={'role': ShopMembership.Role.STAFF})

        if Deal.objects.exists():
            self.stdout.write('Deals already exist; skipping deal creation.')
        else:
            self._make_deals(users, shops)

        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready. Log in as demo_cafe, demo_books, demo_staff, etc. '
            f'The shared dev password is DEMO_PASSWORD in {__file__}'))

    def _make_deals(self, users, shops):
        today = timezone.localdate()
        terms = {
            'offer_text': '10% off one purchase for customers sent by a neighboring shop',
            'discount_percent': 10, 'redemption_cap': 20,
            'start_date': today, 'end_date': today + timedelta(days=30), 'terms': '',
        }
        # 1. An active deal with a few redemptions (cafe <-> books)
        deal = services.create_draft(shops['demo_cafe'], shops['demo_books'], users['demo_cafe'], terms, send=True)
        services.accept(deal, users['demo_books'])
        for referring, honoring_user in [(shops['demo_cafe'], users['demo_books'])] * 3 + \
                                        [(shops['demo_books'], users['demo_cafe'])]:
            voucher = services.issue_voucher(deal, referring)
            services.redeem_voucher(voucher.code, honoring_user)
        # 2. A proposal waiting on the cafe (bakery -> cafe)
        services.create_draft(shops['demo_bakery'], shops['demo_cafe'], users['demo_bakery'], terms, send=True)
        # 3. A draft not yet sent (flowers -> books)
        services.create_draft(shops['demo_flowers'], shops['demo_books'], users['demo_flowers'], terms)
