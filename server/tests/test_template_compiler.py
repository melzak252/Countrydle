import pytest

from countrydle.template_compiler import _COUNTRY_NAMES, check_open_ended_question, compile_template_plan


@pytest.mark.parametrize("question, operator, relation, value", [
    # Continent & Countries
    ("Is it in Europe?", "contains", "continent", "Europe"),
    ("Czy leży w Europie?", "contains", "continent", "Europe"),
    ("Is it in Asia?", "contains", "continent", "Asia"),
    ("Czy leży w Azji?", "contains", "continent", "Asia"),
    ("Is it in Africa?", "contains", "continent", "Africa"),
    ("Czy leży w Afryce?", "contains", "continent", "Africa"),
    ("Is it in North America?", "contains", "continent", "North America"),
    ("Czy leży w Ameryce Północnej?", "contains", "continent", "North America"),
    ("Is it in South America?", "contains", "continent", "South America"),
    ("Czy leży w Ameryce Południowej?", "contains", "continent", "South America"),
    ("Is it Poland?", "equals", "name", "Poland"),
    ("Czy to Polska?", "equals", "name", "Poland"),
    ("Does it border Germany?", "contains", "borders_country", "Germany"),
    ("Is it east of Poland?", "east_of", "coordinates.longitude", "Poland"),
    ("Czy graniczy z Niemcami?", "contains", "borders_country", "Germany"),

    # Island & Coastline (Pure)
    ("Is it an island country?", "equals", "is_island", True),
    ("Czy to państwo wyspiarskie?", "equals", "is_island", True),
    ("Czy to wyspa?", "equals", "is_island", True),
    ("is island?", "equals", "is_island", True),
    ("Does it have a coastline?", "exists", "water_access", None),
    ("has coast?", "exists", "water_access", None),
    ("has sea?", "exists", "water_access", None),
    ("Czy ma dostęp do morza?", "exists", "water_access", None),
    ("Is it landlocked?", "not", "marine_access", None),
    ("Czy jest śródlądowe?", "not", "water_access", None),

    # Driving side & Government type
    ("Czy to monarchia?", "equals", "government_type", "Monarchy"),
    ("Czy to republika?", "equals", "government_type", "Republic"),

    # English Geographic areas & Historical unions & Memberships
    ("Is it in the Balkans?", "contains", "geographic_area", "Balkans"),
    ("Is it in Central Europe?", "contains", "geographic_area", "Central Europe"),
    ("Is it in Southeast Asia?", "contains", "geographic_area", "Southeast Asia"),
    ("Does it border the Baltic Sea?", "contains", "water_access", "Baltic Sea"),
    ("Does it have access to the Mediterranean Sea?", "contains", "water_access", "Mediterranean Sea"),

    # English Hemispheres, Equator, Prime Meridian
    ("Is it in the Southern Hemisphere?", "contains", "hemisphere", "Southern"),
    ("Is it in the Northern Hemisphere?", "contains", "hemisphere", "Northern"),
    ("Is it in the Eastern Hemisphere?", "contains", "hemisphere", "Eastern"),
    ("Is it north of the equator?", "contains", "hemisphere", "Northern"),
    ("Czy leży na północ od równika?", "contains", "hemisphere", "Northern"),
    ("Czy leży nad równikiem?", "contains", "hemisphere", "Northern"),
    ("nad rownikiem?", "contains", "hemisphere", "Northern"),
    ("Is it south of the equator?", "contains", "hemisphere", "Southern"),
    ("Czy leży na południe od równika?", "contains", "hemisphere", "Southern"),
    ("Czy leży pod równikiem?", "contains", "hemisphere", "Southern"),
    ("pod rownikiem?", "contains", "hemisphere", "Southern"),
    ("Czy znajduje się na zachód od południka Greenwich?", "contains", "hemisphere", "Western"),
    ("Czy znajduje się na wschód od południka Greenwich?", "contains", "hemisphere", "Eastern"),
    ("Czy leży na zachód od południka zerowego?", "contains", "hemisphere", "Western"),
    ("Czy leży na wschód od południka zerowego?", "contains", "hemisphere", "Eastern"),

])
def test_compile_supported_templates(question, operator, relation, value):
    compiled = compile_template_plan(question)
    assert compiled is not None
    plan, _ = compiled
    node = plan[0]
    if operator == "not":
        assert [part["operator"] for part in plan] == ["exists", "not"]
        assert plan[0]["left"]["relation"] == relation
    else:
        assert node["operator"] == operator
        assert node["left"]["relation"] == relation
    if operator in {"north_of", "south_of", "east_of", "west_of"}:
        assert node["right"]["entity"] == value
    elif isinstance(value, dict):
        assert node["right"] == value
    elif value is not None:
        assert node["right"]["value"] == value
