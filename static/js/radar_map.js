/* Deal Radar map (Leaflet + OpenStreetMap tiles). The shops come from the page, in
   <script id="radar-points" type="application/json">, so this file makes no request of its own
   except the map tiles. Colours are read from static/css/tokens.css. The tier word is also on
   every card and in every popup, so colour is never the only signal. */
(function () {
  'use strict';
  var el = document.getElementById('radar-map');
  var data = document.getElementById('radar-points');
  if (!el || !data) { return; }
  if (!window.L) { el.hidden = true; return; }      // Leaflet did not load: hide the map, the list still works

  var points = JSON.parse(data.textContent);
  var css = getComputedStyle(document.documentElement);
  function token(name) { return css.getPropertyValue(name).trim(); }
  var tierColour = { Great: token('--teal'), Good: token('--sun'), Possible: token('--coral') };
  var ink = token('--ink');

  var map = L.map(el, { attributionControl: false });
  L.control.attribution({ prefix: false }).addTo(map);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  function marker(point, label, style) {
    var text = document.createElement('span');
    text.textContent = label;                        // textContent, so a shop name can never run as HTML
    L.circleMarker([point.lat, point.lon], style).addTo(map).bindPopup(text, { closeButton: false });
    return [point.lat, point.lon];
  }

  var spots = points.shops.map(function (shop) {
    return marker(shop, shop.name + ' · ' + shop.score + ' · ' + shop.tier, {
      radius: 10, color: ink, weight: 1,
      fillColor: tierColour[shop.tier], fillOpacity: shop.registered ? 0.95 : 0.45
    });
  });
  spots.push(marker(points.me, points.me.name + ' (your shop)', {
    radius: 10, color: token('--bg'), weight: 2, fillColor: ink, fillOpacity: 1
  }));
  map.fitBounds(L.latLngBounds(spots).pad(0.15), { maxZoom: 17 });
}());
