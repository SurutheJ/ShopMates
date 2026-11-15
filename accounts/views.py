from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

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
    shops = approved_shops().exclude(pk=request.shop.pk)
    if q:
        shops = shops.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if category in Shop.Category.values:
        shops = shops.filter(category=category)
    results = [{'shop': s, 'distance': request.shop.distance_miles_to(s)} for s in shops]
    # Nearest first when we know distances, otherwise by name.
    results.sort(key=lambda r: (r['distance'] is None, r['distance'] or 0, r['shop'].name.lower()))
    return render(request, 'accounts/discover.html', {
        'results': results,
        'q': q,
        'category': category,
        'categories': Shop.Category.choices,
        'can_propose': request.shop.is_approved,
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
        'is_mine': shop.pk == request.shop.pk,
        'can_propose': request.shop.is_approved and shop.is_approved and shop.pk != request.shop.pk,
    })
