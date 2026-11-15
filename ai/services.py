"""
AI-assisted drafting. The model suggests; Python validates; a human approves.

The model never produces a number the app trusts without checking it against
the same rules as owner-typed terms (deals.forms.DealTermsForm). If the key is
missing, the call fails, or the output is invalid, a rule-based draft is
returned instead, so the feature never blocks the owner.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from deals.forms import DealTermsForm

from .client import AIError, default_client
from .prompts import build_draft_prompt

MESSAGE_MAX = 400


def draft_deal(proposer, recipient, client='default', today=None):
    """
    Returns {'source': 'ai' | 'fallback', 'reason': str, 'terms': {...}, 'message': str}.
    `terms` holds ISO date strings so it can fill an HTML form directly.
    """
    today = today or timezone.localdate()
    if client == 'default':
        client = default_client()

    reason = 'AI is not configured.'
    if client is not None:
        try:
            raw = client.generate_json(build_draft_prompt(proposer, recipient))
            return _validate(raw, today)
        except AIError as exc:
            reason = str(exc)
        except ValueError as exc:
            reason = f'The AI suggestion was not valid ({exc}).'
    return _fallback(proposer, recipient, today, reason)


def _validate(raw, today):
    try:
        days = int(raw['suggested_duration_days'])
        data = {
            'offer_text': str(raw['offer_text']).strip(),
            'discount_percent': raw['discount_percent'],
            'redemption_cap': raw['redemption_cap'],
            'start_date': today.isoformat(),
            'end_date': (today + timedelta(days=days)).isoformat(),
            'terms': '',
        }
        message = str(raw.get('message_to_neighbor', '')).strip()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('missing or malformed fields') from exc

    form = DealTermsForm(data)
    if not form.is_valid():
        problems = '; '.join(f'{field}: {errs[0]}' for field, errs in form.errors.items())
        raise ValueError(problems)
    if len(message) > MESSAGE_MAX:
        message = message[:MESSAGE_MAX].rstrip()
    return {'source': 'ai', 'reason': '', 'terms': data, 'message': message}


def _fallback(proposer, recipient, today, reason):
    discount = min(10, settings.DISCOUNT_MAX_PERCENT)
    terms = {
        'offer_text': f'{discount}% off one purchase for customers sent by a neighboring shop',
        'discount_percent': discount,
        'redemption_cap': 50,
        'start_date': today.isoformat(),
        'end_date': (today + timedelta(days=30)).isoformat(),
        'terms': '',
    }
    message = (
        f"Hi {recipient.name}, we're {proposer.name}. Would you like to swap a {discount}% "
        f"referral discount for 30 days? Each of us would honor up to 50 customers."
    )[:MESSAGE_MAX]
    return {'source': 'fallback', 'reason': reason, 'terms': terms, 'message': message}
