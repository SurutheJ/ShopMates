import csv
from datetime import timedelta

import segno
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from accounts.access import approved_shop_required, owner_required, shop_required
from accounts.models import Shop, ShopMembership
from ai.services import draft_deal

from . import services, throttle
from .forms import DealTermsForm, MessageForm, RedeemForm
from .models import Deal, DealMessage, Redemption, Voucher
from .services import DealError, RedeemError
from .stats import public_stats

S = Deal.Status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _party_deal_or_404(request, pk):
    """A deal the signed-in shop is a party to. Anyone else gets a 404 (not even a hint it exists)."""
    deal = get_object_or_404(Deal.objects.select_related('proposer', 'recipient', 'turn'), pk=pk)
    if not deal.is_party(request.shop):
        raise Http404('Deal not found')
    services.sync_status(deal)
    return deal


def _terms_initial(version=None):
    if version:
        return {
            'offer_text': version.offer_text,
            'discount_percent': version.discount_percent,
            'redemption_cap': version.redemption_cap,
            'start_date': version.start_date,
            'end_date': version.end_date,
            'terms': version.terms,
        }
    today = timezone.localdate()
    return {
        'offer_text': '10% off one purchase for customers sent by a neighboring shop',
        'discount_percent': 10,
        'redemption_cap': 50,
        'start_date': today,
        'end_date': today + timedelta(days=30),
    }


def _qr_svg(url):
    return mark_safe(segno.make(url, error='m').svg_inline(scale=5, border=2))


def _qr_context(request, deal, shop):
    if deal.status not in (S.ACCEPTED, S.ACTIVE):
        return {}
    url = request.build_absolute_uri(reverse('deals:voucher_start', args=[deal.token_for(shop)]))
    return {'qr_url': url, 'qr_svg': _qr_svg(url)}


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@shop_required
def inbox(request):
    shop = request.shop
    is_owner = request.membership.role == ShopMembership.Role.OWNER
    context = {'is_owner': is_owner}
    if is_owner and shop.is_approved:
        deals = list(Deal.objects.filter(Q(proposer=shop) | Q(recipient=shop))
                     .select_related('proposer', 'recipient', 'turn'))
        services.sync_all(deals)
        for deal in deals:
            deal.partner = deal.partner_of(shop)
            deal.version = deal.current_version
        context.update({
            'needs_response': [d for d in deals if d.status in Deal.OPEN_NEGOTIATION and d.turn_id == shop.pk],
            'waiting': [d for d in deals if d.status in Deal.OPEN_NEGOTIATION and d.turn_id != shop.pk],
            'drafts': [d for d in deals if d.status == S.DRAFT],
            'running': [d for d in deals if d.status in (S.ACCEPTED, S.ACTIVE)],
            'past': [d for d in deals if d.status in Deal.CLOSED],
        })
    return render(request, 'deals/inbox.html', context)


# ---------------------------------------------------------------------------
# Proposals and negotiation
# ---------------------------------------------------------------------------

@owner_required
def deal_new(request, shop_pk):
    recipient = get_object_or_404(Shop, pk=shop_pk, status=Shop.Status.APPROVED)
    if recipient.pk == request.shop.pk:
        raise Http404('Pick a different shop')
    form = DealTermsForm(request.POST or None, initial=_terms_initial())
    if request.method == 'POST' and form.is_valid():
        send = request.POST.get('action') == 'send'
        try:
            deal = services.create_draft(request.shop, recipient, request.user, form.cleaned_data, send=send)
        except DealError as exc:
            messages.error(request, str(exc))
        else:
            note = request.POST.get('message', '').strip()[:1000]
            if note:
                DealMessage.objects.create(deal=deal, author=request.user, shop=request.shop, body=note)
            messages.success(request, 'Proposal sent.' if send else 'Draft saved.')
            return redirect(deal)
    return render(request, 'deals/deal_form.html', {
        'form': form, 'recipient': recipient, 'mode': 'new',
        'message': request.POST.get('message', ''),
    })


