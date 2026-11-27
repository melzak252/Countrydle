"""Direct rule-based local answering against Countrydle's SQLite fact database."""

from __future__ import annotations

from pathlib import Path
import re
import sqlite3

from country_fact_provenance import read_record
from countrydle.answering.aliases import (
    CONTINENT_ALIASES,
    COUNTRY_NAME_SYNONYMS,
    GEOGRAPHIC_AREA_ALIASES,
    GOVERNMENT_TYPE_ALIASES,
    ORG_ALIASES,
    POLISH_COUNTRY_ALIASES,
    REGION_ALIASES,
    RELIGION_ALIASES,
    SUBREGION_ALIASES,
    VALUE_ALIASES,
    WATER_BODY_PARENT_MAP,
    canonical_country_name,
    expand_geographic_areas,
    expand_water_bodies,
    first_mentioned_value,
    get_distinct_oceans,
    is_multi_ocean_question,
    normalize,
    yes_no_question,
)
from countrydle.answering.db import LocalAnswer, get_default_db_path, rows


class LocalCountryFacts:
    def __init__(self, db_path: Path | None = None):
        self.db_path = get_default_db_path() if db_path is None else db_path

    def try_answer(self, original_question: str, country_name: str) -> LocalAnswer | None:
        if not self.db_path.exists():
            return None

        q = normalize(original_question)
        if not yes_no_question(q):
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            country = conn.execute(
                "SELECT * FROM countries WHERE app_country_name = ?", (country_name,)
            ).fetchone()
            if country is None:
                return None

            handlers = (
                self._answer_border,
                self._answer_geographic_area,
                self._answer_subregion,
                self._answer_continent,
                self._answer_region,
                self._answer_water_access,
                self._answer_island,
                self._answer_capital,
                self._answer_currency,
                self._answer_language,
                self._answer_dominant_religion,
                self._answer_government_type,
                self._answer_membership,
                self._answer_population_or_area,
                self._answer_coordinates,
                self._answer_river,
                self._answer_driving_side,
                self._answer_name_pattern,
            )
            for handler in handlers:
                answer = handler(conn, country, original_question, q)
                if answer is not None:
                    return answer
        return None

    def _target_country(self, conn: sqlite3.Connection, q: str) -> str | None:
        names = [r[0] for r in conn.execute("SELECT app_country_name FROM countries")]
        combined_aliases = {**POLISH_COUNTRY_ALIASES, **COUNTRY_NAME_SYNONYMS}
        return first_mentioned_value(q, names, combined_aliases)

    def _answer_border(self, conn, country, original, q):
        if not any(word in q for word in ("border", "borders", "neighbor", "neighbour", "granic", "sasiad")):
            return None
        target = self._target_country(conn, q)
        if not target:
            return None
        if target == country["app_country_name"] or canonical_country_name(target) == canonical_country_name(country["app_country_name"]):
            answer = False
        else:
            borders = {
                canonical_country_name(r[0])
                for r in conn.execute(
                    """
                    SELECT border_country_name FROM country_borders WHERE country_id=?
                    UNION
                    SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id=?
                    """,
                    (country["id"], country["id"]),
                )
            }
            answer = canonical_country_name(target) in borders
        return LocalAnswer(
            question=f"Does the country border {target}?",
            answer=answer,
            clarification=f"The country borders {target}." if answer else f"The country does not border {target}.",
            explanation=f"{country['app_country_name']} {'borders' if answer else 'does not border'} {target}.",
            relation="borders_country",
        )

    def _answer_continent(self, conn, country, original, q):
        if not any(
            word in q
            for word in (
                "continent",
                "kontynent",
                "europ",
                "europe",
                "azj",
                "asia",
                "afryk",
                "africa",
                "america",
                "americ",
                "oceani",
                "oceania",
            )
        ):
            return None
        target = first_mentioned_value(q, CONTINENT_ALIASES.values(), CONTINENT_ALIASES)
        if not target:
            return None
        continents = {r[0] for r in conn.execute("SELECT continent FROM country_continents WHERE country_id=?", (country["id"],))}
        if target == "Americas":
            answer = bool(continents & {"North America", "South America"})
            explanation = f"{country['app_country_name']} is listed under these continents: {', '.join(sorted(continents))}."
            return LocalAnswer(
                question="Is the country in the Americas?",
                answer=answer,
                clarification="The country is in the Americas." if answer else "The country is not in the Americas.",
                explanation=explanation,
                relation="continent",
            )
        answer = target in continents
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            clarification=f"The country is located in {target}." if answer else f"The country is not located in {target}.",
            explanation=f"{country['app_country_name']} is listed under these continents: {', '.join(sorted(continents))}.",
            relation="continent",
        )

    def _answer_geographic_area(self, conn, country, original, q):
        region_values = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        subregion_values = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, [*region_values, *subregion_values], GEOGRAPHIC_AREA_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        country_areas = country_regions | country_subregions
        all_areas = expand_geographic_areas(country_areas)
        answer = any(normalize(area) == normalize(target) for area in all_areas)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            clarification=f"The country is located in {target}." if answer else f"The country is not located in {target}.",
            explanation=f"Geographic areas for {country['app_country_name']}: {', '.join(sorted(country_areas))}.",
            relation="geographic_area",
        )

    def _answer_region(self, conn, country, original, q):
        if "subregion" in q:
            return None
        regions = [r[0] for r in conn.execute("SELECT DISTINCT region_name FROM country_regions")]
        target = first_mentioned_value(q, regions, REGION_ALIASES)
        if not target:
            return None
        country_regions = {
            r[0]
            for r in conn.execute("SELECT region_name FROM country_regions WHERE country_id=?", (country["id"],))
        }
        answer = any(normalize(region) == normalize(target) for region in country_regions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Regions for {country['app_country_name']}: {', '.join(sorted(country_regions))}.",
            relation="region",
        )

    def _answer_subregion(self, conn, country, original, q):
        subregions = [r[0] for r in conn.execute("SELECT DISTINCT subregion_name FROM country_subregions")]
        target = first_mentioned_value(q, subregions, SUBREGION_ALIASES)
        if not target:
            return None
        country_subregions = {
            r[0]
            for r in conn.execute("SELECT subregion_name FROM country_subregions WHERE country_id=?", (country["id"],))
        }
        all_subregions = expand_geographic_areas(country_subregions)
        answer = any(normalize(subregion) == normalize(target) for subregion in all_subregions)
        return LocalAnswer(
            question=f"Is the country in {target}?",
            answer=answer,
            explanation=f"Subregions for {country['app_country_name']}: {', '.join(sorted(country_subregions))}.",
            relation="subregion",
        )

    def _answer_water_access(self, conn, country, original, q):
        if not any(word in q for word in ("sea", "ocean", "morze", "ocean", "dostep", "coast", "coastline", "wybrzez", "nad ")):
            return None
        direct_waters = {r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (country["id"],))}
        if is_multi_ocean_question(q) or is_multi_ocean_question(original):
            oceans = sorted(get_distinct_oceans(direct_waters))
            count = len(oceans)
            answer = count >= 2
            if count >= 2:
                explanation = f"{country['app_country_name']} has access to {count} oceans: {', '.join(oceans)}."
            elif count == 1:
                explanation = f"{country['app_country_name']} has access to only 1 ocean: {oceans[0]}."
            elif direct_waters:
                explanation = f"{country['app_country_name']} has no direct open ocean access. Its recorded coastline: {', '.join(sorted(direct_waters))}."
            else:
                explanation = f"{country['app_country_name']} is completely landlocked with no ocean access."
            clarification = (
                f"The country has access to {count} oceans."
                if answer
                else ("The country has access to only 1 ocean." if count == 1 else "The country has no open ocean access.")
            )
            return LocalAnswer(
                question="Does the country have access to two or more oceans?",
                answer=answer,
                clarification=clarification,
                explanation=explanation,
                relation="water_access",
            )
        waters = expand_water_bodies(direct_waters)
        all_waters = [r[0] for r in conn.execute("SELECT DISTINCT water_body FROM country_water_access")]
        for w in list(all_waters):
            if w in WATER_BODY_PARENT_MAP:
                all_waters.extend(WATER_BODY_PARENT_MAP[w])
        all_waters = list(dict.fromkeys(all_waters))
        target = first_mentioned_value(q, all_waters, VALUE_ALIASES)
        if target == "Ocean":
            answer = "Ocean" in waters
            explanation = (
                f"{country['app_country_name']} has direct coastline access to: {', '.join(sorted(direct_waters))}."
                if answer
                else f"{country['app_country_name']} does not have direct coastline access to an ocean."
            )
        elif target:
            answer = target in waters
            via_sub = [w for w in sorted(direct_waters) if w in WATER_BODY_PARENT_MAP and target in WATER_BODY_PARENT_MAP[w]]
            via_str = f" (via the {', '.join(via_sub)})" if via_sub and target not in direct_waters else ""
            explanation = (
                f"{country['app_country_name']} has direct coastline access to: {target}{via_str}."
                if answer
                else f"{country['app_country_name']} does not have direct access to {target}."
            )
        elif any(word in q for word in ("sea access", "dostep do morza", "dostep do wod", "coast", "coastline", "wybrzez")):
            answer = bool(direct_waters)
            explanation = f"Main water bodies for {country['app_country_name']}: {', '.join(sorted(direct_waters)) if direct_waters else 'none'}."
        else:
            return None
        if target == "Ocean":
            clarification = "The country has direct coastline access to an ocean." if answer else "The country does not have direct coastline access to an ocean."
        elif target == "Sea":
            clarification = "The country has direct coastline access to the sea." if answer else "The country does not have direct access to the sea."
        elif target:
            clarification = f"The country has access to {target}." if answer else f"The country does not have access to {target}."
        else:
            clarification = "The country has a coastline / access to the sea." if answer else "The country is landlocked."
        return LocalAnswer(
            question=f"Does the country have direct access to {'an ocean' if target == 'Ocean' else target or 'a sea/ocean'}?",
            answer=answer,
            clarification=clarification,
            explanation=explanation,
            relation="water_access",
        )

    def _answer_island(self, conn, country, original, q):
        if not any(word in q for word in ("island", "wyspa", "wyspiars", "archipelag", "archipelago")):
            return None
        answer = bool(country["is_island"])
        return LocalAnswer(
            question="Is the country an island country?",
            answer=answer,
            clarification="The country is an island / archipelago." if answer else "The country is not an island country.",
            explanation=f"{country['app_country_name']} is {'an island' if answer else 'not an island'} country.",
            relation="is_island",
        )

    def _answer_capital(self, conn, country, original, q):
        if not any(word in q for word in ("capital", "stolic")):
            return None
        capitals = [r[0] for r in conn.execute("SELECT DISTINCT capital FROM countries WHERE capital IS NOT NULL")]
        capital_aliases = {"warszawa": "Warsaw", "praga": "Prague", "wieden": "Vienna", "rzym": "Rome", "londyn": "London", "paryz": "Paris"}
        target = first_mentioned_value(q, capitals, capital_aliases)
        if not target:
            return None
        answer = normalize(country["capital"] or "") == normalize(target)
        return LocalAnswer(
            question=f"Is the capital {target}?",
            answer=answer,
            clarification=f"The capital is {target}." if answer else f"The capital is not {target}.",
            explanation=f"The capital of {country['app_country_name']} is {country['capital']}.",
            relation="capital",
        )

    def _answer_currency(self, conn, country, original, q):
        if not any(word in q for word in ("currency", "walut", "euro", "dollar", "dolar", "zlot")):
            return None
        currencies = rows(conn, "SELECT currency_name, currency_code FROM country_currencies WHERE country_id=?", (country["id"],))
        all_values = [r[0] for r in conn.execute("SELECT DISTINCT currency_name FROM country_currencies")] + [
            r[0] for r in conn.execute("SELECT DISTINCT currency_code FROM country_currencies WHERE currency_code IS NOT NULL")
        ]
        target = first_mentioned_value(q, all_values, VALUE_ALIASES)
        if not target:
            return None
        target_norm = normalize(target)
        answer = any(normalize(r["currency_name"]) == target_norm or normalize(r["currency_code"] or "") == target_norm for r in currencies)
        names = ", ".join(r["currency_name"] for r in currencies)
        display_target = "US dollars / dollars" if target == "United States dollar" else target
        return LocalAnswer(
            question=f"Does the country use {target}?",
            answer=answer,
            clarification=f"Yes, the country uses {display_target}." if answer else f"No, the country does not use {display_target}.",
            explanation=f"The currency for {country['app_country_name']} is: {names}.",
            relation="currency",
        )

    def _answer_language(self, conn, country, original, q):
        if not any(word in q for word in ("language", "jezyk", "speak", "spoken", "mowi", "official", "co-official", "coofficial", "wspolurzedow", "urzedow")):
            return None
        langs = [r[0] for r in conn.execute("SELECT language_name FROM country_languages WHERE country_id=?", (country["id"],))]
        all_langs = [r[0] for r in conn.execute("SELECT DISTINCT language_name FROM country_languages")]
        target = first_mentioned_value(q, all_langs, VALUE_ALIASES)
        if not target:
            return None
        answer = normalize(target) in {normalize(x) for x in langs}
        is_spoken_inquiry = any(word in q for word in ("speak", "spoken", "mowi"))
        is_strictly_official_inquiry = any(word in q for word in ("official", "urzedow", "wspolurzedow", "co-official", "coofficial", "state language", "national language"))

        if answer:
            if is_spoken_inquiry and not is_strictly_official_inquiry:
                explanation = f"Yes, {target} is an official/co-official language of {country['app_country_name']} ({', '.join(langs)})."
            else:
                explanation = f"Official/co-official languages for {country['app_country_name']}: {', '.join(langs)}."
            clarification = f"Yes, {target} is an official/co-official language of the country."
            return LocalAnswer(
                question=f"Is {target} an official or spoken language?",
                answer=True,
                clarification=clarification,
                explanation=explanation,
                relation="official_language",
            )

        if is_strictly_official_inquiry:
            return LocalAnswer(
                question=f"Is {target} an official language?",
                answer=False,
                clarification=f"No, {target} is not an official language of the country.",
                explanation=f"{target} is not an official language of {country['app_country_name']}. Recorded official languages: {', '.join(langs)}.",
                relation="official_language",
            )

        return None

    def _answer_dominant_religion(self, conn, country, original, q):
        if not any(word in q for word in ("religion", "religious", "catholic", "orthodox", "protestant", "christian", "islam", "muslim", "jewish", "judaism", "buddhist", "buddhism", "hindu", "atheist")):
            return None
        target = first_mentioned_value(q, RELIGION_ALIASES.values(), RELIGION_ALIASES)
        if not target:
            return None
        religion = country["dominant_religion"]
        if not religion:
            return None
        answer = normalize(religion) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's dominant religion {target}?",
            answer=answer,
            clarification=f"Yes, the dominant religion is {target}." if answer else f"No, the dominant religion is not {target}.",
            explanation=f"The dominant religion category for {country['app_country_name']} is {religion}.",
            relation="dominant_religion",
        )

    def _answer_government_type(self, conn, country, original, q):
        if not any(word in q for word in ("government", "republic", "monarchy", "democracy", "federal", "theocracy", "communist", "dictatorship")):
            return None
        government_type = country["government_type"]
        if not government_type:
            return None
        target = first_mentioned_value(q, GOVERNMENT_TYPE_ALIASES.values(), GOVERNMENT_TYPE_ALIASES)
        if not target:
            return None
        answer = normalize(government_type) == normalize(target)
        return LocalAnswer(
            question=f"Is the country's government type {target}?",
            answer=answer,
            clarification=f"Yes, the government type is {target}." if answer else f"No, the government type is not {target}.",
            explanation=f"The government type for {country['app_country_name']} is {government_type}.",
            relation="government_type",
        )

    def _answer_membership(self, conn, country, original, q):
        orgs = [r[0] for r in conn.execute("SELECT DISTINCT organization FROM country_memberships")]
        target = first_mentioned_value(q, orgs, ORG_ALIASES)
        if not target:
            return None
        if not any(word in q for word in ("member", "nalezy", "czlon", "w ", "in ", "belongs", "part of")):
            return None
        memberships = {r[0] for r in conn.execute("SELECT organization FROM country_memberships WHERE country_id=?", (country["id"],))}
        answer = target in memberships
        return LocalAnswer(
            question=f"Is the country a member of {target}?",
            answer=answer,
            clarification=f"Yes, the country is a member of {target}." if answer else f"No, the country is not a member of {target}.",
            explanation=f"{country['app_country_name']} {'is' if answer else 'is not'} a member of {target}.",
            relation="membership",
            fact_provenance=[read_record(conn, country["id"], "membership", target if answer else None)],
        )

    def _answer_population_or_area(self, conn, country, original, q):
        relation = None
        field = None
        unit = None
        if any(word in q for word in ("population", "ludnosc", "mieszkanc", "inhabitants", "people", "citizens")):
            relation, field, unit = "population", "population", "people"
        elif any(word in q for word in ("area", "powierzch", "larger", "bigger", "wieksz")):
            relation, field, unit = "area", "area_km2", "km²"
        else:
            return None

        comparator = None
        if any(word in q for word in ("more", "greater", "larger", "bigger", "higher", "over", "wiecej", "wieksz", "ponad", "above")):
            comparator = "gt"
        elif any(word in q for word in ("less", "fewer", "smaller", "lower", "under", "mniej", "mniejsz", "ponizej", "below")):
            comparator = "lt"
        if not comparator:
            return None

        target_country = self._target_country(conn, q)
        target_value = None
        target_label = None
        if target_country and target_country != country["app_country_name"]:
            field_query = (
                "SELECT population FROM countries WHERE app_country_name=?"
                if field == "population"
                else "SELECT area_km2 FROM countries WHERE app_country_name=?"
            )
            row = conn.execute(field_query, (target_country,)).fetchone()
            if row and row[0] is not None:
                target_value = row[0]
                target_label = target_country
        else:
            number_match = re.search(r"(\d+(?:[\s,.]\d+)*)\s*(million|mln|m|tys|thousand|k)?", q)
            if number_match:
                raw = re.sub(r"[\s,]", "", number_match.group(1))
                target_value = float(raw)
                suffix = number_match.group(2) or ""
                if suffix in {"million", "mln", "m"}:
                    target_value *= 1_000_000
                elif suffix in {"tys", "thousand", "k"}:
                    target_value *= 1_000
                target_label = f"{target_value:g} {unit}"
        if target_value is None:
            return None
        value = country[field]
        answer = value > target_value if comparator == "gt" else value < target_value
        sign = "more than" if comparator == "gt" else "less than"
        clarification = f"Yes, the country has {sign} {target_label}." if answer else f"No, the country does not have {sign} {target_label}."
        return LocalAnswer(
            question=f"Does the country have {sign} {target_label}?",
            answer=answer,
            clarification=clarification,
            explanation=f"{country['app_country_name']} has {value:g} {unit}; comparison: {sign} {target_label}.",
            relation=relation,
        )

    def _answer_coordinates(self, conn, country, original, q):
        if not any(word in q for word in ("hemisphere", "polkul", "equator", "rownik", "greenwich", "latitude", "longitude")):
            return None
        lat = country["latitude"]
        lon = country["longitude"]
        hemispheres = {r[0] for r in conn.execute("SELECT hemisphere FROM country_hemispheres WHERE country_id=?", (country["id"],))}
        if any(word in q for word in ("cross the equator", "crosses the equator", "crossing the equator", "on the equator", "straddle the equator", "przecina rownik", "lezy na rowniku", "na rowniku")):
            answer = "Northern" in hemispheres and "Southern" in hemispheres
            return LocalAnswer(
                question="Does the country cross the equator?",
                answer=answer,
                clarification="The country crosses the equator." if answer else "The country does not cross the equator.",
                explanation=f"{country['app_country_name']} territory spans: {', '.join(sorted(hemispheres))} hemispheres.",
                relation="hemisphere",
            )
        if any(word in q for word in ("cross the prime meridian", "crosses the prime meridian", "crossing the prime meridian", "on the prime meridian", "cross the greenwich", "crosses the greenwich", "przecina poludnik greenwich", "przecina poludnik zerowy", "lezy na poludniku greenwich", "lezy na poludniku zerowym", "na poludniku greenwich", "na poludniku zerowym")):
            answer = "Eastern" in hemispheres and "Western" in hemispheres
            return LocalAnswer(
                question="Does the country cross the prime meridian?",
                answer=answer,
                clarification="The country crosses the prime meridian." if answer else "The country does not cross the prime meridian.",
                explanation=f"{country['app_country_name']} territory spans: {', '.join(sorted(hemispheres))} hemispheres.",
                relation="hemisphere",
            )
        if any(word in q for word in ("northern", "polnocn", "north of equator", "north of the equator", "na polnoc od rownika", "nad rownik", "powyzej rownik", "above equator", "above the equator")):
            answer = "Northern" in hemispheres if hemispheres else lat > 0
            target = "Northern Hemisphere"
        elif any(word in q for word in ("southern", "poludn", "south of equator", "south of the equator", "na poludnie od rownika", "pod rownik", "ponizej rownik", "below equator", "below the equator")):
            answer = "Southern" in hemispheres if hemispheres else lat < 0
            target = "Southern Hemisphere"
        elif any(word in q for word in ("eastern", "wschodn", "east of the prime meridian", "east of prime meridian", "east of greenwich", "na wschod od poludnika greenwich", "na wschod od poludnika zerowego")):
            answer = "Eastern" in hemispheres if hemispheres else lon > 0
            target = "Eastern Hemisphere"
        elif any(word in q for word in ("western", "zachodn", "west of the prime meridian", "west of prime meridian", "west of greenwich", "na zachod od poludnika greenwich", "na zachod od poludnika zerowego")):
            answer = "Western" in hemispheres if hemispheres else lon < 0
            target = "Western Hemisphere"
        else:
            return None
        return LocalAnswer(
            question=f"Is the country in the {target}?",
            answer=answer,
            clarification=f"The country is in the {target}." if answer else f"The country is not in the {target}.",
            explanation=f"{country['app_country_name']} is located in the {', '.join(sorted(hemispheres)) if hemispheres else f'coordinates {lat:g}, {lon:g}'}.",
            relation="hemisphere" if hemispheres else "coordinates",
        )

    def _answer_river(self, conn, country, original, q):
        if not any(word in q for word in ("river", "rzeka", "rzek")):
            return None
        rivers = {r[0] for r in conn.execute("SELECT river_name FROM country_major_rivers WHERE country_id=?", (country["id"],))}
        all_rivers = [r[0] for r in conn.execute("SELECT DISTINCT river_name FROM country_major_rivers")]
        target = first_mentioned_value(q, all_rivers, VALUE_ALIASES)
        if not target:
            return None
        answer = target in rivers
        return LocalAnswer(
            question=f"Does the country have the {target} river?",
            answer=answer,
            clarification=f"The country has the {target} river." if answer else f"The country does not have the {target} river.",
            explanation=f"Major rivers for {country['app_country_name']}: {', '.join(sorted(rivers)) if rivers else 'none in the local database'}.",
            relation="major_rivers",
        )

    def _answer_driving_side(self, conn, country, original, q):
        if not any(word in q for word in ("drive", "driving", "left side", "right side")):
            return None
        if "left" in q:
            target = "left"
        elif "right" in q:
            target = "right"
        else:
            return None
        answer = normalize(country["driving_side"] or "") == target
        return LocalAnswer(
            question=f"Does traffic drive on the {target}?",
            answer=answer,
            clarification=f"Traffic drives on the {target} side." if answer else f"Traffic does not drive on the {target} side.",
            explanation=f"Traffic in {country['app_country_name']} drives on the {country['driving_side']}.",
            relation="driving_side",
        )

    def _answer_name_pattern(self, conn, country, original, q):
        if not any(word in q for word in ("name", "nazw")):
            return None
        cname = country["app_country_name"]
        cname_lower = cname.lower()
        m_end = re.search(r"(?:name|nazwa)\s+(?:end(?:s)?\s+(?:with|in)|konczy sie na)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_end:
            val = m_end.group(1).lower()
            answer = cname_lower.endswith(val)
            return LocalAnswer(
                question=f"Does the country name end with {val}?",
                answer=answer,
                clarification=f"The country name ends with “{val}”." if answer else f"The country name does not end with “{val}”.",
                explanation=f"The country name {cname} {'ends' if answer else 'does not end'} with “{val}”.",
                relation="name",
            )
        m_start = re.search(r"(?:name|nazwa)\s+(?:start(?:s)?\s+(?:with|in)|zaczyna sie na)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_start:
            val = m_start.group(1).lower()
            answer = cname_lower.startswith(val)
            return LocalAnswer(
                question=f"Does the country name start with {val}?",
                answer=answer,
                clarification=f"The country name starts with “{val}”." if answer else f"The country name does not start with “{val}”.",
                explanation=f"The country name {cname} {'starts' if answer else 'does not start'} with “{val}”.",
                relation="name",
            )
        m_cont = re.search(r"(?:name|nazwa)\s+(?:contain(?:s)?|zawiera)\s+[\"'\u201c\u201d]?([a-zA-Z]+)[\"'\u201c\u201d]?", q)
        if m_cont:
            val = m_cont.group(1).lower()
            answer = val in cname_lower
            return LocalAnswer(
                question=f"Does the country name contain {val}?",
                answer=answer,
                clarification=f"The country name contains “{val}”." if answer else f"The country name does not contain “{val}”.",
                explanation=f"The country name {cname} {'contains' if answer else 'does not contain'} “{val}”.",
                relation="name",
            )
        return None


def try_answer_locally(question: str, country_name: str) -> LocalAnswer | None:
    return LocalCountryFacts().try_answer(question, country_name)
