from django import forms
from django.contrib.auth import get_user_model

from .models import Shop, ShopMembership


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'category', 'address', 'city', 'hours', 'description', 'typical_order_value',
                  'margin_pct', 'latitude', 'longitude']
        help_texts = {
            'latitude': 'Optional. Lets other shops see how far away you are.',
            'longitude': 'Optional.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input'   # the designv2 field style; these screens are outside .legacy

    def clean(self):
        cleaned = super().clean()
        lat, lon = cleaned.get('latitude'), cleaned.get('longitude')
        if (lat is None) != (lon is None):
            raise forms.ValidationError('Enter both latitude and longitude, or leave both blank.')
        if lat is not None and not (-90 <= lat <= 90):
            self.add_error('latitude', 'Latitude must be between -90 and 90.')
        if lon is not None and not (-180 <= lon <= 180):
            self.add_error('longitude', 'Longitude must be between -180 and 180.')
        return cleaned


class StaffAddForm(forms.Form):
    identifier = forms.CharField(
        label='Username or email of an existing account',
        max_length=150,
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shop = shop
        self.fields['identifier'].widget.attrs['class'] = 'input'

    def clean_identifier(self):
        value = self.cleaned_data['identifier'].strip()
        User = get_user_model()
        user = (User.objects.filter(username__iexact=value).first()
                or User.objects.filter(email__iexact=value).first())
        if user is None:
            raise forms.ValidationError('No account found. Ask them to sign up first.')
        if ShopMembership.objects.filter(user=user).exists():
            raise forms.ValidationError('That account already belongs to a shop.')
        self.user_to_add = user
        return value
