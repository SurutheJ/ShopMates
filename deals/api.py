"""
JSON APIs.

  GET /api/stats/                      PUBLIC. Anonymized aggregates only.
  GET /api/deals/                      Login. The caller's own shop's deals.
  GET /api/deals/<id>/redemptions/     Login, owner of a party to the deal.

Everything except /api/stats/ returns 401 JSON when logged out.
"""

from django.db.models import Q
from django.http import JsonResponse

from accounts.access import api_login_required, get_membership
from accounts.models import ShopMembership
from shopmates_project.timeutil import local_iso

from . import services
from .models import Deal, Redemption
from .stats import public_stats


def api_stats(request):
    response = JsonResponse(public_stats())
    # Public, read-only data: allow other sites (charts, notebooks) to read it.
    response['Access-Control-Allow-Origin'] = '*'
    return response


def _owner_membership_or_error(request):
    membership = get_membership(request.user)
    if membership is None:
        return None, JsonResponse({'error': 'Create a shop first.'}, status=403)
    if membership.role != ShopMembership.Role.OWNER:
        return None, JsonResponse({'error': 'Only shop owners can use this API.'}, status=403)
    return membership, None


@api_login_required
def api_deals(request):
    membership, error = _owner_membership_or_error(request)
    if error:
        return error
    shop = membership.shop
    deals = list(Deal.visible_to(shop)
                 .select_related('proposer', 'recipient').order_by('-updated_at'))
    services.sync_all(deals)
    results = []
    for deal in deals:
        version = deal.current_version
        results.append({
            'id': deal.pk,
            'status': deal.status,
            'partner': deal.partner_of(shop).name,
            'offer': version.offer_text,
            'discount_percent': version.discount_percent,
            'redemption_cap': version.redemption_cap,
            'start_date': version.start_date.isoformat(),
            'end_date': version.end_date.isoformat(),
            'redemptions_honored_here': services.redemptions_at(deal, shop),
        })
    return JsonResponse({'count': len(results), 'results': results})


@api_login_required
def api_deal_redemptions(request, pk):
    membership, error = _owner_membership_or_error(request)
    if error:
        return error
    deal = Deal.objects.select_related('proposer', 'recipient').filter(pk=pk).first()
    # Not a party: same answer as "does not exist", so the API can't be used to probe deal IDs.
    if deal is None or not deal.is_party(membership.shop):
        return JsonResponse({'error': 'Not found.'}, status=404)
    rows = (Redemption.objects.filter(voucher__deal=deal)
            .select_related('voucher__referring_shop', 'voucher__honoring_shop')
            .order_by('confirmed_at'))
    results = [{
        'id': r.pk,
        'referred_by': r.voucher.referring_shop.name,
        'honored_at': r.voucher.honoring_shop.name,
        'confirmed_at': local_iso(r.confirmed_at),
    } for r in rows]
    return JsonResponse({'deal_id': deal.pk, 'count': len(results), 'results': results})
