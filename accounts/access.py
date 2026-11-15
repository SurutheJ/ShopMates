"""Who is acting for which shop, and decorators that enforce it."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import Shop, ShopMembership


def get_membership(user):
    """The user's shop membership. MVP: one shop per user (multi-location is a later phase)."""
    if not getattr(user, 'is_authenticated', False):
        return None
    return ShopMembership.objects.select_related('shop').filter(user=user).order_by('id').first()


def shop_required(view):
    """Login required, and the user must belong to a shop (otherwise go set one up)."""
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        membership = get_membership(request.user)
        if membership is None:
            return redirect('accounts:shop_create')
        request.membership = membership
        request.shop = membership.shop
        return view(request, *args, **kwargs)
    return wrapped


def approved_shop_required(view):
    """Like shop_required, and the shop must be approved by an admin."""
    @wraps(view)
    @shop_required
    def wrapped(request, *args, **kwargs):
        if not request.shop.is_approved:
            return render(request, 'accounts/pending.html', {'shop': request.shop}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def owner_required(view):
    """Approved shop, and the user must be an owner (not just staff)."""
    @wraps(view)
    @approved_shop_required
    def wrapped(request, *args, **kwargs):
        if request.membership.role != ShopMembership.Role.OWNER:
            return render(request, 'accounts/forbidden.html',
                          {'message': 'Only shop owners can do this.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def api_login_required(view):
    """
    Like login_required, but for JSON APIs: a logged-out request gets a 401
    JSON error, not a redirect to an HTML login page a script cannot use.
    """
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'error': 'Authentication required. Log in to use this API.',
                 'login_url': request.build_absolute_uri(reverse('account_login'))},
                status=401,
            )
        return view(request, *args, **kwargs)
    return wrapped


def approved_shops():
    return Shop.objects.filter(status=Shop.Status.APPROVED)