@owner_required
def deal_detail(request, pk):
    deal = _party_deal_or_404(request, pk)
    shop = request.shop
    version = deal.current_version
    my_turn = deal.status in Deal.OPEN_NEGOTIATION and deal.turn_id == shop.pk
    context = {
        'deal': deal,
        'version': version,
        'versions': deal.versions.select_related('created_by_shop'),
        'events': deal.events.select_related('actor'),
        'deal_messages': deal.messages.select_related('author', 'shop'),
        'message_form': MessageForm(),
        'partner': deal.partner_of(shop),
        'my_turn': my_turn,
        'can_send': deal.status == S.DRAFT and deal.proposer_id == shop.pk,
        'can_withdraw': deal.proposer_id == shop.pk and deal.status in (S.DRAFT, S.PROPOSED, S.COUNTERED),
        'can_message': deal.status in Deal.LIVE,
        'is_proposer': deal.proposer_id == shop.pk,
    }
    context.update(_qr_context(request, deal, shop))
    return render(request, 'deals/deal_detail.html', context)


@owner_required
@require_POST
def deal_action(request, pk, action):
    deal = _party_deal_or_404(request, pk)
    handlers = {
        'send': (services.send_proposal, 'Proposal sent.'),
        'accept': (services.accept, 'Deal accepted.'),
        'decline': (services.decline, 'Deal declined.'),
        'withdraw': (services.withdraw, 'Deal withdrawn.'),
    }
    if action not in handlers:
        raise Http404('Unknown action')
    handler, success = handlers[action]
    try:
        handler(deal, request.user)
    except DealError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, success)
    return redirect(deal)


@owner_required
def deal_counter(request, pk):
    deal = _party_deal_or_404(request, pk)
    if not (deal.status in Deal.OPEN_NEGOTIATION and deal.turn_id == request.shop.pk):
        messages.error(request, 'It is not your turn to respond.')
        return redirect(deal)
    form = DealTermsForm(request.POST or None, initial=_terms_initial(deal.current_version))
    if request.method == 'POST' and form.is_valid():
        try:
            services.counter(deal, request.user, form.cleaned_data)
        except DealError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Counter-offer sent.')
            return redirect(deal)
    return render(request, 'deals/deal_form.html', {
        'form': form, 'recipient': deal.partner_of(request.shop), 'mode': 'counter', 'deal': deal,
    })


@owner_required
@require_POST
def deal_message(request, pk):
    deal = _party_deal_or_404(request, pk)
    form = MessageForm(request.POST)
    if form.is_valid():
        DealMessage.objects.create(deal=deal, author=request.user, shop=request.shop,
                                   body=form.cleaned_data['body'])
    else:
        messages.error(request, 'Write a message first.')
    return redirect(deal)


@owner_required
def deal_summary(request, pk):
    deal = _party_deal_or_404(request, pk)
    context = {'deal': deal, 'summary': services.summary(deal)}
    context.update(_qr_context(request, deal, request.shop))
    return render(request, 'deals/deal_summary.html', context)


# ---------------------------------------------------------------------------
# AI drafting
# ---------------------------------------------------------------------------

@owner_required
@require_POST
def ai_draft(request):
    if not throttle.allow(f'ai-draft:{request.user.pk}', settings.AI_DRAFT_LIMIT_PER_HOUR):
        return JsonResponse({'error': 'Too many AI requests. Try again later.'}, status=429)
    recipient = Shop.objects.filter(pk=request.POST.get('recipient_id'),
                                    status=Shop.Status.APPROVED).first()
    if recipient is None or recipient.pk == request.shop.pk:
        return JsonResponse({'error': 'Pick a shop to propose to first.'}, status=400)
    return JsonResponse(draft_deal(request.shop, recipient))


# ---------------------------------------------------------------------------
# Exports (parties to the deal only)
# ---------------------------------------------------------------------------

def _redemption_rows(deal):
    redemptions = (Redemption.objects.filter(voucher__deal=deal)
                   .select_related('voucher__referring_shop', 'voucher__honoring_shop', 'confirmed_by')
                   .order_by('confirmed_at'))
    return [{
        'redemption_id': r.pk,
        'deal_id': deal.pk,
        'referred_by': r.voucher.referring_shop.name,
        'honored_at': r.voucher.honoring_shop.name,
        'confirmed_at': r.confirmed_at.isoformat(),
        'confirmed_by': r.confirmed_by.username if r.confirmed_by else '',
    } for r in redemptions]


