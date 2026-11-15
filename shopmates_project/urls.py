from django.contrib import admin
from django.urls import include, path

from accounts.views import home

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),   # login, signup, logout, Google
    path('', include('accounts.urls')),            # shop setup, discover
    path('', include('deals.urls')),               # deals, vouchers, redeem, APIs
]
