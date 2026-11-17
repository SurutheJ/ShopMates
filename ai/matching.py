"""
Partner match score: which neighboring shops are worth proposing a deal to?

This is an explainable, rule-based recommender. Every number is computed in
Python from fields already in the database, and every score comes with the
reasons behind it, so an owner can see *why* a shop is ranked first. No model
call is involved, so it is instant, free and deterministic.

Score (0-100) = 45% category fit + 35% walking distance + 20% spend balance.

The category-fit table is a hand-written prior (an assumption, not learned
from data). With real redemption data it could be replaced by observed rates.
"""

# How well two categories send customers to each other, 0 to 1, with a reason.
# Keys are unordered pairs. Same-category pairs are handled separately.
_FIT = {
    ('cafe', 'bookstore'): (1.0, 'Readers linger over coffee, and cafe guests browse books'),
    ('cafe', 'fitness'): (0.9, 'Post-workout coffee is a natural second stop'),
    ('cafe', 'retail'): (0.8, 'Shoppers take coffee breaks between stores'),
    ('cafe', 'salon'): (0.7, 'Appointment waits and coffee go together'),
    ('cafe', 'flowers'): (0.7, 'Gift shoppers often grab a coffee'),
    ('cafe', 'bakery'): (0.6, 'Overlapping menus, so keep the offers different'),
    ('cafe', 'restaurant'): (0.5, 'Similar visit, so the audience overlaps'),
    ('bakery', 'flowers'): (0.9, 'Both sell gifts for the same occasions'),
    ('bakery', 'bookstore'): (0.7, 'Treat plus a browse is an easy afternoon'),
    ('bakery', 'retail'): (0.5, 'Some cross-traffic on weekends'),
    ('bakery', 'fitness'): (0.4, 'Indulgent treats vs healthy goals'),
    ('bakery', 'salon'): (0.6, 'Occasion-driven visits overlap'),
    ('bakery', 'restaurant'): (0.4, 'Both are food, so customers may just substitute'),
    ('restaurant', 'flowers'): (0.8, 'Date nights and celebrations'),
    ('restaurant', 'salon'): (0.7, 'Get ready, then go out to eat'),
    ('restaurant', 'fitness'): (0.6, 'Post-class meals'),
    ('restaurant', 'bookstore'): (0.5, 'Quiet evening out'),
    ('restaurant', 'retail'): (0.6, 'Shop, then eat'),
    ('fitness', 'salon'): (0.8, 'Self-care customers overlap strongly'),
    ('fitness', 'retail'): (0.6, 'Activewear and gear shoppers'),
    ('fitness', 'flowers'): (0.4, 'Little natural overlap'),
    ('fitness', 'bookstore'): (0.5, 'Wellness reading'),
    ('salon', 'retail'): (0.8, 'Appearance-minded shoppers'),
    ('salon', 'flowers'): (0.7, 'Gifts and pampering share occasions'),
    ('salon', 'bookstore'): (0.4, 'Little natural overlap'),
    ('retail', 'bookstore'): (0.7, 'Browsers visit both'),
    ('retail', 'flowers'): (0.6, 'Gift shopping trip'),
}
_FIT = {frozenset(pair): value for pair, value in _FIT.items()}
# Two or three words per pair for the small tile on Discover. The full sentence above shows when the tile is opened.
_KEYWORDS = {
    ('cafe', 'bookstore'): 'Readers + coffee', ('cafe', 'fitness'): 'Post-workout stop',
    ('cafe', 'retail'): 'Shopping breaks', ('cafe', 'salon'): 'Waits + coffee',
    ('cafe', 'flowers'): 'Gift shoppers', ('cafe', 'bakery'): 'Overlapping menus',
    ('cafe', 'restaurant'): 'Similar visit', ('bakery', 'flowers'): 'Shared gifts',
    ('bakery', 'bookstore'): 'Treat + browse', ('bakery', 'retail'): 'Weekend traffic',
    ('bakery', 'fitness'): 'Treats vs goals', ('bakery', 'salon'): 'Occasion visits',
    ('bakery', 'restaurant'): 'Both food', ('restaurant', 'flowers'): 'Date nights',
    ('restaurant', 'salon'): 'Get ready, dine', ('restaurant', 'fitness'): 'Post-class meals',
    ('restaurant', 'bookstore'): 'Quiet evening', ('restaurant', 'retail'): 'Shop, then eat',
    ('fitness', 'salon'): 'Self-care crowd', ('fitness', 'retail'): 'Gear shoppers',
    ('fitness', 'flowers'): 'Little overlap', ('fitness', 'bookstore'): 'Wellness reading',
    ('salon', 'retail'): 'Style shoppers', ('salon', 'flowers'): 'Gifts + pampering',
    ('salon', 'bookstore'): 'Little overlap', ('retail', 'bookstore'): 'Browsers',
    ('retail', 'flowers'): 'Gift trips',
}
_KEYWORDS = {frozenset(pair): text for pair, text in _KEYWORDS.items()}
_DEFAULT_FIT = (0.5, 'Neutral fit: no strong reason either way')
_SAME_CATEGORY = (0.2, 'Same category, so you may compete for the same customers')

