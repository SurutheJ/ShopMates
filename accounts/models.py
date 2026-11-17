import string
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from .geo import haversine_miles


class User(AbstractUser):
    """Custom user from day one, so fields can be added later without a painful migration."""


class Shop(models.Model):
    class Category(models.TextChoices):
        CAFE = 'cafe', 'Cafe'
        BOOKSTORE = 'bookstore', 'Bookstore'
        BAKERY = 'bakery', 'Bakery'
        RESTAURANT = 'restaurant', 'Restaurant'
        FLOWERS = 'flowers', 'Flowers and gifts'
        FITNESS = 'fitness', 'Fitness'
        SALON = 'salon', 'Salon and beauty'
        RETAIL = 'retail', 'Retail'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending approval'
        APPROVED = 'approved', 'Approved'
        SUSPENDED = 'suspended', 'Suspended'

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.CAFE)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=80, default='Champaign')
    hours = models.CharField(max_length=200, blank=True, help_text='For example: Mon-Fri 7am-6pm')
    description = models.CharField(
        max_length=300, blank=True,
        help_text='One or two sentences about your shop and customers, in your own words. '
                  'Used to find partners with similar customers.',
    )
    typical_order_value = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('12.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Average spend per customer, in dollars. Used to estimate the cost of a discount.',
    )
    margin_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Gross margin, in percent. Used only to estimate fairness.',
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts:shop_detail', kwargs={'pk': self.pk})

    @property
    def category_short(self):
        """The category name cut to its first words before ' and ', for tags and chips ("Flowers", not "Flowers and gifts")."""
        return self.get_category_display().split(' and ')[0]

    @property
    def initials(self):
        """Two capital letters for the avatar circle: first letters of the first two words, or the first two letters of one word."""
        words = [w for w in (w.lstrip(string.punctuation) for w in self.name.split()) if w]
        if not words:
            return '?'
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][0] + words[1][0]).upper()

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    def distance_miles_to(self, other):
        if None in (self.latitude, self.longitude, other.latitude, other.longitude):
            return None
        return haversine_miles(self.latitude, self.longitude, other.latitude, other.longitude)


class ShopMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        STAFF = 'staff', 'Staff'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'shop'], name='unique_membership_per_user_shop'),
        ]

    def __str__(self):
        return f'{self.user} is {self.role} at {self.shop}'


class OsmQueryCache(models.Model):
    """One saved answer from OpenStreetMap's Overpass search, so the same area is asked for at most once a week."""
    key = models.CharField(max_length=120, unique=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField()

    def __str__(self):
        return self.key
