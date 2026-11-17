from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai import osm
from ai.matching import match_score
from ai.radar import radar as radar_results
from shopmates_project.links import absolute_url

from .access import approved_shops, get_membership, owner_required, shop_required
from .forms import ShopForm, StaffAddForm
from .models import Shop, ShopMembership


def home(request):
    if request.user.is_authenticated and get_membership(request.user):
        return redirect('deals:inbox')
    return render(request, 'home.html')


@login_required
def shop_create(request):
    if get_membership(request.user):
        return redirect('accounts:shop_edit')
    form = ShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        shop = form.save(commit=False)
        shop.status = Shop.Status.APPROVED if settings.SHOPS_AUTO_APPROVE else Shop.Status.PENDING
        shop.save()
        ShopMembership.objects.create(user=request.user, shop=shop, role=ShopMembership.Role.OWNER)
        if shop.is_approved:
            messages.success(request, 'Shop created. You can find neighbors and propose a deal.')
        else:
            messages.success(request, 'Shop created. An admin will approve it before you can propose deals.')
        return redirect('home')
    return render(request, 'accounts/shop_form.html', {'form': form, 'creating': True})


@shop_required
def shop_edit(request):
    if request.membership.role != ShopMembership.Role.OWNER:
        return render(request, 'accounts/forbidden.html',
                      {'message': 'Only shop owners can edit the shop.'}, status=403)
    form = ShopForm(request.POST or None, instance=request.shop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Shop updated.')
        return redirect('accounts:shop_edit')
    return render(request, 'accounts/shop_form.html', {'form': form, 'creating': False})


@owner_required
def shop_staff(request):
    form = StaffAddForm(request.POST or None, shop=request.shop)
    if request.method == 'POST' and form.is_valid():
        ShopMembership.objects.create(
            user=form.user_to_add, shop=request.shop, role=ShopMembership.Role.STAFF)
        messages.success(request, f'{form.user_to_add.username} added as staff.')
        return redirect('accounts:shop_staff')
    memberships = request.shop.memberships.select_related('user').order_by('role', 'user__username')
    return render(request, 'accounts/shop_staff.html', {'form': form, 'memberships': memberships})


@owner_required
@require_POST
def shop_staff_remove(request, pk):
    membership = get_object_or_404(
        ShopMembership, pk=pk, shop=request.shop, role=ShopMembership.Role.STAFF)
    membership.delete()
    messages.success(request, 'Staff member removed.')
    return redirect('accounts:shop_staff')


@shop_required
def discover(request):
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'match')
    shops = approved_shops().exclude(pk=request.shop.pk)
    if q:
        shops = shops.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if category in Shop.Category.values:
        shops = shops.filter(category=category)
    results = []
    for s in shops:
        distance = request.shop.distance_miles_to(s)
        results.append({'shop': s, 'distance': distance, 'match': match_score(request.shop, s, distance)})
    if sort == 'distance':
        # Nearest first when we know distances, otherwise by name.
        results.sort(key=lambda r: (r['distance'] is None, r['distance'] or 0, r['shop'].name.lower()))
    else:
        results.sort(key=lambda r: (-r['match']['score'], r['shop'].name.lower()))
    return render(request, 'accounts/discover.html', {
        'results': results,
        'q': q,
        'category': category,
        'sort': sort,
        'categories': [(value, label.split(' and ')[0]) for value, label in Shop.Category.choices],
        'can_propose': request.shop.is_approved,
    })


@shop_required
def radar(request):
    radius = request.GET.get('radius', '')
    radius = int(radius) if radius in ('300', '600', '1000') else 600
    category = request.GET.get('category', '').strip()
    if category not in Shop.Category.values:
        category = ''
    has_location = request.shop.latitude is not None and request.shop.longitude is not None
    places, osm_unavailable = [], False
    if settings.RADAR_OSM_ENABLED and has_location:
        places, osm_unavailable = osm.nearby(request.shop.latitude, request.shop.longitude, radius)
        places = osm.drop_registered(places, Shop.objects.exclude(latitude=None).exclude(longitude=None))
    # Every shop is scored before the category filter, so a shop's score does not change with the filter.
    results = radar_results(request.shop, approved_shops().exclude(pk=request.shop.pk), radius, places)
    if category:
        results = [r for r in results if r['shop'].category == category]
    return render(request, 'accounts/radar.html', {
        'results': results,
        'osm_unavailable': osm_unavailable,
        'site_url': absolute_url(request, '/'),
        'points': {
            'me': {'name': request.shop.name, 'lat': request.shop.latitude, 'lon': request.shop.longitude},
            'shops': [{
                'id': r['shop'].pk if r['registered'] else f"{r['place']['osm_type']}/{r['place']['osm_id']}",
                'name': r['shop'].name, 'lat': r['shop'].latitude, 'lon': r['shop'].longitude,
                'score': r['score'], 'tier': r['tier'], 'registered': r['registered'],
            } for r in results],
        },
        'radius': radius,
        'radii': [300, 600, 1000],
        'category': category,
        'categories': [(value, label.split(' and ')[0]) for value, label in Shop.Category.choices],
        'has_location': has_location,
        'few_results': 0 < len(results) < 3,
        'shop_approved': request.shop.is_approved,
        'can_propose': request.shop.is_approved and request.membership.role == ShopMembership.Role.OWNER,
    })


@shop_required
def shop_detail(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    # Unapproved shops are only visible to their own members.
    if not shop.is_approved and shop.pk != request.shop.pk:
        return render(request, 'accounts/forbidden.html', {'message': 'Shop not found.'}, status=404)
    return render(request, 'accounts/shop_detail.html', {
        'shop': shop,
        'distance': request.shop.distance_miles_to(shop),
        'match': None if shop.pk == request.shop.pk else match_score(
            request.shop, shop, request.shop.distance_miles_to(shop)),
        'is_mine': shop.pk == request.shop.pk,
        'can_propose': request.shop.is_approved and shop.is_approved and shop.pk != request.shop.pk,
    })