@pytest.mark.parametrize("question", [
    # Conjunctions / open-ended / ambiguous
    "Is it in Europe and Asia?", "Czy leży w Europie lub Azji?",
    "Does it live in Poland?",
    "Is it north-west of Poland and south of France?",
    "Is it above sea level?", "Czy leży powyżej poziomu morza?",
    "Is it in Italy?", "In Italy?", "Is it in South Africa?",
    "it island?", "Is it left-driving?", "drive left?", "drive on left?",
    "Is it right-driving?", "drive right?", "Is it a monarchy?", "Is it a republic?",
    "Is it in the EU?", "Was it part of the USSR?", "Was it in the Warsaw Pact?",
    "Is it above the equator?", "north to equator?", "Is it below the equator?",
    "south to equator?", "Is it west of the prime meridian?", "Is it east of the prime meridian?",
    "Is it above Germany?", "Is it north to Poland?",
    "north to poland?", "Is it west to Poland?", "west to poland?",
    "Is it east to Germany?", "east to germany?", "Is it south to France?",
    "south to france?", "left to poland?", "right to germany?",
    "Is the population greater than 10 million?", "pop over 10m?", "more 10m people?",
    "Is the population below 500 thousand?", "Does it have more people than Poland?",
    "Does it have fewer people than France?", "Is its area larger than 500,000 km2?",
    "Is the area under 100,000 sq km?", "Is it bigger than Poland?", "Is it smaller than Germany?",
    "Is it larger than 500k km?", "Is it under 100k km?",
    "Does it have Spanish as an official language?", "speak english?", "language english?",
    "Does its flag contain red?", "Does its flag contain blue?",
    "Is it north-west of Poland?", "Is it entirely in the Northern Hemisphere?",

    # Compound / slash questions (must fall through to Gemini)
    "czy ma dostep do morza/oceanu?",
    "sea/ocean access?",
    "west/east coast?",

    # Directional coastlines (must NOT collapse to generic sea access)
    "west coastline?",
    "east coastline?",
    "north coastline?",
    "south coastline?",

    # Polish regional, historical, directional, and comparison questions
    # (Intentionally removed from templates: handled cleanly by Gemini 2.5 Flash Lite)
    "Czy leży na Bałkanach?",
    "Czy należało do ZSRR?",
    "Czy ma dostęp do Morza Czarnego?",
    "Czy jest na południe od Francji?",
    "Czy leży na lewo od Polski?",
    "Czy obowiązuje ruch lewostronny?",
    "Czy ruch jest prawostronny?",
    "czy jest po prawej stronie od słoweni",
    "czy leży na prawo od słowenii",
    "Czy ma ponad 10 milionów mieszkańców?",
    "Czy populacja jest poniżej 500 tysięcy?",
    "Czy ma więcej mieszkańców niż Niemcy?",
    "Czy ma mniej mieszkańców niż Włochy?",
    "Czy powierzchnia jest większa niż 500 tysięcy km2?",
    "Czy powierzchnia jest poniżej 100 tysięcy km2?",
    "Czy jest większy od Polski?",
    "Czy jest mniejszy od Niemiec?",
    "Czy jest większe niż 500k km?",
    "Czy ma ponad 500k km?",
    "Czy ma mniej niż 100k km?",
    "Czy to północna część Afryki?",
])
def test_unrecognized_or_ambiguous_questions_fall_through(question):
    assert compile_template_plan(question) is None


def test_polish_entirely_in_hemisphere_behavior_is_unchanged():
    compiled_pl = compile_template_plan("Czy leży całkowicie na półkuli zachodniej?")
    assert compiled_pl is not None
    plan_pl, _ = compiled_pl
    assert plan_pl[0]["right"]["value"] == "Western"
    assert plan_pl[1]["right"]["value"] == "Eastern"


def test_open_ended_driving_side_questions_reject_with_clarification():
    queries = [
        "Which side of the road do they drive on?",
        "Po której stronie drogi się jeździ?",
        "What side do they drive on?",
        "Which side do they drive?",
    ]
    for q in queries:
        res = check_open_ended_question(q)
        assert res is not None
        assert "driving side" in res or "stronę ruchu" in res
@pytest.mark.parametrize("country", _COUNTRY_NAMES)
def test_country_border_templates_cover_catalog_names(country):
    if " and " in country.casefold() or "-" in country:
        assert compile_template_plan(f"Does it border {country}?") is None
        return
    compiled = compile_template_plan(f"Does it border {country}?")
    assert compiled is not None
    plan, _ = compiled
    assert plan[0]["left"]["relation"] == "borders_country"
    assert plan[0]["right"]["value"] == country
