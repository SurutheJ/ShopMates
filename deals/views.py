import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import segno
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from accounts.access import approved_shop_required, owner_required, shop_required
from accounts.models import Shop, ShopMembership
from ai.services import answer_playbook, draft_deal, explain_balance, suggest_renewal
from shopmates_project.links import absolute_url
from shopmates_project.timeutil import local_iso

from . import charts, services, throttle
from .fairness import fairness
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
    # Black on white with the full 4-module quiet zone scanners expect. CSS sets the size.
    return mark_safe(segno.make(url, error='q').svg_inline(
        scale=1, border=4, dark='#000', light='#fff', omitsize=True))


def _qr_context(request, deal, shop):
    if deal.status not in (S.ACCEPTED, S.ACTIVE):
        return {}
    url = absolute_url(request, reverse('deals:voucher_start', args=[deal.token_for(shop)]))
    return {'qr_url': url, 'qr_svg': _qr_svg(url)}


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

@shop_required
def inbox(request):
    shop = request.shop
    is_owner = request.membership.role == ShopMembership.Role.OWNER
    context = {'is_owner': is_owner}
    if shop.is_approved:
        deals = list(Deal.visible_to(shop)
                     .select_related('proposer', 'recipient', 'turn')
                     .prefetch_related('versions'))
        services.sync_all(deals)
        for deal in deals:
            deal.partner = deal.partner_of(shop)
            deal.version = deal.current_version
        if not is_owner:
            # Staff can see what is pending but cannot act on it; only the owner approves.
            context['pending'] = [d for d in deals if d.status in Deal.OPEN_NEGOTIATION]
            return render(request, 'deals/inbox.html', context)
        needs_response = [d for d in deals if d.status in Deal.OPEN_NEGOTIATION and d.turn_id == shop.pk]
        waiting = [d for d in deals if d.status in Deal.OPEN_NEGOTIATION and d.turn_id != shop.pk]
        drafts = [d for d in deals if d.status == S.DRAFT]
        context.update({
            'sent_this_month': services.customers_sent_this_month(shop),
            'selected': needs_response[0] if needs_response else None,   # shown in the preview pane on wide screens
            'needs_response': needs_response,
            'waiting': waiting,
            'drafts': drafts,
            'waiting_total': len(waiting) + len(drafts),
            'running': [d for d in deals if d.status in (S.ACCEPTED, S.ACTIVE)],
            'past': [d for d in deals if d.status in Deal.CLOSED],
        })
    return render(request, 'deals/inbox.html', context)


# ---------------------------------------------------------------------------
# Proposals and negotiation
# ---------------------------------------------------------------------------

def _renewable_deal(request, recipient):
    """The completed deal named by ?renew=<id>, if this shop was in it with `recipient`. Otherwise None."""
    pk = request.GET.get('renew', '')
    if not pk.isdigit():
        return None
    deal = Deal.objects.filter(pk=pk, status=S.COMPLETED).first()
    if deal and deal.is_party(request.shop) and deal.partner_of(request.shop).pk == recipient.pk:
        return deal
    return None


def _spend_note(mine, theirs):
    """One sentence for the wizard when the two shops' typical spends differ by 40% or more (the app's lopsided threshold), else ''."""
    a, b = mine.typical_order_value, theirs.typical_order_value
    if abs(a - b) / max(a, b) < 0.4:
        return ''
    if b > a:
        return 'Their customers spend more than yours, so equal discounts cost them more.'
    return 'Your customers spend more than theirs, so equal discounts cost you more.'


@owner_required
def deal_new(request, shop_pk):
    recipient = get_object_or_404(Shop, pk=shop_pk, status=Shop.Status.APPROVED)
    if recipient.pk == request.shop.pk:
        raise Http404('Pick a different shop')
    old = _renewable_deal(request, recipient)
    initial = services.renewal_terms(old) if old else _terms_initial()
    form = DealTermsForm(request.POST or None, initial=initial)
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
        'form': form, 'recipient': recipient, 'mode': 'new', 'renewing': old,
        'message': request.POST.get('message', ''), 'spend_note': _spend_note(request.shop, recipient),
    })


