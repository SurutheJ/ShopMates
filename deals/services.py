"""
The rules of Shopmates: negotiation states, vouchers and redemptions.

All state changes go through this module so the rules live in one place and
are easy to test. Views only translate HTTP to these functions.
"""

import secrets
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from accounts.models import Shop, ShopMembership

from .models import Deal, DealEvent, DealVersion, Redemption, Voucher

S = Deal.Status

# Letters and digits without look-alikes (no 0/O, 1/I/L).
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 8


class DealError(Exception):
    """A rule was broken. The message is safe to show to the user."""


class RedeemError(DealError):
    def __init__(self, message, reason='invalid'):
        super().__init__(message)
        self.reason = reason


def record(deal, actor, action, note=''):
    DealEvent.objects.create(deal=deal, actor=actor, action=action, note=note)


def _owner_shop(deal, user):
    """The shop (a party to this deal) that `user` owns. Raises if there is none."""
    membership = (ShopMembership.objects
                  .select_related('shop')
                  .filter(user=user, role=ShopMembership.Role.OWNER,
                          shop_id__in=[deal.proposer_id, deal.recipient_id])
                  .first())
    if membership is None:
        raise DealError('You are not allowed to act on this deal.')
    if not membership.shop.is_approved:
        raise DealError('Your shop is not approved yet.')
    return membership.shop


def _require_turn(deal, shop):
    if deal.status not in Deal.OPEN_NEGOTIATION:
        raise DealError('This deal is not open for a response.')
    if deal.turn_id != shop.pk:
        raise DealError('It is not your turn to respond.')


def _new_deadline():
    return timezone.now() + timedelta(days=settings.DEAL_RESPONSE_DAYS)


def _add_version(deal, shop, user, terms):
    last = deal.versions.order_by('-number').first()
    return DealVersion.objects.create(
        deal=deal,
        number=(last.number + 1) if last else 1,
        offer_text=terms['offer_text'],
        discount_percent=terms['discount_percent'],
        redemption_cap=terms['redemption_cap'],
        start_date=terms['start_date'],
        end_date=terms['end_date'],
        terms=terms.get('terms', ''),
        created_by=user,
        created_by_shop=shop,
    )


# ---------------------------------------------------------------------------
# Negotiation
# ---------------------------------------------------------------------------

@transaction.atomic
def create_draft(proposer, recipient, user, terms, send=False):
    if proposer.pk == recipient.pk:
        raise DealError('You can not make a deal with your own shop.')
    if not (proposer.is_approved and recipient.is_approved):
        raise DealError('Both shops must be approved to make a deal.')
    is_owner = ShopMembership.objects.filter(
        user=user, shop=proposer, role=ShopMembership.Role.OWNER).exists()
    if not is_owner:
        raise DealError('Only the shop owner can propose a deal.')
    live = Deal.objects.filter(status__in=Deal.LIVE).filter(
        proposer__in=[proposer, recipient], recipient__in=[proposer, recipient])
    if live.exists():
        raise DealError('These two shops already have a deal in progress.')

    deal = Deal.objects.create(proposer=proposer, recipient=recipient)
    _add_version(deal, proposer, user, terms)
    record(deal, user, 'created')
    if send:
        send_proposal(deal, user)
    return deal


@transaction.atomic
def edit_draft(deal, user, terms):
    """Change a draft's terms in place. It was never sent, so it stays version 1."""
    shop = _owner_shop(deal, user)
    if deal.status != S.DRAFT or shop.pk != deal.proposer_id:
        raise DealError('Only the proposer can edit a draft.')
    version = deal.current_version
    for field in ('offer_text', 'discount_percent', 'redemption_cap', 'start_date', 'end_date'):
        setattr(version, field, terms[field])
    version.terms = terms.get('terms', '')
    version.save()
    record(deal, user, 'edited')
    return deal


@transaction.atomic
def send_proposal(deal, user):
    shop = _owner_shop(deal, user)
    if deal.status != S.DRAFT or shop.pk != deal.proposer_id:
        raise DealError('Only the proposer can send a draft.')
    deal.status = S.PROPOSED
    deal.turn = deal.recipient
    deal.response_deadline = _new_deadline()
    deal.save()
    record(deal, user, 'sent', f'to {deal.recipient.name}')
    return deal


