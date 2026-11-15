from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Shop, ShopMembership, User

admin.site.register(User, UserAdmin)


class MembershipInline(admin.TabularInline):
    model = ShopMembership
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'city', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('name', 'address')
    inlines = [MembershipInline]
    actions = ['approve', 'suspend']

    @admin.action(description='Approve selected shops')
    def approve(self, request, queryset):
        queryset.update(status=Shop.Status.APPROVED)

    @admin.action(description='Suspend selected shops')
    def suspend(self, request, queryset):
        queryset.update(status=Shop.Status.SUSPENDED)
