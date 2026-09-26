import pytest

from countrydle.template_compiler import _COUNTRY_NAMES, check_open_ended_question, compile_template_plan


@pytest.mark.parametrize("question, operator, relation, value", [
    ("Is it in Europe?", "contains", "continent", "Europe"),
    ("Czy leży w Europie?", "contains", "continent", "Europe"),
    ("Is it in the Balkans?", "contains", "geographic_area", "Balkans"),
    ("Czy leży na Bałkanach?", "contains", "geographic_area", "Balkans"),
    ("Is it in the EU?", "contains", "membership", "EU"),
    ("Czy należy do UE?", "contains", "membership", "EU"),
    ("Was it part of the USSR?", "contains", "historical_union", "USSR"),
    ("Czy należało do ZSRR?", "contains", "historical_union", "USSR"),
    ("Does it border Germany?", "contains", "borders_country", "Germany"),
    ("Czy graniczy z Niemcami?", "contains", "borders_country", "Germany"),
    ("Is it Poland?", "equals", "name", "Poland"),
    ("Czy to Polska?", "equals", "name", "Poland"),
    ("Does it have a coastline?", "exists", "water_access", None),
    ("Czy ma dostęp do morza?", "exists", "water_access", None),
    ("Is it landlocked?", "not", "water_access", None),
    ("Czy jest śródlądowe?", "not", "water_access", None),
    ("Does it border the Baltic Sea?", "contains", "water_access", "Baltic Sea"),
    ("Czy ma dostęp do Bałtyku?", "contains", "water_access", "Baltic Sea"),
    ("Is it an island country?", "equals", "is_island", True),
    ("Czy to państwo wyspiarskie?", "equals", "is_island", True),
    ("Is it north of the equator?", "greater_than", "coordinates.latitude", 0),
    ("Is it west of the prime meridian?", "less_than", "coordinates.longitude", 0),
    ("Is it left-driving?", "equals", "driving_side", "left"),
    ("Czy obowiązuje ruch lewostronny?", "equals", "driving_side", "left"),
    ("Is it a monarchy?", "equals", "government_type", "Monarchy"),
    ("Czy to monarchia?", "equals", "government_type", "Monarchy"),
    ("Does it have Spanish as an official language?", "contains", "official_language", "Spanish"),
    ("Czy językiem urzędowym jest polski?", "contains", "official_language", "Polish"),
    ("Does its flag contain red?", "contains", "flag_color", "red"),
    ("Czy na fladze jest gwiazda?", "contains", "flag_symbol", "star"),
    ("Does it have access to the Mediterranean Sea?", "contains", "water_access", "Mediterranean Sea"),
    ("Czy ma dostęp do Morza Czarnego?", "contains", "water_access", "Black Sea"),
    ("Is it in the Southern Hemisphere?", "contains", "hemisphere", "Southern"),
    ("Czy leży na półkuli południowej?", "contains", "hemisphere", "Southern"),
    ("Is it in the Northern Hemisphere?", "contains", "hemisphere", "Northern"),
    ("Czy leży na półkuli północnej?", "contains", "hemisphere", "Northern"),
    ("Is it in the Eastern Hemisphere?", "contains", "hemisphere", "Eastern"),
    ("Czy leży na półkuli zachodniej?", "contains", "hemisphere", "Western"),
    ("Czy leży na północ od równika?", "greater_than", "coordinates.latitude", 0),
    ("Is it east of the prime meridian?", "greater_than", "coordinates.longitude", 0),
    ("Czy znajduje się na zachód od południka Greenwich?", "less_than", "coordinates.longitude", 0),
    ("Is it east of Poland?", "east_of", "coordinates.longitude", "Poland"),
    ("Czy jest na południe od Francji?", "south_of", "coordinates.latitude", "France"),
    ("Is it above Germany?", "north_of", "coordinates.latitude", "Germany"),
    ("Czy leży na lewo od Polski?", "west_of", "coordinates.longitude", "Poland"),
    ("Is it a republic?", "equals", "government_type", "Republic"),
    ("Czy jeździ się po prawej stronie?", "equals", "driving_side", "right"),
    ("Does it have English as an official language?", "contains", "official_language", "English"),
    ("Czy językiem urzędowym jest hiszpański?", "contains", "official_language", "Spanish"),
    ("Does its flag contain blue?", "contains", "flag_color", "blue"),
    ("Czy na fladze jest krzyż?", "contains", "flag_symbol", "cross"),
    ("Is the population greater than 10 million?", "greater_than", "population", 10000000),
    ("Czy ma ponad 10 milionów mieszkańców?", "greater_than", "population", 10000000),
    ("Is the population below 500 thousand?", "less_than", "population", 500000),
    ("Czy populacja jest poniżej 500 tysięcy?", "less_than", "population", 500000),
    ("Does it have more people than Poland?", "greater_than", "population", {"entity": "Poland", "relation": "population"}),
    ("Czy ma więcej mieszkańców niż Niemcy?", "greater_than", "population", {"entity": "Germany", "relation": "population"}),
    ("Does it have fewer people than France?", "less_than", "population", {"entity": "France", "relation": "population"}),
    ("Czy ma mniej mieszkańców niż Włochy?", "less_than", "population", {"entity": "Italy", "relation": "population"}),
    ("Is its area larger than 500,000 km2?", "greater_than", "area", 500000),
    ("Czy powierzchnia jest większa niż 500 tysięcy km2?", "greater_than", "area", 500000),
    ("Is the area under 100,000 sq km?", "less_than", "area", 100000),
    ("Czy powierzchnia jest poniżej 100 tysięcy km2?", "less_than", "area", 100000),
    ("Is it bigger than Poland?", "greater_than", "area", {"entity": "Poland", "relation": "area"}),
    ("Czy jest większy od Polski?", "greater_than", "area", {"entity": "Poland", "relation": "area"}),
    ("Is it smaller than Germany?", "less_than", "area", {"entity": "Germany", "relation": "area"}),
    ("Czy jest mniejszy od Niemiec?", "less_than", "area", {"entity": "Germany", "relation": "area"}),
    ("Czy jest większe niż 500k km?", "greater_than", "area", 500000),
    ("Czy ma ponad 500k km?", "greater_than", "area", 500000),
    ("Is it larger than 500k km?", "greater_than", "area", 500000),
    ("Is it under 100k km?", "less_than", "area", 100000),
    ("Czy ma mniej niż 100k km?", "less_than", "area", 100000),
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
    ("north to equator?", "greater_than", "coordinates.latitude", 0),
    ("south to equator?", "less_than", "coordinates.latitude", 0),
    ("has sea?", "exists", "water_access", None),
    ("has coast?", "exists", "water_access", None),
    ("is island?", "equals", "is_island", True),
    ("it island?", "equals", "is_island", True),
    ("drive left?", "equals", "driving_side", "left"),
    ("drive right?", "equals", "driving_side", "right"),
    ("drive on left?", "equals", "driving_side", "left"),
    ("pop over 10m?", "greater_than", "population", 10000000),
    ("more 10m people?", "greater_than", "population", 10000000),
    ("speak english?", "contains", "official_language", "English"),
    ("language english?", "contains", "official_language", "English"),
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
    "Is it in Europe and Asia?", "Czy leży w Europie lub Azji?",
    "Does it live in Poland?",
    "Is it north-west of Poland and south of France?",
    "Is it above sea level?", "Czy leży powyżej poziomu morza?",
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
    assert elapsed_ms < 0.05
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