@transaction.atomic
def accept(deal, user, today=None):
    shop = _owner_shop(deal, user)
    _require_turn(deal, shop)
    today = today or timezone.localdate()
    if deal.current_version.end_date < today:
        raise DealError('These terms have already ended. Counter with new dates instead.')
    deal.status = S.ACCEPTED
    deal.turn = None
    deal.response_deadline = None
    deal.save()
    record(deal, user, 'accepted', f'version {deal.current_version.number}')
    sync_status(deal)
    return deal


@transaction.atomic
def counter(deal, user, terms):
    shop = _owner_shop(deal, user)
    _require_turn(deal, shop)
    version = _add_version(deal, shop, user, terms)
    deal.status = S.COUNTERED
    deal.turn = deal.partner_of(shop)
    deal.response_deadline = _new_deadline()
    deal.save()
    record(deal, user, 'countered', f'version {version.number}')
    return deal


@transaction.atomic
def decline(deal, user):
    shop = _owner_shop(deal, user)
    _require_turn(deal, shop)
    deal.status = S.DECLINED
    deal.turn = None
    deal.response_deadline = None
    deal.save()
    record(deal, user, 'declined')
    return deal


@transaction.atomic
def withdraw(deal, user):
    shop = _owner_shop(deal, user)
    if shop.pk != deal.proposer_id:
        raise DealError('Only the shop that proposed the deal can withdraw it.')
    if deal.status not in (S.DRAFT, S.PROPOSED, S.COUNTERED):
        raise DealError('This deal can no longer be withdrawn.')
    deal.status = S.WITHDRAWN
    deal.turn = None
    deal.response_deadline = None
    deal.save()
    record(deal, user, 'withdrawn')
    return deal


# ---------------------------------------------------------------------------
# Time-based transitions (run lazily on read, and by the management command)
# ---------------------------------------------------------------------------

def redemptions_at(deal, shop):
    """How many redemptions `shop` has honored for this deal."""
    return Redemption.objects.filter(voucher__deal=deal, voucher__honoring_shop=shop).count()


def _redemption_counts(deals):
    """{(deal id, honoring shop id): redemptions} for many deals in one query."""
    rows = (Redemption.objects.filter(voucher__deal__in=deals)
            .values('voucher__deal', 'voucher__honoring_shop').annotate(n=Count('id')))
    return {(r['voucher__deal'], r['voucher__honoring_shop']): r['n'] for r in rows}


def sync_status(deal, now=None, counts=None):
    """
    Apply time-based transitions: expire stale proposals, start and finish deals.

    `counts` is the optional result of _redemption_counts, so a list page does
    not run two count queries per deal.
    """
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    original = deal.status

    if deal.status in Deal.OPEN_NEGOTIATION and deal.response_deadline and deal.response_deadline < now:
        deal.status = S.EXPIRED
        deal.turn = None
        record(deal, None, 'expired', 'no response in time')

    version = deal.current_version
    if version and deal.status == S.ACCEPTED and version.start_date <= today:
        deal.status = S.ACTIVE
        record(deal, None, 'activated')

    if version and deal.status in (S.ACCEPTED, S.ACTIVE):
        if counts is None:
            both_full = all(
                redemptions_at(deal, shop) >= version.redemption_cap for shop in (deal.proposer, deal.recipient)
            )
        else:
            both_full = all(
                counts.get((deal.pk, shop.pk), 0) >= version.redemption_cap for shop in (deal.proposer, deal.recipient)
            )
        if today > version.end_date or (deal.status == S.ACTIVE and both_full):
            deal.status = S.COMPLETED
            record(deal, None, 'completed')

    if deal.status != original:
        deal.save()
    return deal


