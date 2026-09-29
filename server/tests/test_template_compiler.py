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
    ("Czy graniczy z Niemcami?", "contains", "borders_country", "Germany"),

    # Island & Coastline (Pure)
    ("Is it an island country?", "equals", "is_island", True),
    ("Czy to państwo wyspiarskie?", "equals", "is_island", True),
    ("Czy to wyspa?", "equals", "is_island", True),
    ("is island?", "equals", "is_island", True),
    ("it island?", "equals", "is_island", True),
    ("Does it have a coastline?", "exists", "water_access", None),
    ("has coast?", "exists", "water_access", None),
    ("has sea?", "exists", "water_access", None),
    ("Czy ma dostęp do morza?", "exists", "water_access", None),
    ("Is it landlocked?", "not", "water_access", None),
    ("Czy jest śródlądowe?", "not", "water_access", None),

    # Driving side & Government type
    ("Is it left-driving?", "equals", "driving_side", "left"),
    ("drive left?", "equals", "driving_side", "left"),
    ("drive on left?", "equals", "driving_side", "left"),
    ("Czy obowiązuje ruch lewostronny?", "equals", "driving_side", "left"),
    ("Is it right-driving?", "equals", "driving_side", "right"),
    ("drive right?", "equals", "driving_side", "right"),
    ("Is it a monarchy?", "equals", "government_type", "Monarchy"),
    ("Czy to monarchia?", "equals", "government_type", "Monarchy"),
    ("Is it a republic?", "equals", "government_type", "Republic"),
    ("Czy to republika?", "equals", "government_type", "Republic"),

    # English Geographic areas & Historical unions & Memberships
    ("Is it in the Balkans?", "contains", "geographic_area", "Balkans"),
    ("Is it in Central Europe?", "contains", "geographic_area", "Central Europe"),
    ("Is it in Southeast Asia?", "contains", "geographic_area", "Southeast Asia"),
    ("Is it in the EU?", "contains", "membership", "EU"),
    ("Was it part of the USSR?", "contains", "historical_union", "USSR"),
    ("Was it in the Warsaw Pact?", "contains", "historical_union", "Warsaw Pact"),
    ("Does it border the Baltic Sea?", "contains", "water_access", "Baltic Sea"),
    ("Does it have access to the Mediterranean Sea?", "contains", "water_access", "Mediterranean Sea"),

    # English Hemispheres, Equator, Prime Meridian
    ("Is it in the Southern Hemisphere?", "contains", "hemisphere", "Southern"),
    ("Is it in the Northern Hemisphere?", "contains", "hemisphere", "Northern"),
    ("Is it in the Eastern Hemisphere?", "contains", "hemisphere", "Eastern"),
    ("Is it north of the equator?", "greater_than", "coordinates.latitude", 0),
    ("Is it above the equator?", "greater_than", "coordinates.latitude", 0),
    ("north to equator?", "greater_than", "coordinates.latitude", 0),
    ("Czy leży na północ od równika?", "greater_than", "coordinates.latitude", 0),
    ("Czy leży nad równikiem?", "greater_than", "coordinates.latitude", 0),
    ("nad rownikiem?", "greater_than", "coordinates.latitude", 0),
    ("Is it south of the equator?", "less_than", "coordinates.latitude", 0),
    ("Is it below the equator?", "less_than", "coordinates.latitude", 0),
    ("south to equator?", "less_than", "coordinates.latitude", 0),
    ("Czy leży na południe od równika?", "less_than", "coordinates.latitude", 0),
    ("Czy leży pod równikiem?", "less_than", "coordinates.latitude", 0),
    ("pod rownikiem?", "less_than", "coordinates.latitude", 0),
    ("Is it west of the prime meridian?", "less_than", "coordinates.longitude", 0),
    ("Is it east of the prime meridian?", "greater_than", "coordinates.longitude", 0),
    ("Czy znajduje się na zachód od południka Greenwich?", "less_than", "coordinates.longitude", 0),

    # English Relative directions
    ("Is it east of Poland?", "east_of", "coordinates.longitude", "Poland"),
    ("Is it above Germany?", "north_of", "coordinates.latitude", "Germany"),
    ("Is it north to Poland?", "north_of", "coordinates.latitude", "Poland"),
    ("north to poland?", "north_of", "coordinates.latitude", "Poland"),
    ("Is it west to Poland?", "west_of", "coordinates.longitude", "Poland"),
    ("west to poland?", "west_of", "coordinates.longitude", "Poland"),
    ("Is it east to Germany?", "east_of", "coordinates.longitude", "Germany"),
    ("east to germany?", "east_of", "coordinates.longitude", "Germany"),
    ("Is it south to France?", "south_of", "coordinates.latitude", "France"),
    ("south to france?", "south_of", "coordinates.latitude", "France"),
    ("left to poland?", "west_of", "coordinates.longitude", "Poland"),
    ("right to germany?", "east_of", "coordinates.longitude", "Germany"),

    # English Population & Area
    ("Is the population greater than 10 million?", "greater_than", "population", 10000000),
    ("pop over 10m?", "greater_than", "population", 10000000),
    ("more 10m people?", "greater_than", "population", 10000000),
    ("Is the population below 500 thousand?", "less_than", "population", 500000),
    ("Does it have more people than Poland?", "greater_than", "population", {"entity": "Poland", "relation": "population"}),
    ("Does it have fewer people than France?", "less_than", "population", {"entity": "France", "relation": "population"}),
    ("Is its area larger than 500,000 km2?", "greater_than", "area", 500000),
    ("Is the area under 100,000 sq km?", "less_than", "area", 100000),
    ("Is it bigger than Poland?", "greater_than", "area", {"entity": "Poland", "relation": "area"}),
    ("Is it smaller than Germany?", "less_than", "area", {"entity": "Germany", "relation": "area"}),
    ("Is it larger than 500k km?", "greater_than", "area", 500000),
    ("Is it under 100k km?", "less_than", "area", 100000),

    # English Language & Flag
    ("Does it have Spanish as an official language?", "contains", "official_language", "Spanish"),
    ("speak english?", "contains", "official_language", "English"),
    ("language english?", "contains", "official_language", "English"),
    ("Does its flag contain red?", "contains", "flag_color", "red"),
    ("Does its flag contain blue?", "contains", "flag_color", "blue"),
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
def test_diagonal_directions_compile_to_and_plan():
    compiled = compile_template_plan("Is it north-west of Poland?")
    assert compiled is not None
    plan, _ = compiled
    assert plan[-1] == {"operator": "and", "args": [0, 1]}
    assert [node["operator"] for node in plan[:2]] == ["north_of", "west_of"]
