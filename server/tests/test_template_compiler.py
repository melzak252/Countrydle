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
    ("Czy jest śródlądowe?", "not", "marine_access", None),

    # Driving side & Government type
    ("Czy to monarchia?", "equals", "government_type", "Monarchy"),
    ("Czy to republika?", "equals", "government_type", "Republic"),

    # English Geographic areas & Historical unions & Memberships
    ("Is it in the Balkans?", "contains", "geographic_area", "Balkans"),
    ("Is it in Central Europe?", "contains", "geographic_area", "Central Europe"),
    ("Is it in Southeast Asia?", "contains", "geographic_area", "Southeast Asia"),
    ("Does it border the Baltic Sea?", "contains", "water_access", "Baltic Sea"),
    ("Does it have access to the Mediterranean Sea?", "contains", "water_access", "Mediterranean Sea"),
    ("Is it left-driving?", "equals", "driving_side", "left"),
    ("Is it right-driving?", "equals", "driving_side", "right"),
    ("Is it a monarchy?", "equals", "government_type", "Monarchy"),
    ("Is it a republic?", "equals", "government_type", "Republic"),
    ("Is it in the EU?", "contains", "membership", "EU"),
    ("Was it part of the USSR?", "contains", "historical_union", "USSR"),
    ("Was it in the Warsaw Pact?", "contains", "historical_union", "Warsaw Pact"),
    ("Does it have Spanish as an official language?", "contains", "official_language", "Spanish"),
    ("Does its flag contain red?", "contains", "flag_color", "red"),
    ("Does its flag contain blue?", "contains", "flag_color", "blue"),
    ("Czy leży na Bałkanach?", "contains", "geographic_area", "Balkans"),
    ("Czy należało do ZSRR?", "contains", "historical_union", "USSR"),
    ("Czy ma dostęp do Morza Czarnego?", "contains", "water_access", "Black Sea"),
    ("Czy obowiązuje ruch lewostronny?", "equals", "driving_side", "left"),
    ("Czy ruch jest prawostronny?", "equals", "driving_side", "right"),
    ("Czy to północna część Afryki?", "contains", "geographic_area", "Northern Africa"),
    ("Czy ma ponad 10 milionów mieszkańców?", "greater_than", "population", 10_000_000),
    ("Czy populacja jest poniżej 500 tysięcy?", "less_than", "population", 500_000),
    ("Czy ma więcej mieszkańców niż Niemcy?", "greater_than", "population", "Germany"),
    ("Czy ma mniej mieszkańców niż Włochy?", "less_than", "population", "Italy"),
    ("Czy powierzchnia jest większa niż 500 tysięcy km2?", "greater_than", "area", 500_000),
    ("Czy powierzchnia jest poniżej 100 tysięcy km2?", "less_than", "area", 100_000),
    ("Czy jest większy od Polski?", "greater_than", "area", "Poland"),
    ("Czy jest mniejszy od Niemiec?", "less_than", "area", "Germany"),
    # English Hemispheres, Equator, Prime Meridian
    ("Is it in the Southern Hemisphere?", "contains", "hemisphere", "Southern"),
    ("Is it in the Northern Hemisphere?", "contains", "hemisphere", "Northern"),
    ("Is it in the Eastern Hemisphere?", "contains", "hemisphere", "Eastern"),
    ("Is it north of the equator?", "contains", "hemisphere", "Northern"),
    ("is it north of equator?", "contains", "hemisphere", "Northern"),
    ("Is it south of the equator?", "contains", "hemisphere", "Southern"),
    ("is it south of equator?", "contains", "hemisphere", "Southern"),
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
    ("Czy jest na południe od Francji?", "south_of", "coordinates.latitude", "France"),
    ("Czy leży na lewo od Polski?", "west_of", "coordinates.longitude", "Poland"),
    ("czy leży na prawo od słowenii", "east_of", "coordinates.longitude", "Slovenia"),
    ("does the country name end with stan?", "ends_with", "name", "stan"),
    ("does the country have less than 10 million inhabitants?", "less_than", "population", 10_000_000),

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
    elif isinstance(node.get("right"), dict) and "entity" in node["right"]:
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
    "it island?", "drive left?", "drive on left?",
    "drive right?",
    "Is it above the equator?", "north to equator?", "Is it below the equator?",
    "south to equator?", "Is it west of the prime meridian?", "Is it east of the prime meridian?",
    "Is it above Germany?", "Is it north to Poland?",
    "north to poland?", "Is it west to Poland?", "west to poland?",
    "Is it east to Germany?", "east to germany?", "Is it south to France?",
    "south to france?", "left to poland?", "right to germany?",
    "pop over 10m?", "more 10m people?",
    "Does it have more people than Poland?", "Does it have fewer people than France?",
    "Is it bigger than Poland?", "Is it smaller than Germany?",
    "Is it larger than 500k km?", "Is it under 100k km?",
    "speak english?", "language english?",
    "Is it north-west of Poland?", "Is it entirely in the Northern Hemisphere?",
    "Does it touch South America and Europe?",
    "Does it touch South America by sea?",
    "Does it touch southern Europe?",
    "Does it touch South America only?",
    "Does it not touch South America or Africa?",
    "Does it touch the coast of South America?",
    "Does the capital touch South America?",

    # Compound / slash questions (must fall through to Gemini)
    "sea/ocean access?",
    "west/east coast?",

    # Directional coastlines (must NOT collapse to generic sea access)
    "west coastline?",
    "east coastline?",
    "north coastline?",
    "south coastline?",

    # Polish regional, historical, directional, and comparison questions
    # Polish bare-km area queries and vague directional phrases fall through
    "Czy jest większe niż 500k km?",
    "Czy ma ponad 500k km?",
    "Czy ma mniej niż 100k km?",
    "Czy leży na południu Afryki?",
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
        "when was this country founded",
        "when was it founded",
        "when did it gain independence",
        "kiedy powstał ten kraj",
        "where is this country located",
        "where is it",
        "gdzie leży ten kraj",
        "who is the president",
        "kto rządzi",
        "what is the capital of this country",
        "jaka jest stolica",
        "what is the official language",
        "jaki jest język",
        "what is the currency",
        "jaka jest waluta",
        "how many people live in this country",
        "how many countries border it",
        "ile ma mieszkańców",
        "why is this country famous",
        "dlaczego ten kraj",
    ]
    for q in queries:
        res = check_open_ended_question(q)
        assert res is not None, f"Expected open-ended clarification for {q}"
        assert "yes/no" in res.lower()
        assert "question" in res.lower()


