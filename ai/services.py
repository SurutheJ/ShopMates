"""
AI-assisted drafting. The model suggests; Python validates; a human approves.

The model never produces a number the app trusts without checking it against
the same rules as owner-typed terms (deals.forms.DealTermsForm). If the key is
missing, the call fails, or the output is invalid, a rule-based draft is
returned instead, so the feature never blocks the owner.
"""

import logging
import math
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from deals.forms import DealTermsForm

from . import playbook
from .client import AIError, default_client
from .prompts import build_balance_prompt, build_draft_prompt, build_playbook_prompt

logger = logging.getLogger('ai')

MESSAGE_MAX = 400


def draft_deal(proposer, recipient, client='default', today=None):
    """
    Returns {'source': 'ai' | 'fallback', 'reason': str, 'terms': {...}, 'message': str}.
    `terms` holds ISO date strings so it can fill an HTML form directly.
    """
    today = today or timezone.localdate()
    if client == 'default':
        client = default_client()

    passages = playbook.passages_for_pair(proposer, recipient)
    sources = [p['title'] for p in passages]

    reason = 'AI is not configured.'
    if client is not None:
        try:
            raw = client.generate_json(build_draft_prompt(proposer, recipient, passages))
            result = _validate(raw, today, (proposer, recipient))
            result['sources'] = sources
            return result
        except AIError as exc:
            reason = str(exc)
            logger.warning('draft used the fallback: %s', reason)
        except ValueError as exc:
            reason = f'The AI suggestion was not valid ({exc}).'
            logger.warning('draft used the fallback: %s', reason)
    result = _fallback(proposer, recipient, today, reason)
    result['sources'] = sources
    return result


def _validate(raw, today, shops=()):
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
    # Same rule as the coach: the sentences may only use numbers the app checked
    # (or gave the model), so they cannot contradict the fields above.
    allowed = {float(data['discount_percent']), float(data['redemption_cap']), float(days)}
    allowed |= {round(float(shop.typical_order_value), 2) for shop in shops}
    if _numbers_in(f"{data['offer_text']} {message}") - allowed:
        raise ValueError('the text used numbers that differ from the checked terms')
    if len(message) > MESSAGE_MAX:
        message = message[:MESSAGE_MAX].rstrip()
    return {'source': 'ai', 'reason': '', 'terms': data, 'message': message}


def fallback_cap(proposer, recipient, base_cap=50):
    """
    The same cap applies to both shops, so a big gap in typical spend means the
    higher-priced shop could pay much more for the same number of redemptions.
    Scale the cap down by the spend ratio (never below 10, rounded to 5) to
    limit that exposure. Added after evaluation test 5 (docs/EVALUATION.md).
    """
    low, high = sorted((float(proposer.typical_order_value), float(recipient.typical_order_value)))
    ratio = low / high
    if ratio >= 0.6:
        return base_cap
    return max(10, int(round(base_cap * ratio / 5.0)) * 5)


def _fallback(proposer, recipient, today, reason):
    discount = min(10, settings.DISCOUNT_MAX_PERCENT)
    cap = fallback_cap(proposer, recipient)
    terms = {
        'offer_text': f'{discount}% off one purchase for customers sent by a neighboring shop',
        'discount_percent': discount,
        'redemption_cap': cap,
        'start_date': today.isoformat(),
        'end_date': (today + timedelta(days=30)).isoformat(),
        'terms': '',
    }
    message = (
        f"Hi {recipient.name}, we're {proposer.name}. Would you like to swap a {discount}% "
        f"referral discount for 30 days? Each of us would honor up to {cap} customers."
    )[:MESSAGE_MAX]
    return {'source': 'fallback', 'reason': reason, 'terms': terms, 'message': message}


# ---------------------------------------------------------------------------
# Deal coach: explain the balance of a running deal and suggest a renewal
# ---------------------------------------------------------------------------

EXPLANATION_MAX = 500
_NUMBER = re.compile(r'\d+(?:\.\d+)?')


def balance_facts(summary):
    """The numbers the coach is allowed to talk about. All computed from the database."""
    a, b = summary['sides']
    version = summary['version']
    return {
        'discount_percent': version.discount_percent,
        'total_redemptions': summary['total'],
        'lopsided': summary['lopsided'],
        'shops': [{
            'name': side['shop'].name,
            'customers_sent': side['sent'],
            'customers_received': side['received'],
            'discount_cost_usd': side['cost'],
        } for side in (a, b)],
    }