WALKABLE_MILES = 1.5     # beyond this, distance contributes nothing
WEIGHTS = {'fit': 0.45, 'distance': 0.35, 'spend': 0.20}


def category_fit(a_category, b_category):
    if a_category == b_category:
        return _SAME_CATEGORY
    return _FIT.get(frozenset((a_category, b_category)), _DEFAULT_FIT)


def fit_keyword(a_category, b_category):
    if a_category == b_category:
        return 'Same category'
    return _KEYWORDS.get(frozenset((a_category, b_category)), 'Neutral fit')


def match_score(shop, other, distance_miles=None):
    """
    Returns {'score': int 0-100, 'label': str, 'reasons': [(is_positive, text), ...], 'keywords': [fit, spend]}.
    `distance_miles` is None when either shop has no coordinates.
    """
    reasons = []

    fit, fit_reason = category_fit(shop.category, other.category)
    reasons.append((fit >= 0.6, fit_reason))

    if distance_miles is None:
        distance_part = 0.5
        reasons.append((False, 'Distance unknown (no coordinates entered)'))
    else:
        distance_part = max(0.0, 1 - distance_miles / WALKABLE_MILES)
        if distance_miles <= 0.3:
            reasons.append((True, f'{distance_miles:.1f} mi away: a short walk'))
        elif distance_miles <= WALKABLE_MILES:
            reasons.append((True, f'{distance_miles:.1f} mi away: walkable'))
        else:
            reasons.append((False, f'{distance_miles:.1f} mi away: too far for walk-in traffic'))

    mine, theirs = float(shop.typical_order_value), float(other.typical_order_value)
    ratio = min(mine, theirs) / max(mine, theirs)
    spend_part = ratio
    if ratio >= 0.6:
        reasons.append((True, f'Similar typical spend (${mine:.0f} vs ${theirs:.0f}), so a shared '
                              f'discount costs both of you about the same'))
    else:
        reasons.append((False, f'Spend differs a lot (${mine:.0f} vs ${theirs:.0f}), so the same '
                               f'percentage discount is not equally costly. Consider a cap.'))

    raw = (WEIGHTS['fit'] * fit + WEIGHTS['distance'] * distance_part + WEIGHTS['spend'] * spend_part)
    score = round(100 * raw)
    label = 'Great match' if score >= 75 else 'Good match' if score >= 55 else 'Possible match'
    keywords = [fit_keyword(shop.category, other.category), 'Similar spend' if ratio >= 0.6 else 'Spend gap']
    return {'score': score, 'label': label, 'reasons': reasons, 'keywords': keywords}
