from django.urls import path

from . import api, views

app_name = 'deals'

urlpatterns = [
    path('inbox/', views.inbox, name='inbox'),

    # Negotiation
    path('deals/new/<int:shop_pk>/', views.deal_new, name='new'),
    path('deals/ai-draft/', views.ai_draft, name='ai_draft'),
    path('deals/fairness/<int:partner_id>/', views.fairness_preview, name='fairness'),
    path('deals/<int:pk>/', views.deal_detail, name='detail'),
    path('deals/<int:pk>/edit/', views.deal_edit, name='edit'),
    path('deals/<int:pk>/qr/', views.deal_qr, name='qr'),
    path('deals/<int:pk>/card/', views.deal_card, name='card'),
    path('deals/<int:pk>/qr.png', views.deal_qr_file, {'kind': 'png'}, name='qr_png'),
    path('deals/<int:pk>/qr.svg', views.deal_qr_file, {'kind': 'svg'}, name='qr_svg'),
    path('deals/<int:pk>/qr.pdf', views.deal_qr_file, {'kind': 'pdf'}, name='qr_pdf'),
    path('deals/<int:pk>/action/<str:action>/', views.deal_action, name='action'),
    path('deals/<int:pk>/counter/', views.deal_counter, name='counter'),
    path('deals/<int:pk>/message/', views.deal_message, name='message'),
    path('deals/<int:pk>/summary/', views.deal_summary, name='summary'),
    path('deals/<int:pk>/coach/', views.deal_coach, name='coach'),
    path('playbook/', views.playbook_page, name='playbook'),
    path('deals/<int:pk>/export.csv', views.export_csv, name='export_csv'),
    path('deals/<int:pk>/export.json', views.export_json, name='export_json'),

    # Customers (no account) and staff
    path('v/<uuid:token>/', views.voucher_start, name='voucher_start'),
    path('voucher/<str:code>/', views.voucher_show, name='voucher_show'),
    path('redeem/', views.redeem, name='redeem'),

    # Public stats page and APIs
    path('stats/', views.stats_page, name='stats'),
    path('api/stats/', api.api_stats, name='api_stats'),
    path('api/deals/', api.api_deals, name='api_deals'),
    path('api/deals/<int:pk>/redemptions/', api.api_deal_redemptions, name='api_redemptions'),
]