def _export_name(deal, ext):
    return f'shopmates_deal-{deal.pk}_{timezone.localtime():%Y-%m-%d_%H-%M}.{ext}'


@owner_required
def export_csv(request, pk):
    deal = _party_deal_or_404(request, pk)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{_export_name(deal, "csv")}"'
    fields = ['redemption_id', 'deal_id', 'referred_by', 'honored_at', 'confirmed_at', 'confirmed_by']
    writer = csv.DictWriter(response, fieldnames=fields)
    writer.writeheader()
    writer.writerows(_redemption_rows(deal))
    return response


@owner_required
def export_json(request, pk):
    deal = _party_deal_or_404(request, pk)
    rows = _redemption_rows(deal)
    summary = services.summary(deal)
    response = JsonResponse({
        'generated_at': timezone.now().isoformat(),
        'record_count': len(rows),
        'deal': {
            'id': deal.pk,
            'status': deal.status,
            'shops': [deal.proposer.name, deal.recipient.name],
            'offer': deal.current_version.offer_text,
            'discount_percent': deal.current_version.discount_percent,
        },
        'summary': [{'shop': s['shop'].name, 'sent': s['sent'], 'received': s['received'],
                     'estimated_discount_cost': s['cost']} for s in summary['sides']],
        'redemptions': rows,
    }, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="{_export_name(deal, "json")}"'
    return response


# ---------------------------------------------------------------------------
# Customer pages (no account)
# ---------------------------------------------------------------------------

def _deal_by_token_or_404(token):
    deal = Deal.objects.select_related('proposer', 'recipient').filter(
        Q(proposer_token=token) | Q(recipient_token=token)).first()
    if deal is None:
        raise Http404('Offer not found')
    referring = deal.proposer if deal.proposer_token == token else deal.recipient
    return deal, referring


def voucher_start(request, token):
    deal, referring = _deal_by_token_or_404(token)
    services.sync_status(deal)
    honoring = deal.partner_of(referring)
    available = deal.status == S.ACTIVE
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        if not throttle.allow(f'voucher:{ip}', settings.VOUCHER_ISSUE_LIMIT_PER_HOUR):
            return render(request, 'deals/voucher_start.html', {
                'deal': deal, 'referring': referring, 'honoring': honoring, 'available': available,
                'version': deal.current_version, 'error': 'Too many requests. Try again later.'}, status=429)
        try:
            voucher = services.issue_voucher(deal, referring)
        except DealError as exc:
            return render(request, 'deals/voucher_start.html', {
                'deal': deal, 'referring': referring, 'honoring': honoring, 'available': False,
                'version': deal.current_version, 'error': str(exc)})
        return redirect('deals:voucher_show', code=voucher.code)
    return render(request, 'deals/voucher_start.html', {
        'deal': deal, 'referring': referring, 'honoring': honoring,
        'available': available, 'version': deal.current_version})


def voucher_show(request, code):
    voucher = get_object_or_404(
        Voucher.objects.select_related('deal', 'honoring_shop', 'referring_shop'),
        code=services.normalize_code(code))
    used = Redemption.objects.filter(voucher=voucher).exists()
    return render(request, 'deals/voucher_show.html', {
        'voucher': voucher,
        'version': voucher.deal.current_version,
        'used': used,
        'expired': voucher.expires_at < timezone.now(),
    })


# ---------------------------------------------------------------------------
# Staff redeem page
# ---------------------------------------------------------------------------

@approved_shop_required
def redeem(request):
    form = RedeemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            redemption = services.redeem_voucher(form.cleaned_data['code'], request.user)
        except RedeemError as exc:
            messages.error(request, str(exc))
        else:
            v = redemption.voucher.deal.current_version
            messages.success(
                request,
                f'Confirmed. Give the customer their offer: {v.offer_text} ({v.discount_percent}% off).')
        return redirect('deals:redeem')
    recent = (Redemption.objects.filter(voucher__honoring_shop=request.shop)
              .select_related('voucher__referring_shop')[:10])
    return render(request, 'deals/redeem.html', {'form': form, 'recent': recent})


# ---------------------------------------------------------------------------
# Public stats page
# ---------------------------------------------------------------------------

def stats_page(request):
    return render(request, 'deals/stats.html', {'stats': public_stats()})
