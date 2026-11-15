from datetime import timedelta

from django import forms
from django.conf import settings
from django.utils import timezone


class DealTermsForm(forms.Form):
    """
    The single source of truth for what valid deal terms look like. Used for
    owner-typed terms and to validate anything the AI assistant suggests.
    """

    offer_text = forms.CharField(
        label='Offer', max_length=200,
        help_text='What a referred customer gets, for example "10% off any drink".')
    discount_percent = forms.IntegerField(label='Discount (%)', min_value=1)
    redemption_cap = forms.IntegerField(
        label='Redemption cap (per shop)', min_value=1,
        help_text='Most customers each shop will honor.')
    start_date = forms.DateField(label='Start date', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='End date', widget=forms.DateInput(attrs={'type': 'date'}))
    terms = forms.CharField(label='Other terms', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean_discount_percent(self):
        value = self.cleaned_data['discount_percent']
        if value > settings.DISCOUNT_MAX_PERCENT:
            raise forms.ValidationError(f'Discount can be at most {settings.DISCOUNT_MAX_PERCENT}%.')
        return value

    def clean_redemption_cap(self):
        value = self.cleaned_data['redemption_cap']
        if value > settings.REDEMPTION_CAP_MAX:
            raise forms.ValidationError(f'Cap can be at most {settings.REDEMPTION_CAP_MAX}.')
        return value

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        today = timezone.localdate()
        if start and end:
            if end < start:
                self.add_error('end_date', 'The end date must be on or after the start date.')
            elif end < today:
                self.add_error('end_date', 'The end date can not be in the past.')
            elif (end - start) > timedelta(days=settings.DEAL_MAX_DAYS):
                self.add_error('end_date', f'A deal can last at most {settings.DEAL_MAX_DAYS} days.')
        return cleaned


class MessageForm(forms.Form):
    body = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows': 2}), label='Message')


class RedeemForm(forms.Form):
    code = forms.CharField(
        max_length=20, label='Customer code',
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters'}))
