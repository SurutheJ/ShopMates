import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from accounts.models import Shop


class Deal(models.Model):
    """An agreement between two shops. The terms live in DealVersion rows (newest = current)."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PROPOSED = 'proposed', 'Proposed'
        COUNTERED = 'countered', 'Countered'
        ACCEPTED = 'accepted', 'Accepted'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DECLINED = 'declined', 'Declined'
        EXPIRED = 'expired', 'Expired'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    OPEN_NEGOTIATION = (Status.PROPOSED, Status.COUNTERED)
    # A pair of shops can only have one of these at a time.
    LIVE = (Status.DRAFT, Status.PROPOSED, Status.COUNTERED, Status.ACCEPTED, Status.ACTIVE)
    CLOSED = (Status.COMPLETED, Status.DECLINED, Status.EXPIRED, Status.WITHDRAWN)

    proposer = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='proposed_deals')
    recipient = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='received_deals')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    # Whose move it is while the deal is being negotiated.
    turn = models.ForeignKey(Shop, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    response_deadline = models.DateTimeField(null=True, blank=True)
    # Secret tokens in each shop's QR code. A customer who scans shop X's QR
    # gets a voucher to use at the partner shop.
    proposer_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    recipient_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(proposer=models.F('recipient')),
                name='deal_shops_differ',
            ),
        ]

    def __str__(self):
        return f'Deal {self.pk}: {self.proposer} and {self.recipient} ({self.status})'

    def get_absolute_url(self):
        return reverse('deals:detail', kwargs={'pk': self.pk})

    def is_party(self, shop):
        return shop is not None and shop.pk in (self.proposer_id, self.recipient_id)

    def partner_of(self, shop):
        return self.recipient if shop.pk == self.proposer_id else self.proposer

    def token_for(self, shop):
        """The QR token of `shop` (customers who scan it get a voucher usable at the partner)."""
        return self.proposer_token if shop.pk == self.proposer_id else self.recipient_token

    @property
    def current_version(self):
        return self.versions.order_by('-number').first()

    @property
    def is_negotiating(self):
        return self.status in self.OPEN_NEGOTIATION


class DealVersion(models.Model):
    """One set of terms. A counter-offer creates a new version; an accepted version never changes."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='versions')
    number = models.PositiveIntegerField()
    offer_text = models.CharField(max_length=200, help_text='What a referred customer gets, in plain words.')
    discount_percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)])
    redemption_cap = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Most redemptions each shop will honor.')
    start_date = models.DateField()
    end_date = models.DateField()
    terms = models.TextField(blank=True, help_text='Anything else both shops should agree on.')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_by_shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['deal', 'number'], name='unique_version_number_per_deal'),
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')),
                                   name='version_end_after_start'),
        ]

    def __str__(self):
        return f'Deal {self.deal_id} v{self.number}'


class DealMessage(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='+')
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class DealEvent(models.Model):
    """Audit trail of every state change: who did what, and when."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='+')
    action = models.CharField(max_length=30)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class Voucher(models.Model):
    """A one-time code a customer gets by scanning a shop's QR; redeemable at the partner shop."""

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='vouchers')
    referring_shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='vouchers_sent')
    honoring_shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='vouchers_honored')
    code = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return self.code


class Redemption(models.Model):
    """A staff-confirmed use of a voucher. The OneToOne makes double redemption impossible."""

    voucher = models.OneToOneField(Voucher, on_delete=models.PROTECT, related_name='redemption')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-confirmed_at']
