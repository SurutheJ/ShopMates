from django.db.models import Q
from django.utils import timezone

from deals.models import Deal

from .access import get_membership
from .models import ShopMembership

# Which nav item is lit for each page. Follows data-nav in design/shell-demo.html.
NAV_FOR_VIEW = {
    'deals:inbox': 'inbox', 'deals:detail': 'inbox', 'deals:edit': 'inbox', 'deals:qr': 'inbox', 'deals:counter': 'inbox', 'deals:summary': 'inbox',
    'accounts:discover': 'discover', 'accounts:shop_detail': 'discover', 'deals:new': 'discover',
    'deals:redeem': 'redeem',
    'deals:playbook': 'playbook',
    'accounts:shop_edit': 'me', 'accounts:shop_staff': 'me',
}


def current_shop(request):
    """Make the signed-in user's shop, role, nav state and inbox badge available to every template."""
    membership = get_membership(request.user) if hasattr(request, 'user') else None
    shop = membership.shop if membership else None
    match = getattr(request, 'resolver_match', None)
    waiting = 0
    if shop and shop.is_approved and membership.role == ShopMembership.Role.OWNER:
        not_expired = Q(response_deadline__isnull=True) | Q(response_deadline__gte=timezone.now())
        waiting = Deal.objects.filter(not_expired, status__in=Deal.OPEN_NEGOTIATION, turn=shop).count()
    return {
        'my_membership': membership,
        'my_shop': shop,
        'nav_active': NAV_FOR_VIEW.get(match.view_name) if match else None,
        'inbox_waiting': waiting,
    }