@owner_required
def deal_edit(request, pk):
    """Edit a draft before sending it. Only the proposing shop can even see this page."""
    deal = get_object_or_404(Deal.objects.select_related('proposer', 'recipient'), pk=pk, proposer=request.shop)
    if deal.status != S.DRAFT:
        messages.error(request, 'Only a draft can be edited.')
        return redirect(deal)
    note = deal.messages.filter(shop=request.shop).order_by('id').first()
    form = DealTermsForm(request.POST or None, initial=_terms_initial(deal.current_version))
    if request.method == 'POST' and form.is_valid():
        send = request.POST.get('action') == 'send'
        try:
            services.edit_draft(deal, request.user, form.cleaned_data)
            if send:
                services.send_proposal(deal, request.user)
        except DealError as exc:
            messages.error(request, str(exc))
        else:
            text = request.POST.get('message', '').strip()[:1000]
            if text and note:
                note.body = text
                note.save()
            elif text:
                DealMessage.objects.create(deal=deal, author=request.user, shop=request.shop, body=text)
            elif note:
                note.delete()
            messages.success(request, 'Proposal sent.' if send else 'Draft saved.')
            return redirect(deal)
    shown = request.POST.get('message') if request.method == 'POST' else (note.body if note else '')
    return render(request, 'deals/deal_form.html', {
        'form': form, 'recipient': deal.recipient, 'deal': deal, 'mode': 'edit', 'message': shown,
        'spend_note': _spend_note(request.shop, deal.recipient),
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
        'can_edit': deal.status == S.DRAFT and deal.proposer_id == shop.pk,
        'can_withdraw': deal.proposer_id == shop.pk and deal.status in (S.DRAFT, S.PROPOSED, S.COUNTERED),
        'can_renew': deal.status == S.COMPLETED and not Deal.objects.filter(
            status__in=Deal.LIVE, proposer__in=[deal.proposer, deal.recipient],
            recipient__in=[deal.proposer, deal.recipient]).exists(),
        'can_message': deal.status in Deal.LIVE,
        'is_proposer': deal.proposer_id == shop.pk,
    }
    context.update(_qr_context(request, deal, shop))
    return render(request, 'deals/deal_detail.html', context)


@owner_required
def deal_qr(request, pk):
    """The shop's own QR code, big, for showing on a phone or printing. Only while the deal can issue codes."""
    deal = _party_deal_or_404(request, pk)
    context = _qr_context(request, deal, request.shop)
    if not context:
        messages.error(request, 'The QR code is available once a deal is accepted, until it ends.')
        return redirect(deal)
    context.update({'deal': deal, 'version': deal.current_version, 'partner': deal.partner_of(request.shop)})
    return render(request, 'deals/qr.html', context)


@owner_required
def deal_card(request, pk):
    """A printable counter card (two copies per Letter page) with this shop's QR code and the deal terms."""
    deal = _party_deal_or_404(request, pk)
    context = _qr_context(request, deal, request.shop)
    if not context:
        messages.error(request, 'The counter card is available once a deal is accepted, until it ends.')
        return redirect(deal)
    context.update({
        'deal': deal, 'version': deal.current_version, 'partner': deal.partner_of(request.shop),
        'link_text': context['qr_url'].split('://', 1)[-1], 'ttl_hours': settings.VOUCHER_TTL_HOURS,
    })
    return render(request, 'deals/card.html', context)


QR_PNG_MIN_PX = 1200   # 4 inches at 300 dpi


def qr_png_scale(code):
    """The smallest whole-number scale that makes the PNG at least QR_PNG_MIN_PX wide. Whole numbers keep the squares sharp."""
    modules = code.symbol_size(border=4)[0]
    return -(-QR_PNG_MIN_PX // modules)


# SVG and PDF are vector (sharp at any size, best for printing). PDF scale 10 makes a page about 6 inches square.
QR_FILES = {'png': 'image/png', 'svg': 'image/svg+xml', 'pdf': 'application/pdf'}


@owner_required
def deal_qr_file(request, pk, kind):
    """The shop's QR code as a PNG, SVG or PDF download, same rules as the QR page."""
    deal = _party_deal_or_404(request, pk)
    context = _qr_context(request, deal, request.shop)
    if not context:
        messages.error(request, 'The QR code is available once a deal is accepted, until it ends.')
        return redirect(deal)
    code = segno.make(context['qr_url'], error='q')
    options = {'png': {'scale': qr_png_scale(code)},
               'svg': {'scale': 10, 'xmldecl': True, 'title': f'{request.shop.name} QR code'},
               'pdf': {'scale': 10}}[kind]
    buffer = io.BytesIO()
    code.save(buffer, kind=kind, border=4, dark='#000', light='#fff', **options)
    response = HttpResponse(buffer.getvalue(), content_type=QR_FILES[kind])
    response['Content-Disposition'] = f'attachment; filename="shopmates-{slugify(request.shop.name)}-qr.{kind}"'
    return response


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
    return redirect(deal.get_absolute_url() + '?tab=chat')   # stay on the Chat tab


@owner_required
def deal_summary(request, pk):
    deal = _party_deal_or_404(request, pk)
    summary = services.summary(deal)
    context = {
        'deal': deal, 'summary': summary,
        'renewal': suggest_renewal(summary),
        'chart_svg': charts.redemptions_chart(deal),
    }
    context.update(_qr_context(request, deal, request.shop))
    return render(request, 'deals/deal_summary.html', context)


@owner_required
@require_POST
def deal_coach(request, pk):
    """AI explanation of a deal's balance. Numbers come from the database; the model only words them."""
    deal = _party_deal_or_404(request, pk)
    if not throttle.allow(f'ai-coach:{request.user.pk}', settings.AI_DRAFT_LIMIT_PER_HOUR):
        return JsonResponse({'error': 'Too many AI requests. Try again later.'}, status=429)
    result = explain_balance(services.summary(deal))
    result.pop('facts', None)
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Playbook (retrieval-augmented Q&A)
# ---------------------------------------------------------------------------

@owner_required
def playbook_page(request):
    question = request.GET.get('q', '').strip()
    result = None
    if question:
        if throttle.allow(f'ai-playbook:{request.user.pk}', settings.AI_DRAFT_LIMIT_PER_HOUR):
            result = answer_playbook(question)
        else:
            messages.error(request, 'Too many AI requests. Try again later.')
    return render(request, 'deals/playbook.html', {
        'question': question, 'result': result,
        'examples': ['What deal should a bakery offer a flower shop?',
                     'Our deal feels unfair, what can we change?',
                     'How do I pick a redemption cap?'],
    })


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
# Fairness estimate (plain math in fairness.py, no AI)
# ---------------------------------------------------------------------------

ASSUMED_MARGIN = Decimal('50')


@owner_required
@require_POST
def fairness_preview(request, partner_id):
    """What each shop is estimated to earn from the terms in the wizard: this shop (a) against the partner (b)."""
    partner = get_object_or_404(Shop, pk=partner_id, status=Shop.Status.APPROVED)
    if partner.pk == request.shop.pk:
        raise Http404('Pick a different shop')
    try:
        mine = int(request.POST.get('discount_percent', ''))
        theirs = int(request.POST.get('partner_discount_percent', mine))
        cap = int(request.POST.get('cap', ''))
        days = (date.fromisoformat(request.POST.get('end_date', ''))
                - date.fromisoformat(request.POST.get('start_date', ''))).days
    except ValueError:
        return JsonResponse({'error': 'Enter whole numbers and valid dates.'}, status=400)
    if not (1 <= mine <= 100 and 1 <= theirs <= 100 and cap >= 1 and days >= 0):
        return JsonResponse({'error': 'Discounts are 1 to 100, the cap at least 1, and the end date on or after the start.'},
                            status=400)

    def side(shop, discount):
        return {'name': shop.name, 'ticket': shop.typical_order_value, 'margin_pct': ASSUMED_MARGIN if shop.margin_pct is None else shop.margin_pct,
                'discount_percent': discount, 'cap': cap}

    result = fairness(side(request.shop, mine), side(partner, theirs), months=max(1, round(days / 30)))
    result['margin_assumed'] = request.shop.margin_pct is None or partner.margin_pct is None
    return JsonResponse(result)


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
        'confirmed_at': local_iso(r.confirmed_at),
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
        'generated_at': local_iso(timezone.now()),
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
    recent = (Redemption.objects.filter(voucher__honoring_shop=request.shop)
              .select_related('voucher__referring_shop')[:10])
    # Limit by user, not IP: this page needs a login, and behind a proxy many
    # shops can share one IP address.
    if request.method == 'POST' and not throttle.allow(
            f'redeem:{request.user.pk}', settings.REDEEM_LIMIT_PER_HOUR):
        messages.error(request, 'Too many attempts. Try again in an hour.')
        return render(request, 'deals/redeem.html', {'form': RedeemForm(), 'recent': recent}, status=429)
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
    return render(request, 'deals/redeem.html', {'form': form, 'recent': recent})


# ---------------------------------------------------------------------------
# Public stats page
# ---------------------------------------------------------------------------

def stats_page(request):
    return render(request, 'deals/stats.html', {'stats': public_stats()})
