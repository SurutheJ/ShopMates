from django.contrib import admin

from .models import Deal, DealEvent, DealMessage, DealVersion, Redemption, Voucher


class VersionInline(admin.TabularInline):
    model = DealVersion
    extra = 0
    readonly_fields = ('number', 'created_by', 'created_by_shop', 'created_at')


class EventInline(admin.TabularInline):
    model = DealEvent
    extra = 0
    readonly_fields = ('actor', 'action', 'note', 'created_at')
    can_delete = False


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('id', 'proposer', 'recipient', 'status', 'updated_at')
    list_filter = ('status',)
    inlines = [VersionInline, EventInline]
    readonly_fields = ('proposer_token', 'recipient_token')


admin.site.register(DealMessage)
admin.site.register(Voucher)
admin.site.register(Redemption)