def test_local_planner_rejects_open_ended_questions():
    from countrydle.local_planner import analyze_question_for_local_plan
    for q in ("when was this country founded", "where is it", "kiedy powstał ten kraj", "how many people live there"):
        plan = analyze_question_for_local_plan(q)
        assert plan.valid is False
        assert plan.supported is False
        assert plan.plan is None
        assert plan.explanation is not None



@pytest.mark.parametrize("question", [
    "Does it border Germany?",
    "Czy graniczy z Niemcami?",
])
def test_border_rewrite_is_english_for_both_input_languages(question):
    plan, improved = compile_template_plan(question)
    assert plan[0]["operator"] == "contains"
    assert plan[0]["left"]["relation"] == "borders_country"
    assert plan[0]["right"]["value"] == "Germany"
    assert "border" in improved.lower()
    assert "Germany" in improved
    assert improved.rstrip().endswith("?")


@pytest.mark.parametrize("question", [
    "Is it in Europe?",
    "Czy leży w Europie?",
])
def test_continent_rewrite_is_english_for_both_input_languages(question):
    plan, improved = compile_template_plan(question)
    assert plan[0]["operator"] == "contains"
    assert plan[0]["left"]["relation"] == "continent"
    assert plan[0]["right"]["value"] == "Europe"
    assert "country" in improved.lower()
    assert "Europe" in improved
    assert improved.rstrip().endswith("?")

def test_flag_symbol_moon_and_crescent_matching():
    from countrydle.local_planner import analyze_question_for_local_plan
    from countrydle.local_answering import execute_local_plan

    moon_queries = (
        "does it have a moon in a flag",
        "does it have a moon on its flag",
        "does it have a crescent on its flag",
        "does it have a crescent moon on its flag",
        "does the flag have a moon",
        "is there a moon on the flag",
        "does its flag have a moon",
        "czy na fladze jest księżyc",
    )
    for q in moon_queries:
        plan = analyze_question_for_local_plan(q)
        assert plan.valid is True
        assert plan.supported is True
        assert plan.plan is not None
        assert plan.plan.get("operator") == "contains"
        assert plan.plan.get("left", {}).get("relation") == "flag_symbol"
        assert plan.plan.get("right", {}).get("value") == "crescent"
        ans_uzb = execute_local_plan(plan.plan, "Uzbekistan", q)
        assert ans_uzb.answer is True
        ans_pol = execute_local_plan(plan.plan, "Poland", q)
        assert ans_pol.answer is False

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
