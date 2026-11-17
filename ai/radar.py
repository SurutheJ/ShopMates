"""
Deal Radar: rank the shops within walking distance by how good a partner each would be.

Score (0-100) = 100 x (45% fit + 30% walk + 25% hours). Everything is plain
arithmetic on the shops it is given: no model call, no network, no
randomness, so the same shops always give the same list.

Audience similarity compares the two shops' descriptions with TF-IDF, written
out in plain Python below (TF-IDF: count each word, give rarer words more
weight, then measure the angle between the two word lists). It is 0.5 when
either shop has no description.

Hours overlap is the time both shops are open in a week, divided by the open
time of the shop with fewer hours. It is 0.5 when either shop's hours text
cannot be read (see ai/hours.py).
"""

import math
import re
from collections import Counter

from accounts.geo import haversine_miles
from accounts.models import Shop

from .hours import open_minutes, overlap_minutes, parse_hours

WEIGHTS = {'fit': 0.45, 'walk': 0.30, 'hours': 0.25}

METRES_PER_MILE = 1609.344
STREET_FACTOR = 1.3          # straight-line distance to street distance
METRES_PER_MINUTE = 80       # walking speed
MAX_WALK_MINUTES = 12        # at or beyond this, walk contributes nothing
AUDIENCE_UNKNOWN = 0.5       # used when either shop has no description
STOP_WORDS = frozenset('the and for with our are you your who that this from have has not but all mostly very also'.split())
HOURS_UNKNOWN = 0.5          # used when either shop's hours cannot be read

# Our category values mapped to the names used in the prior table; anything else is 'other'.
_NAMES = {'cafe': 'cafe', 'bookstore': 'books', 'bakery': 'bakery',
          'fitness': 'gym', 'retail': 'clothing', 'salon': 'salon'}

# How well two categories complement each other, 0 to 1. A hand-set, editable
# assumption (not learned from data). Symmetric: row and column order match.
_ORDER = ('cafe', 'books', 'bakery', 'gym', 'clothing', 'salon', 'other')
_PRIOR = {
    'cafe':     (0.10, 0.90, 0.35, 0.70, 0.60, 0.60, 0.50),
    'books':    (0.90, 0.10, 0.70, 0.40, 0.60, 0.50, 0.50),
    'bakery':   (0.35, 0.70, 0.10, 0.50, 0.50, 0.60, 0.50),
    'gym':      (0.70, 0.40, 0.50, 0.10, 0.70, 0.60, 0.50),
    'clothing': (0.60, 0.60, 0.50, 0.70, 0.15, 0.80, 0.50),
    'salon':    (0.60, 0.50, 0.60, 0.60, 0.80, 0.10, 0.50),
    'other':    (0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.30),
}


def tier(score):
    return 'Great' if score >= 80 else 'Good' if score >= 60 else 'Possible'


def _fit_words(prior):
    if prior >= 0.6:
        return 'are complementary'
    if prior < 0.4:
        return 'compete for the same customers'
    return 'are a neutral fit'


def _words(shop):
    """Word counts for "{category} {description}": lower case, 3+ letters, stop words dropped."""
    text = f'{shop.category} {shop.description}'.lower()
    return Counter(w for w in re.findall(r'[a-z]{3,}', text) if w not in STOP_WORDS)


def _idf(shops):
    """Weight per word: ln((1 + shops) / (1 + shops using the word)) + 1, so rarer words count more."""
    docs = [_words(s) for s in shops if s.description.strip()]
    used_by = Counter(word for doc in docs for word in doc)
    return {word: math.log((1 + len(docs)) / (1 + n)) + 1 for word, n in used_by.items()}


def _audience(a, b, idf):
    """
    (similarity 0..1, best shared word or '') for two shops that both have a description,
    else (None, ''). Similarity is the cosine of the two TF-IDF word vectors.
    """
    if not a.description.strip() or not b.description.strip():
        return None, ''
    wa = {w: n * idf[w] for w, n in _words(a).items()}
    wb = {w: n * idf[w] for w, n in _words(b).items()}
    shared = {w: wa[w] * wb[w] for w in wa if w in wb}
    length = math.sqrt(sum(v * v for v in wa.values())) * math.sqrt(sum(v * v for v in wb.values()))
    similarity = min(1.0, max(0.0, sum(shared.values()) / length))
    word = min(shared, key=lambda w: (-shared[w], w)) if shared else ''
    return similarity, word


def radar(shop, candidates, radius_m, places=()):
    """
    Returns [{'shop', 'score', 'walk_minutes', 'tier', 'reason', 'hours_note', 'audience_note',
    'registered', 'place'}, ...] for the candidates within `radius_m` metres (straight line)
    of `shop`, best score first, ties by name. Shops without coordinates are left out.

    `places` are unregistered shops from ai/osm.py. They get the same formula with no
    description and no hours, 'registered' False, and 'shop' is an unsaved Shop built
    from the OSM name, category and position ('place' keeps the OSM dict).
    """
    if shop.latitude is None or shop.longitude is None:
        return []
    candidates = list(candidates)
    mine = _NAMES.get(shop.category, 'other')
    idf = _idf([shop, *candidates])
    my_hours = parse_hours(shop.hours)
    unregistered = [(Shop(name=p['name'], category=p['category'], latitude=p['lat'], longitude=p['lon']), p)
                    for p in places]
    results = []
    for other, place in [(c, None) for c in candidates] + unregistered:
        if other.latitude is None or other.longitude is None:
            continue
        metres = METRES_PER_MILE * haversine_miles(
            shop.latitude, shop.longitude, other.latitude, other.longitude)
        if metres > radius_m:
            continue
        theirs = _NAMES.get(other.category, 'other')
        prior = _PRIOR[mine][_ORDER.index(theirs)]
        walk_minutes = metres * STREET_FACTOR / METRES_PER_MINUTE
        similarity, word = _audience(shop, other, idf)
        fit = prior * (0.5 + 0.5 * (AUDIENCE_UNKNOWN if similarity is None else similarity))
        walk = max(0.0, 1 - walk_minutes / MAX_WALK_MINUTES)
        their_hours = parse_hours(other.hours)
        reason = [f'{round(walk_minutes)} min walk']
        if my_hours and their_hours:
            together = overlap_minutes(my_hours, their_hours)
            hours = min(1.0, together / min(open_minutes(my_hours), open_minutes(their_hours)))
            hours_note = f'open together {round(together / 60)} h/week'
            reason.append(hours_note)
        else:
            hours, hours_note = HOURS_UNKNOWN, 'hours unknown'
        score = round(100 * (WEIGHTS['fit'] * fit + WEIGHTS['walk'] * walk + WEIGHTS['hours'] * hours))
        reason.append(f'{mine} + {theirs} {_fit_words(prior)}')
        if similarity is not None and similarity > 0.5 and word:
            reason.append(f'both mention {word}')
        results.append({
            'shop': other,
            'score': score,
            'walk_minutes': round(walk_minutes),
            'tier': tier(score),
            'reason': ', '.join(reason),
            'hours_note': hours_note,
            'audience_note': 'not enough info' if similarity is None else '',
            'registered': place is None,
            'place': place,
        })
    results.sort(key=lambda r: (-r['score'], r['shop'].name.lower()))
    return results
