"""Continent, region, and subregion alias maps and hierarchy expansion."""

from __future__ import annotations

from typing import Iterable

CONTINENT_ALIASES = {
    "europa": "Europe",
    "europie": "Europe",
    "europe": "Europe",
    "azja": "Asia",
    "azji": "Asia",
    "asia": "Asia",
    "afryka": "Africa",
    "afryce": "Africa",
    "africa": "Africa",
    "ameryka polnocna": "North America",
    "ameryce polnocnej": "North America",
    "north america": "North America",
    "ameryka poludniowa": "South America",
    "ameryce poludniowej": "South America",
    "south america": "South America",
    "ameryki": "Americas",
    "amerykach": "Americas",
    "ameryk": "Americas",
    "ameryce": "Americas",
    "ameryka": "Americas",
    "americas": "Americas",
    "oceania": "Oceania",
    "antarktyda": "Antarctica",
    "antarctica": "Antarctica",
}


REGION_ALIASES = {
    "europe": "Europe",
    "asia": "Asia",
    "africa": "Africa",
    "americas": "Americas",
    "ameryki": "Americas",
    "amerykach": "Americas",
    "ameryk": "Americas",
    "ameryce": "Americas",
    "ameryka": "Americas",
    "north america": "Americas",
    "south america": "Americas",
    "oceania": "Oceania",
}


SUBREGION_ALIASES = {
    "central europe": "Central Europe",
    "eastern europe": "Eastern Europe",
    "western europe": "Western Europe",
    "northern europe": "Northern Europe",
    "southern europe": "Southern Europe",
    "southeast europe": "Southeast Europe",
    "east europe": "Eastern Europe",
    "north europe": "Northern Europe",
    "south europe": "Southern Europe",
    "east asia": "Eastern Asia",
    "west asia": "Western Asia",
    "south asia": "Southern Asia",
    "east africa": "Eastern Africa",
    "north africa": "Northern Africa",
    "west africa": "Western Africa",
    "eastern asia": "Eastern Asia",
    "western asia": "Western Asia",
    "southern asia": "Southern Asia",
    "southeast asia": "South-Eastern Asia",
    "south eastern asia": "South-Eastern Asia",
    "south-eastern asia": "South-Eastern Asia",
    "central asia": "Central Asia",
    "central africa": "Middle Africa",
    "caribean": "Caribbean",
    "caribbean": "Caribbean",
    "central america": "Central America",
    "north america": "North America",
    "south america": "South America",
    "middle east": "Middle East",
    "scandinavia": "Scandinavia",
    "baltic states": "Baltic states",
    "baltics": "Baltic states",
    "balkans": "Balkans",
    "iberia": "Iberia",
    "iberian peninsula": "Iberian Peninsula",
    "mediterranean": "Mediterranean",
    "eastern africa": "Eastern Africa",
    "middle africa": "Middle Africa",
    "northern africa": "Northern Africa",
    "southern africa": "Southern Africa",
    "western africa": "Western Africa",
    "melanesia": "Melanesia",
    "micronesia": "Micronesia",
    "polynesia": "Polynesia",
    "australia and new zealand": "Australia and New Zealand",
    # Polish regional aliases
    "bliski wschod": "Middle East",
    "bliskim wschodzie": "Middle East",
    "bliskiego wschodu": "Middle East",
    "bliskiemu wschodowi": "Middle East",
    "balkany": "Balkans",
    "balkanach": "Balkans",
    "balkanow": "Balkans",
    "balkanami": "Balkans",
    "polwysep balkanski": "Balkans",
    "polwyspie balkanskim": "Balkans",
    "skandynawia": "Scandinavia",
    "skandynawii": "Scandinavia",
    "kraj nordycki": "Nordic countries",
    "kraje nordyckie": "Nordic countries",
    "krajow nordyckich": "Nordic countries",
    "nordycki": "Nordic countries",
    "nordyckie": "Nordic countries",
    "kraj baltycki": "Baltic states",
    "kraje baltyckie": "Baltic states",
    "panstwa baltyckie": "Baltic states",
    "krajach baltyckich": "Baltic states",
    "baltycki": "Baltic states",
    "karaiby": "Caribbean",
    "karaibach": "Caribbean",
    "karaibow": "Caribbean",
    "karaibami": "Caribbean",
    "polwysep iberyjski": "Iberian Peninsula",
    "polwyspie iberyjskim": "Iberian Peninsula",
    "polwyspu iberyjskiego": "Iberian Peninsula",
    "iberii": "Iberian Peninsula",
    "benelux": "Benelux",
    "beneluks": "Benelux",
    "beneluksu": "Benelux",
    "rog afryki": "Horn of Africa",
    "rogu afryki": "Horn of Africa",
    "wyspy brytyjskie": "British Isles",
    "wyspach brytyjskich": "British Isles",
    "ameryka srodkowa": "Central America",
    "ameryce srodkowej": "Central America",
    "ameryki srodkowej": "Central America",
    "ameryka polnocna": "North America",
    "ameryce polnocnej": "North America",
    "ameryki polnocnej": "North America",
    "ameryka poludniowa": "South America",
    "ameryce poludniowej": "South America",
    "ameryki poludniowej": "South America",
    "europa srodkowa": "Central Europe",
    "europie srodkowej": "Central Europe",
    "europy srodkowej": "Central Europe",
    "europa wschodnia": "Eastern Europe",
    "europie wschodniej": "Eastern Europe",
    "europy wschodniej": "Eastern Europe",
    "europa zachodnia": "Western Europe",
    "europie zachodniej": "Western Europe",
    "europy zachodniej": "Western Europe",
    "europa poludniowa": "Southern Europe",
    "europie poludniowej": "Southern Europe",
    "europy poludniowej": "Southern Europe",
    "europa polnocna": "Northern Europe",
    "europie polnocnej": "Northern Europe",
    "europy polnocnej": "Northern Europe",
    "azja poludniowo wschodnia": "South-Eastern Asia",
    "azji poludniowo wschodniej": "South-Eastern Asia",
    "azja poludniowowschodnia": "South-Eastern Asia",
    "azji poludniowowschodniej": "South-Eastern Asia",
    "azja wschodnia": "Eastern Asia",
    "azji wschodniej": "Eastern Asia",
    "azja poludniowa": "Southern Asia",
    "azji poludniowej": "Southern Asia",
    "azja centralna": "Central Asia",
    "azji centralnej": "Central Asia",
    "azja srodkowa": "Central Asia",
    "azji srodkowej": "Central Asia",
}


