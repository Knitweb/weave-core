"""Browser exploration links for a recognized object.

Given a label and a WGS84 position, build deterministic deep links into
public knowledge and mapping services. No network calls happen here —
links are constructed client-side and opened by the explorer page, so
the pipeline stays fast and offline-friendly.
"""

from __future__ import annotations

from urllib.parse import quote


def build_links(lat: float, lon: float, label: str, radius_m: int = 250) -> dict:
    q = quote(label)
    overpass = quote(
        f'node(around:{radius_m},{lat},{lon})["name"];out body 20;'
    )
    wikidata_sparql = quote(
        "SELECT ?place ?placeLabel ?dist WHERE { "
        "SERVICE wikibase:around { ?place wdt:P625 ?loc. "
        f'bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral. '
        f'bd:serviceParam wikibase:radius "{radius_m / 1000}". '
        "bd:serviceParam wikibase:distance ?dist. } "
        'SERVICE wikibase:label { bd:serviceParam wikibase:language "nl,en". } } '
        "ORDER BY ?dist LIMIT 20"
    )
    return {
        "openstreetmap": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}",
        "google_maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
        "geohack": f"https://geohack.toolforge.org/geohack.php?params={lat}_N_{lon}_E",
        "wikipedia_nearby": f"https://nl.wikipedia.org/wiki/Speciaal:Dichtstbijzijnde?lat={lat}&lon={lon}",
        "wikidata_nearby": f"https://query.wikidata.org/#{wikidata_sparql}",
        "overpass_turbo": f"https://overpass-turbo.eu/?Q={overpass}&C={lat};{lon};18",
        "mapillary": f"https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=18",
        "wikipedia_label": f"https://nl.wikipedia.org/wiki/Speciaal:Zoeken?search={q}",
        "openverse_images": f"https://openverse.org/search?q={q}",
    }