def suggest_renewal(summary):
    """
    Renewal terms, computed in Python (the model never sets numbers).

    If the deal is lopsided, raise the cap so the busier side is not cut off
    and ask the shop that received more to add a small perk. Otherwise repeat
    the terms.
    """
    version = summary['version']
    days = max(1, (version.end_date - version.start_date).days)
    cap = version.redemption_cap
    perk = ''
    if summary['lopsided']:
        busiest = max(max(s['sent'], s['received']) for s in summary['sides'])
        cap = max(cap, int(math.ceil(busiest * 1.25 / 5.0) * 5))
        receiver = max(summary['sides'], key=lambda s: s['received'])['shop']
        giver = min(summary['sides'], key=lambda s: s['received'])['shop']
        perk = (f'{receiver.name} adds a small free item for customers sent by {giver.name}, '
                f'to even out who benefits.')
    return {'discount_percent': version.discount_percent, 'redemption_cap': cap,
            'duration_days': days, 'perk': perk}


def _allowed_numbers(facts):
    allowed = set()

    def add(value):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            allowed.add(round(float(value), 2))
        elif isinstance(value, dict):
            for v in value.values():
                add(v)
        elif isinstance(value, list):
            for v in value:
                add(v)

    add(facts)
    return allowed


def _numbers_in(text):
    return {round(float(n), 2) for n in _NUMBER.findall(text)}


def _fallback_explanation(facts):
    a, b = facts['shops']
    if facts['total_redemptions'] == 0:
        return 'No customers have redeemed this deal yet. Check back after a few redemptions.'
    sent_gap = abs(a['customers_sent'] - b['customers_sent'])
    more, less = (a, b) if a['customers_sent'] >= b['customers_sent'] else (b, a)
    text = (f"{a['name']} sent {a['customers_sent']} customers and {b['name']} sent "
            f"{b['customers_sent']}. Estimated discount cost: {a['name']} ${a['discount_cost_usd']:.2f}, "
            f"{b['name']} ${b['discount_cost_usd']:.2f}.")
    if facts['lopsided']:
        text += (f" {more['name']} is sending {sent_gap} more customers than {less['name']}, "
                 f"so consider a renewal with a higher cap and a small perk from {less['name']}.")
    elif facts['total_redemptions'] < 4:
        text += ' It is too early to judge fairness.'
    else:
        text += ' The exchange looks balanced.'
    return text


def explain_balance(summary, client='default'):
    """
    Returns {'source': 'ai' | 'fallback', 'reason', 'explanation', 'renewal', 'facts'}.

    The model only words the explanation. Any number it writes must appear in
    the facts the app computed, otherwise the explanation is rejected and a
    templated one is used instead.
    """
    if client == 'default':
        client = default_client()
    facts = balance_facts(summary)
    renewal = suggest_renewal(summary)
    result = {'facts': facts, 'renewal': renewal}

    reason = 'AI is not configured.'
    if client is not None:
        try:
            raw = client.generate_json(build_balance_prompt(facts))
            text = str(raw.get('explanation', '')).strip()
            if not text:
                raise ValueError('empty explanation')
            stray = _numbers_in(text) - _allowed_numbers(facts)
            if stray:
                raise ValueError('it used numbers the app did not compute')
            return {**result, 'source': 'ai', 'reason': '', 'explanation': text[:EXPLANATION_MAX]}
        except AIError as exc:
            reason = str(exc)
            logger.warning('coach used the fallback: %s', reason)
        except (ValueError, AttributeError) as exc:
            reason = f'The AI explanation was rejected ({exc}).'
            logger.warning('coach used the fallback: %s', reason)
    return {**result, 'source': 'fallback', 'reason': reason,
            'explanation': _fallback_explanation(facts)}


# ---------------------------------------------------------------------------
# Playbook Q&A (retrieval-augmented)
# ---------------------------------------------------------------------------

ANSWER_MAX = 600


def answer_playbook(question, client='default', k=3):
    """
    Retrieve the best playbook passages, then (if the model is available) have
    it answer from those passages only. Returns
    {'source', 'reason', 'answer', 'passages'}; `answer` is '' when only the
    passages are shown.
    """
    question = (question or '').strip()[:300]
    passages = playbook.search(question, k=k)
    if not passages:
        return {'source': 'none', 'reason': 'No playbook passage matched that question.',
                'answer': '', 'passages': []}
    if client == 'default':
        client = default_client()

    reason = 'AI is not configured, so the matching passages are shown as they are.'
    if client is not None:
        try:
            raw = client.generate_json(build_playbook_prompt(question, passages))
            answer = str(raw.get('answer', '')).strip()
            used = raw.get('used', [])
            if not answer:
                raise ValueError('empty answer')
            valid_ids = {p['id'] for p in passages}
            if not isinstance(used, list) or not set(used) <= valid_ids:
                raise ValueError('it cited a source that was not retrieved')
            return {'source': 'ai', 'reason': '', 'answer': answer[:ANSWER_MAX], 'passages': passages}
        except AIError as exc:
            reason = f'{exc} The matching passages are shown instead.'
            logger.warning('playbook used the fallback: %s', reason)
        except (ValueError, AttributeError) as exc:
            reason = f'The AI answer was rejected ({exc}). The matching passages are shown instead.'
            logger.warning('playbook used the fallback: %s', reason)
    return {'source': 'fallback', 'reason': reason, 'answer': '', 'passages': passages}
