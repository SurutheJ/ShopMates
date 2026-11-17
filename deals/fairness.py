"""
Fairness calculator: an estimate of what each shop earns from a deal. Plain Decimal math, no AI.

Each shop honors its own offer for the customers its partner sends. It assumes every redeemer is a new
customer who spends the average ticket once, so it is an estimate for negotiation, not a forecast.
"""
from decimal import ROUND_CEILING, Decimal

CENT = Decimal('0.01')
BALANCED = Decimal('0.25')
LOPSIDED = Decimal('0.50')


def _per_redemption(shop, discount_percent):
    """(discount, profit) in dollars for one redemption at `shop`, unrounded."""
    discount = Decimal(discount_percent) / 100 * shop['ticket']
    return discount, shop['margin_pct'] / 100 * shop['ticket'] - discount


def _imbalance(pa, pb):
    return abs(pa - pb) / max(abs(pa), abs(pb), CENT)


def _suggest(high, low_profit, redemptions):
    """
    The smallest whole-percent discount for `high` (the shop earning more) that brings the two profits within
    25% while `high` still earns something on each redemption. None when no such discount exists.
    """
    def ok(pct):
        profit = redemptions * _per_redemption(high, pct)[1]
        return profit > 0 and pct <= 100 and _imbalance(profit, low_profit) <= BALANCED

    if low_profit <= 0:
        return None
    # Bisection between today's discount (too lopsided) and the break-even discount (profit reaches 0).
    lo, hi = Decimal(high['discount_percent']), high['margin_pct']
    for _ in range(30):
        mid = (lo + hi) / 2
        profit = redemptions * _per_redemption(high, mid)[1]
        if profit < low_profit or _imbalance(profit, low_profit) <= BALANCED:
            hi = mid
        else:
            lo = mid
    # Round up to a whole percent. `lo` sits just under the exact answer, so the answer is this or the next one.
    pct = int(lo.to_integral_value(rounding=ROUND_CEILING))
    for candidate in (pct, pct + 1):
        if ok(candidate):
            return candidate
    return None


def fairness(a, b, months, expected_sent_per_month=20):
    """
    a and b are dicts: name, ticket, margin_pct, discount_percent, cap (percent offers only).
    Returns the per-shop numbers, the imbalance and its label, blockers, a balancing suggestion and a sentence.
    """
    shops, profits, blockers = {}, {}, []
    for key, shop in (('a', a), ('b', b)):
        discount, per = _per_redemption(shop, shop['discount_percent'])
        redemptions = min(shop['cap'], expected_sent_per_month * months)
        profits[key] = redemptions * per
        shops[key] = {
            'name': shop['name'],
            'redemptions': redemptions,
            'discount': discount.quantize(CENT),
            'profit_per_redemption': per.quantize(CENT),
            'profit': profits[key].quantize(CENT),
        }
        if per < 0:
            blockers.append(f"{shop['name']} loses money on every redemption")

    pa, pb = profits['a'], profits['b']
    imbalance = _imbalance(pa, pb)
    label = 'balanced' if imbalance < BALANCED else 'lopsided' if imbalance <= LOPSIDED else 'very lopsided'
    high, high_key, low_key = (a, 'a', 'b') if pa > pb else (b, 'b', 'a')

    period = f"{months} month{'' if months == 1 else 's'}"
    explanation = (f"At these terms, {a['name']} is estimated to earn ${shops['a']['profit']} and {b['name']} "
                   f"${shops['b']['profit']} over {period} ({imbalance * 100:.0f}% apart).")
    suggestion, note = None, ''
    if label != 'balanced':
        redemptions = shops[high_key]['redemptions']
        pct = _suggest(high, profits[low_key], redemptions)
        if pct is None:
            note = 'No discount change balances this deal. Try unequal caps instead.'
        else:
            per = _per_redemption(high, pct)[1]
            new_imbalance = _imbalance(redemptions * per, profits[low_key])
            suggestion = {
                'shop': high['name'],
                'discount_percent': pct,
                'profit_per_redemption': per.quantize(CENT),
                'profit': (redemptions * per).quantize(CENT),
                'imbalance': new_imbalance.quantize(Decimal('0.001')),
            }
            explanation += (f" Raising {high['name']}'s discount to {pct}% "
                            f"brings them within {new_imbalance * 100:.0f}%.")
    return {
        'a': shops['a'],
        'b': shops['b'],
        'months': months,
        'imbalance': imbalance.quantize(Decimal('0.001')),
        'label': label,
        'better_off': None if pa == pb else high['name'],
        'blockers': blockers,
        'suggestion': suggestion,
        'note': note,
        'explanation': explanation,
    }
