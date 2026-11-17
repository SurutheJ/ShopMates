"""
Nearby shops that are not on ShopMates yet, from OpenStreetMap (OSM).

Overpass is OSM's free search service: one POST with a small query returns the
named shops around a point. It needs no key, so the rule is to be polite: one
request per area, kept in OsmQueryCache for 7 days, and a User-Agent that says
who is asking. If the request fails, an older saved answer is better than none.
"""

import re
from datetime import timedelta

import requests
from django.utils import timezone

from accounts.geo import haversine_miles
from accounts.models import OsmQueryCache

URL = 'https://overpass-api.de/api/interpreter'
HEADERS = {'User-Agent': 'ShopMates-CoursePilot/1.0 (INFO 490 class project)'}
TIMEOUT_SECONDS = 8
CACHE_DAYS = 7
SAME_SHOP_METRES = 50
METRES_PER_MILE = 1609.344

QUERY = '''[out:json][timeout:25];
(
  node(around:{radius},{lat},{lon})["shop"]["name"];
  node(around:{radius},{lat},{lon})["amenity"~"^(cafe|restaurant|fast_food|bar|ice_cream)$"]["name"];
  way(around:{radius},{lat},{lon})["shop"]["name"];
);
out center tags 60;'''

_AMENITY = {'cafe': 'cafe', 'restaurant': 'restaurant', 'fast_food': 'restaurant',
            'bar': 'restaurant', 'ice_cream': 'restaurant'}
_SHOP = {'bakery': 'bakery', 'books': 'bookstore', 'florist': 'flowers',
         'hairdresser': 'salon', 'beauty': 'salon'}


def category_for(tags):
    """Our Shop.Category value for a set of OSM tags."""
    if tags.get('amenity') in _AMENITY:
        return _AMENITY[tags['amenity']]
    if tags.get('leisure') in ('fitness_centre', 'sports_centre'):
        return 'fitness'
    if 'shop' in tags:
        return _SHOP.get(tags['shop'], 'retail')
    return 'other'


def _places(data):
    """Overpass JSON to our dicts. A way (a building outline) carries its position under 'center'."""
    if 'remark' in data:          # Overpass reports its own errors and timeouts this way, with status 200
        raise ValueError(data['remark'])
    places = []
    for element in data['elements']:
        tags = element.get('tags', {})
        position = element.get('center', element)
        if tags.get('name') and 'lat' in position and 'lon' in position:
            places.append({'name': tags['name'], 'lat': position['lat'], 'lon': position['lon'],
                           'category': category_for(tags), 'osm_type': element['type'], 'osm_id': element['id']})
    return places


def nearby(lat, lon, radius_m):
    """
    (places, unavailable). places is a list of
    {'name', 'lat', 'lon', 'category', 'osm_type', 'osm_id'}. unavailable is True
    only when the request failed and nothing was saved earlier, so the page can say so.
    """
    key = f'overpass:{lat:.3f},{lon:.3f}:{radius_m}'
    saved = OsmQueryCache.objects.filter(key=key).first()
    if saved and timezone.now() - saved.fetched_at < timedelta(days=CACHE_DAYS):
        return saved.payload, False
    try:
        response = requests.post(URL, data={'data': QUERY.format(radius=radius_m, lat=lat, lon=lon)},
                                 headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        places = _places(response.json())
    except (requests.RequestException, ValueError, KeyError):
        return (saved.payload, False) if saved else ([], True)
    OsmQueryCache.objects.update_or_create(key=key, defaults={'payload': places, 'fetched_at': timezone.now()})
    return places, False


def _plain(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def drop_registered(places, shops):
    """Leave out OSM places that are already a ShopMates shop: same name (ignoring case and punctuation) within 50 m."""
    shops = list(shops)

    def is_registered(place):
        return any(
            _plain(shop.name) == _plain(place['name'])
            and METRES_PER_MILE * haversine_miles(shop.latitude, shop.longitude, place['lat'], place['lon'])
            <= SAME_SHOP_METRES
            for shop in shops)
    return [place for place in places if not is_registered(place)]