GEOGRAPHIC_SUBREGION_PARENT_MAP: dict[str, set[str]] = {
    # Middle East
    "Arabian Peninsula": {"Middle East", "Western Asia", "Asia"},
    "Levant": {"Middle East", "Western Asia", "Asia"},
    "Persian Gulf": {"Middle East"},

    # Europe
    "Scandinavia": {"Nordic countries", "Northern Europe", "Europe"},
    "Nordic countries": {"Northern Europe", "Europe"},
    "Baltic states": {"Northern Europe", "Europe"},
    "Benelux": {"Western Europe", "Europe"},
    "British Isles": {"Northern Europe", "Europe"},
    "Iberia": {"Iberian Peninsula", "Southern Europe", "Europe"},
    "Iberian Peninsula": {"Southern Europe", "Europe"},
    "Balkans": {"Southeast Europe", "Southern Europe", "Europe"},
    "Central Europe": {"Europe"},
    "Eastern Europe": {"Europe"},
    "Western Europe": {"Europe"},
    "Northern Europe": {"Europe"},
    "Southern Europe": {"Europe"},
    "Southeast Europe": {"Balkans", "Southern Europe", "Europe"},

    # Americas
    "Central America": {"North America", "Americas"},
    "Caribbean": {"North America", "Americas"},
    "North America": {"Americas"},
    "South America": {"Americas"},

    # Asia
    "South-Eastern Asia": {"Southeast Asia", "Asia"},
    "Southeast Asia": {"Asia"},
    "Eastern Asia": {"East Asia", "Asia"},
    "East Asia": {"Asia"},
    "Southern Asia": {"South Asia", "Asia"},
    "South Asia": {"Asia"},
    "Central Asia": {"Asia"},
    "Western Asia": {"Asia"},
    "Indian subcontinent": {"South Asia", "Asia"},

    # Africa
    "Maghreb": {"Northern Africa", "North Africa", "Africa"},
    "Horn of Africa": {"Eastern Africa", "East Africa", "Africa"},
    "Sahel": {"Africa"},
    "Northern Africa": {"North Africa", "Africa"},
    "Eastern Africa": {"East Africa", "Africa"},
    "Western Africa": {"West Africa", "Africa"},
    "Middle Africa": {"Central Africa", "Africa"},
    "Southern Africa": {"Africa"},
}


def expand_geographic_areas(areas: Iterable[str]) -> set[str]:
    """Compute transitive parent regions and continents for a collection of areas."""
    expanded = set(areas)
    queue = list(areas)
    while queue:
        item = queue.pop(0)
        if item in GEOGRAPHIC_SUBREGION_PARENT_MAP:
            for parent in GEOGRAPHIC_SUBREGION_PARENT_MAP[item]:
                if parent not in expanded:
                    expanded.add(parent)
                    queue.append(parent)
    return expanded


GEOGRAPHIC_AREA_ALIASES = {
    **SUBREGION_ALIASES,
    **REGION_ALIASES,
}