def test_entirely_in_hemisphere_compiles_to_and_not_plan():
    compiled = compile_template_plan("Is it entirely in the Northern Hemisphere?")
    assert compiled is not None
    plan, _ = compiled
    assert plan[-1] == {"operator": "and", "args": [0, 2]}
    assert plan[2] == {"operator": "not", "args": [1]}
    assert plan[0] == {"operator": "contains", "left": {"entity": "target_country", "relation": "hemisphere"}, "right": {"value": "Northern"}}
    assert plan[1] == {"operator": "contains", "left": {"entity": "target_country", "relation": "hemisphere"}, "right": {"value": "Southern"}}

    compiled_pl = compile_template_plan("Czy leży całkowicie na półkuli zachodniej?")
    assert compiled_pl is not None
    plan_pl, _ = compiled_pl
    assert plan_pl[0]["right"]["value"] == "Western"
    assert plan_pl[1]["right"]["value"] == "Eastern"




def test_template_compilation_is_fast():
    import time
    questions = ("Is it in Europe?", "Czy graniczy z Niemcami?", "Is it an island?") * 1000
    start = time.perf_counter()
    for question in questions:
        compile_template_plan(question)
    elapsed_ms = (time.perf_counter() - start) * 1000 / len(questions)
    assert elapsed_ms < 0.1
def test_local_planner_uses_template_without_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from countrydle.local_planner import analyze_question_for_local_plan

    result = analyze_question_for_local_plan("Does it have a coastline?", use_cache=False)
    assert result.valid and result.supported
    assert result.explanation == "Deterministic template match."
    assert result.plan == [{"operator": "exists", "left": {"entity": "target_country", "relation": "water_access"}}]

def test_open_ended_driving_side_questions_reject_with_clarification(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from countrydle.local_planner import analyze_question_for_local_plan

    queries = [
        "Which side of the road do they drive on?",
        "Po której stronie drogi się jeździ?",
        "Po której stronie się jeździ?",
        "What side do they drive on?",
        "Which side do they drive?",
    ]
    for q in queries:
        assert check_open_ended_question(q) is not None
        res = analyze_question_for_local_plan(q, use_cache=False)
        assert res.valid is False
        assert res.supported is False
        assert res.plan is None
        assert "driving side" in res.explanation or "stronę ruchu" in res.explanation
@pytest.mark.parametrize("country", _COUNTRY_NAMES)
def test_country_border_templates_cover_catalog_names(country):
    compiled = compile_template_plan(f"Does it border {country}?")
    assert compiled is not None
    plan, _ = compiled
    assert plan[0]["left"]["relation"] == "borders_country"
    assert plan[0]["right"]["value"] == country