def renewal_terms(deal, today=None):
    """Terms for renewing a completed deal: same offer, cap up by half (rounded up), same length from today."""
    version = deal.current_version
    today = today or timezone.localdate()
    cap = min(-(-version.redemption_cap * 3 // 2), settings.REDEMPTION_CAP_MAX)
    return {
        'offer_text': version.offer_text,
        'discount_percent': version.discount_percent,
        'redemption_cap': cap,
        'start_date': today,
        'end_date': today + (version.end_date - version.start_date),
        'terms': version.terms,
    }


def sync_all(deals):
    running = [d for d in deals if d.status in (S.ACCEPTED, S.ACTIVE)]
    counts = _redemption_counts(running) if running else {}
    for deal in deals:
        sync_status(deal, counts=counts)


def customers_sent_this_month(shop):
    """Redemptions confirmed this calendar month (local time) for customers that `shop`'s QR code sent."""
    today = timezone.localdate()
    month_start = timezone.make_aware(datetime.combine(today.replace(day=1), time.min))
    return Redemption.objects.filter(voucher__referring_shop=shop, confirmed_at__gte=month_start).count()


# ---------------------------------------------------------------------------
# Vouchers and redemptions
# ---------------------------------------------------------------------------

def _new_code():
    for _ in range(20):
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Voucher.objects.filter(code=code).exists():
            return code
    raise DealError('Could not create a code. Try again.')


def issue_voucher(deal, referring_shop):
    """A customer scanned `referring_shop`'s QR: give them a one-time code for the partner shop."""
    sync_status(deal)
    version = deal.current_version
    today = timezone.localdate()
    if deal.status != S.ACTIVE:
        raise DealError('This offer is not available right now.')
    if not (version.start_date <= today <= version.end_date):
        raise DealError('This offer is outside its dates.')
    honoring = deal.partner_of(referring_shop)
    if redemptions_at(deal, honoring) >= version.redemption_cap:
        raise DealError('Sorry, this offer has reached its limit.')
    return Voucher.objects.create(
        deal=deal,
        referring_shop=referring_shop,
        honoring_shop=honoring,
        code=_new_code(),
        expires_at=timezone.now() + timedelta(hours=settings.VOUCHER_TTL_HOURS),
    )


def normalize_code(raw):
    return (raw or '').strip().upper().replace(' ', '').replace('-', '')


def redeem_voucher(code, user):
    """
    Staff or an owner of the honoring shop confirms a customer's code.

    Checks, in order: code exists, it belongs to the user's shop, it is unused,
    the deal is active and in its dates, the code has not expired, and the cap
    is not reached. The database's OneToOne makes a double confirmation
    impossible even if two requests race.
    """
    voucher = (Voucher.objects
               .select_related('deal', 'honoring_shop', 'referring_shop')
               .filter(code=normalize_code(code)).first())
    if voucher is None:
        raise RedeemError('Code not found. Check it and try again.', 'not_found')

    if not ShopMembership.objects.filter(user=user, shop=voucher.honoring_shop).exists():
        raise RedeemError('This code is for a different shop.', 'wrong_shop')

    if Redemption.objects.filter(voucher=voucher).exists():
        raise RedeemError('This code was already used.', 'already_used')

    deal = voucher.deal
    sync_status(deal)
    version = deal.current_version
    today = timezone.localdate()
    if deal.status != S.ACTIVE:
        raise RedeemError('This deal is not active.', 'not_active')
    if not (version.start_date <= today <= version.end_date):
        raise RedeemError('This deal is outside its dates.', 'outside_dates')
    if voucher.expires_at < timezone.now():
        raise RedeemError('This code has expired. Ask the customer to scan again.', 'expired')

    try:
        with transaction.atomic():
            if redemptions_at(deal, voucher.honoring_shop) >= version.redemption_cap:
                raise RedeemError('The redemption cap has been reached.', 'cap_reached')
            redemption = Redemption.objects.create(voucher=voucher, confirmed_by=user)
    except IntegrityError:
        raise RedeemError('This code was already used.', 'already_used')

    sync_status(deal)  # may complete the deal if both caps are now full
    return redemption


# ---------------------------------------------------------------------------
# Summary and fairness
# ---------------------------------------------------------------------------

def summary(deal):
    """Customers sent and received per shop, estimated discount cost, and a fairness verdict."""
    version = deal.current_version
    sides = []
    for shop in (deal.proposer, deal.recipient):
        sent = Redemption.objects.filter(voucher__deal=deal, voucher__referring_shop=shop).count()
        received = Redemption.objects.filter(voucher__deal=deal, voucher__honoring_shop=shop).count()
        cost = received * (version.discount_percent / 100) * float(shop.typical_order_value)
        sides.append({'shop': shop, 'sent': sent, 'received': received, 'cost': round(cost, 2)})

    total = sum(s['sent'] for s in sides)
    gap = abs(sides[0]['sent'] - sides[1]['sent'])
    lopsided = total >= 4 and gap / total >= 0.4
    suggestion = ''
    if lopsided:
        more, less = sorted(sides, key=lambda s: s['sent'], reverse=True)
        suggestion = (
            f"{more['shop'].name} sent {gap} more customers than {less['shop'].name}. "
            f"For a renewal, consider a higher cap or discount for {more['shop'].name}'s customers, "
            f"or a shorter deal so both sides stay happy."
        )
    return {'sides': sides, 'total': total, 'lopsided': lopsided, 'suggestion': suggestion, 'version': version}
