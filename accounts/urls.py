from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('shop/new/', views.shop_create, name='shop_create'),
    path('shop/edit/', views.shop_edit, name='shop_edit'),
    path('shop/staff/', views.shop_staff, name='shop_staff'),
    path('shop/staff/<int:pk>/remove/', views.shop_staff_remove, name='shop_staff_remove'),
    path('discover/', views.discover, name='discover'),
    path('shops/<int:pk>/', views.shop_detail, name='shop_detail'),
]
