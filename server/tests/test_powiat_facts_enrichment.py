"""Enrichment and executor regressions against a private, source-built SQLite KB.

Provider interpretation checks are explicit live opt-in and are not evidence of
current factual accuracy. Offline facts come from the checked-in PRG catalog and
the real enrichment builder; expected geographical answers remain independent.
"""
from pathlib import Path
from collections import Counter
from dataclasses import replace
import importlib
import json
import os
import sqlite3
import pytest

from local_kb_question import execute_plan
from powiatdle.utils import LOCAL_CONFIG

DB_PATH = LOCAL_CONFIG.db_path

live_planner_eval = pytest.mark.skipif(
    os.getenv("COUNTRYDLE_RUN_LIVE_PLANNER_EVAL") != "1",
    reason="Set COUNTRYDLE_RUN_LIVE_PLANNER_EVAL=1 for current provider interpretation checks",
)


@pytest.fixture(autouse=True)
def private_enriched_facts(monkeypatch, tmp_path):
    from powiat_names import build_powiat_aliases
    from scripts.enrich_powiat_facts import enrich_database
    from voivodeship_names import CANONICAL_VOIVODESHIPS
    from wojewodztwodle import utils as woj_utils

    local_kb = Path(__file__).resolve().parents[1] / "powiatdle" / "local_kb"
    catalog = json.loads((local_kb / "borders.json").read_text(encoding="utf-8"))["source"]["county_names"]
    duplicates = Counter(name.casefold() for name in catalog.values())
    database = tmp_path / "powiat-facts.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript((local_kb / "schema.sql").read_text(encoding="utf-8"))
        connection.execute("ALTER TABLE powiats ADD COLUMN latitude REAL")
        connection.execute("ALTER TABLE powiats ADD COLUMN longitude REAL")
        rows = []
        for code, source_name in sorted(catalog.items()):
            province = CANONICAL_VOIVODESHIPS[int(code[:2]) // 2 - 1]
            is_city = int(code[2:]) >= 60
            name = source_name.removeprefix("powiat ") if is_city else "Powiat " + source_name.removeprefix("powiat ")
            if duplicates[source_name.casefold()] > 1:
                name += f" (województwo {province.lower()})"
            rows.append((int(code), name, province, int(is_city), code, "frozen PRG catalog"))
        connection.executemany(
            "INSERT INTO powiats (id, name, voivodeship, is_city_county, terc, md_file) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.row_factory = sqlite3.Row
        aliases = build_powiat_aliases(dict(row) for row in connection.execute("SELECT * FROM powiats"))
        connection.executemany(
            "INSERT INTO powiat_name_aliases VALUES (?, ?)",
            [(alias, identifier) for alias, identifiers in aliases.items() for identifier in identifiers],
        )
        # Fixed representative-point operands, not a certification of territorial extent.
        connection.executemany(
            "UPDATE powiats SET latitude = ?, longitude = ? WHERE name = ?",
            [(52.23, 21.01, "Warszawa"), (52.41, 16.93, "Poznań"),
             (52.35, 14.56, "Powiat słubicki"), (53.13, 23.16, "Białystok"),
             (52.12, 16.12, "Powiat wolsztyński")],
        )
    enrich_database(database)
    monkeypatch.setitem(globals(), "DB_PATH", database)
    monkeypatch.setitem(globals(), "LOCAL_CONFIG", replace(LOCAL_CONFIG, db_path=database))

    province_db = tmp_path / "province-facts.sqlite"
    with sqlite3.connect(province_db) as connection:
        connection.executescript("""
            CREATE TABLE voivodeships (id INTEGER PRIMARY KEY, name TEXT, longitude REAL);
            INSERT INTO voivodeships VALUES (1, 'Śląskie', 19.02), (2, 'Mazowieckie', 21.01);
        """)
    monkeypatch.setattr(woj_utils, "LOCAL_CONFIG", replace(woj_utils.LOCAL_CONFIG, db_path=province_db))
    cache_module = importlib.import_module("utils.plan_cache")
    monkeypatch.setattr(cache_module, "plan_cache", cache_module.PlanCache(db_path=tmp_path / "cache.sqlite"))


def get_country_borders(powiat_name: str) -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.country_name 
            FROM powiats p 
            JOIN powiat_borders_countries b ON p.id = b.powiat_id 
            WHERE p.name = ?
        """, (powiat_name,))
        return {r[0] for r in cursor.fetchall()}


def get_rivers(powiat_name: str) -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.river_name 
            FROM powiats p 
            JOIN powiat_major_rivers r ON p.id = r.powiat_id 
            WHERE p.name = ?
        """, (powiat_name,))
        return {r[0] for r in cursor.fetchall()}


def get_roads(powiat_name: str) -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rd.road_name 
            FROM powiats p 
            JOIN powiat_major_roads rd ON p.id = rd.powiat_id 
            WHERE p.name = ?
        """, (powiat_name,))
        return {r[0] for r in cursor.fetchall()}


def test_powiat_international_borders_positive_checks():
    # Germany
    assert "Niemcy" in get_country_borders("Świnoujście")
    assert "Niemcy" in get_country_borders("Powiat słubicki")
    assert "Niemcy" in get_country_borders("Powiat zgorzelecki")
    assert "Niemcy" in get_country_borders("Powiat policki")
    assert "Niemcy" in get_country_borders("Powiat gryfiński")

    # Czechia
    assert "Czechy" in get_country_borders("Powiat głubczycki")
    assert "Czechy" in get_country_borders("Powiat cieszyński")
    assert "Czechy" in get_country_borders("Powiat kłodzki")
    assert "Czechy" in get_country_borders("Powiat nyski")

    # Slovakia
    assert "Słowacja" in get_country_borders("Powiat tatrzański")
    assert "Słowacja" in get_country_borders("Powiat nowotarski")
    assert "Słowacja" in get_country_borders("Powiat bieszczadzki")

    # Ukraine
    assert "Ukraina" in get_country_borders("Powiat przemyski")
    assert "Ukraina" in get_country_borders("Powiat tomaszowski (województwo lubelskie)")
    assert "Ukraina" in get_country_borders("Powiat hrubieszowski")

    # Belarus
    assert "Białoruś" in get_country_borders("Powiat hajnowski")
    assert "Białoruś" in get_country_borders("Powiat sokólski")
    assert "Białoruś" in get_country_borders("Powiat włodawski")

    # Lithuania
    assert "Litwa" in get_country_borders("Powiat sejneński")
    assert "Litwa" in get_country_borders("Powiat suwalski")

    # Russia
    assert "Rosja" in get_country_borders("Powiat braniewski")
    assert "Rosja" in get_country_borders("Powiat bartoszycki")
    assert "Rosja" in get_country_borders("Powiat gołdapski")


def test_powiat_international_borders_no_false_positives():
    # Podlaskie counties must NEVER border Germany
    assert "Niemcy" not in get_country_borders("Powiat augustowski")
    assert "Niemcy" not in get_country_borders("Powiat suwalski")
    assert "Niemcy" not in get_country_borders("Powiat bielski (województwo podlaskie)")
    assert "Niemcy" not in get_country_borders("Powiat kolneński")
    assert "Niemcy" not in get_country_borders("Powiat łomżyński")
    assert "Niemcy" not in get_country_borders("Powiat wysokomazowiecki")

    # Interior counties must NEVER border foreign countries
    assert "Niemcy" not in get_country_borders("Powiat lipnowski")
    assert "Niemcy" not in get_country_borders("Powiat ostrowski (województwo mazowieckie)")
    assert len(get_country_borders("Warszawa")) == 0
    assert len(get_country_borders("Kraków")) == 0
    assert len(get_country_borders("Łódź")) == 0
    assert len(get_country_borders("Poznań")) == 0


def test_powiat_major_rivers():
    # Wisła crosses major historical cities and counties
    assert "Wisła" in get_rivers("Płock")
    assert "Wisła" in get_rivers("Warszawa")
    assert "Wisła" in get_rivers("Toruń")
    assert "Wisła" in get_rivers("Kraków")
    assert "Wisła" in get_rivers("Gdańsk")
    assert "Wisła" in get_rivers("Powiat cieszyński")

    # Odra
    assert "Odra" in get_rivers("Wrocław")
    assert "Odra" in get_rivers("Szczecin")
    assert "Odra" in get_rivers("Opole")
    assert "Odra" in get_rivers("Powiat raciborski")

    # Warta
    assert "Warta" in get_rivers("Poznań")
    assert "Warta" in get_rivers("Gorzów Wielkopolski")
    assert "Warta" in get_rivers("Częstochowa")

    # Bug
    assert "Bug" in get_rivers("Powiat wyszkowski")
    assert "Bug" in get_rivers("Powiat włodawski")

    # Narew
    assert "Narew" in get_rivers("Łomża")
    assert "Narew" in get_rivers("Ostrołęka")

    # San
    assert "San" in get_rivers("Przemyśl")
    assert "San" in get_rivers("Powiat sanocki")


def test_powiat_major_roads():
    # Expressways and motorways correctly assigned
    assert "S8" in get_roads("Powiat wyszkowski")
    assert "S8" in get_roads("Warszawa")
    assert "S8" in get_roads("Wrocław")
    assert "S8" in get_roads("Białystok")

    # A1
    assert "A1" in get_roads("Gdańsk")
    assert "A1" in get_roads("Toruń")
    assert "A1" in get_roads("Łódź")
    assert "A1" in get_roads("Częstochowa")
    assert "A1" in get_roads("Gliwice")
    # Płock does NOT have A1
    assert "A1" not in get_roads("Płock")

    # A2
    assert "A2" in get_roads("Poznań")
    assert "A2" in get_roads("Warszawa")
    assert "A2" in get_roads("Powiat słubicki")

    # A4
    assert "A4" in get_roads("Wrocław")
    assert "A4" in get_roads("Powiat opolski (województwo opolskie)")
    assert "A4" in get_roads("Gliwice")
    assert "A4" in get_roads("Katowice")
    assert "A4" in get_roads("Kraków")
    assert "A4" in get_roads("Rzeszów")

    # S7
    assert "S7" in get_roads("Gdańsk")
    assert "S7" in get_roads("Radom")
    assert "S7" in get_roads("Kielce")
    assert "S7" in get_roads("Kraków")


def test_powiat_water_access_baltic_sea():
    # Coastal counties
    coastal_samples = ["Świnoujście", "Powiat kołobrzeski", "Powiat pucki", "Gdynia", "Gdańsk"]
    with sqlite3.connect(DB_PATH) as conn:
        for name in coastal_samples:
            row = conn.execute("SELECT id FROM powiats WHERE name = ?", (name,)).fetchone()
            assert row is not None
            has_coast = conn.execute(
                "SELECT 1 FROM powiat_water_access WHERE powiat_id = ? AND water_name = 'Morze Bałtyckie'",
                (row[0],)
            ).fetchone()
            assert has_coast is not None, f"{name} should have access to Morze Bałtyckie"

        inland_samples = ["Kraków", "Warszawa", "Poznań", "Wrocław"]
        for name in inland_samples:
            row = conn.execute("SELECT id FROM powiats WHERE name = ?", (name,)).fetchone()
            assert row is not None
            has_coast = conn.execute(
                "SELECT 1 FROM powiat_water_access WHERE powiat_id = ? AND water_name = 'Morze Bałtyckie'",
                (row[0],)
            ).fetchone()
            assert has_coast is None, f"{name} must NOT have access to Morze Bałtyckie"


@live_planner_eval
def test_powiat_grammar_and_identity_fixes():
    from local_kb_question import analyze_question, execute_plan

    # 1. Grammar: Instrumental case after "z / ze"
    p_cz = analyze_question("Czy powiat graniczy z Czechami?", LOCAL_CONFIG, use_cache=False)
    ans_cieszyn = execute_plan(LOCAL_CONFIG, "Powiat cieszyński", p_cz)
    assert ans_cieszyn.answer is True
    assert "graniczy z Czechami." in ans_cieszyn.explanation

    ans_chojnice = execute_plan(LOCAL_CONFIG, "Powiat chojnicki", p_cz)
    assert ans_chojnice.answer is False
    assert "nie graniczy z Czechami." in ans_chojnice.explanation

    p_sk = analyze_question("Czy powiat graniczy ze Słowacją?", LOCAL_CONFIG, use_cache=False)
    ans_zywiec = execute_plan(LOCAL_CONFIG, "Powiat żywiecki", p_sk)
    assert ans_zywiec.answer is True
    assert "ze Słowacją." in ans_zywiec.explanation

    # 2. Direct Identity: Adjective form matching
    p_ident = analyze_question("Czy to powiat chojnicki?", LOCAL_CONFIG, use_cache=False)
    ans_ident = execute_plan(LOCAL_CONFIG, "Powiat chojnicki", p_ident)
    assert ans_ident.answer is True


@live_planner_eval
def test_powiat_relative_directions():
    from local_kb_question import analyze_question, execute_plan

    p_west = analyze_question("Czy powiat leży na zachód od Warszawy?", LOCAL_CONFIG, use_cache=False)
    assert p_west.valid is True
    assert p_west.supported is True

    ans_slubice = execute_plan(LOCAL_CONFIG, "Powiat słubicki", p_west)
    assert ans_slubice.answer is True

    ans_bialystok = execute_plan(LOCAL_CONFIG, "Białystok", p_west)
    assert ans_bialystok.answer is False

    p_south = analyze_question("Czy powiat leży na południe od Poznania?", LOCAL_CONFIG, use_cache=False)
    ans_wolsztyn = execute_plan(LOCAL_CONFIG, "Powiat wolsztyński", p_south)
    assert ans_wolsztyn.answer is True


@live_planner_eval
def test_historical_regions_and_partitions():
    from local_kb_question import analyze_question, execute_plan

    # Historical partitions
    p_pruski = analyze_question("Czy powiat leżał w zaborze pruskim?", LOCAL_CONFIG, use_cache=False)
    assert p_pruski.valid is True and p_pruski.supported is True
    assert execute_plan(LOCAL_CONFIG, "Poznań", p_pruski).answer is True
    assert execute_plan(LOCAL_CONFIG, "Warszawa", p_pruski).answer is False

    p_rosyjski = analyze_question("Czy powiat leżał w zaborze rosyjskim?", LOCAL_CONFIG, use_cache=False)
    assert p_rosyjski.valid is True and p_rosyjski.supported is True
    assert execute_plan(LOCAL_CONFIG, "Warszawa", p_rosyjski).answer is True
    assert execute_plan(LOCAL_CONFIG, "Poznań", p_rosyjski).answer is False

    p_odzyskane = analyze_question("Czy powiat leży na Ziemiach Odzyskanych?", LOCAL_CONFIG, use_cache=False)
    assert p_odzyskane.valid is True and p_odzyskane.supported is True
    assert execute_plan(LOCAL_CONFIG, "Wrocław", p_odzyskane).answer is True
    assert execute_plan(LOCAL_CONFIG, "Kraków", p_odzyskane).answer is False

    # Historical lands
    p_mazowsze = analyze_question("Czy powiat leży na Mazowszu?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Płock", p_mazowsze).answer is True
    assert execute_plan(LOCAL_CONFIG, "Gdańsk", p_mazowsze).answer is False

    p_slask = analyze_question("Czy powiat leży na Śląsku?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Gliwice", p_slask).answer is True
    assert execute_plan(LOCAL_CONFIG, "Warszawa", p_slask).answer is False

    p_malopolska = analyze_question("Czy powiat leży w Małopolsce?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Kraków", p_malopolska).answer is True
    assert execute_plan(LOCAL_CONFIG, "Poznań", p_malopolska).answer is False


@live_planner_eval
def test_wojewodztwodle_relative_directions():
    from wojewodztwodle.utils import LOCAL_CONFIG as WOJ_CONFIG
    from local_kb_question import analyze_question, execute_plan

    p = analyze_question("Czy województwo leży na zachód od Mazowsza?", WOJ_CONFIG, use_cache=False)
    assert p.valid is True and p.supported is True
    ans = execute_plan(WOJ_CONFIG, "śląskie", p)
    assert ans.answer is True


@live_planner_eval
def test_powiat_national_parks():
    from local_kb_question import analyze_question, execute_plan

    p_any = analyze_question("Czy na terenie powiatu znajduje się park narodowy?", LOCAL_CONFIG, use_cache=False)
    assert p_any.valid is True and p_any.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat tatrzański", p_any).answer is True
    assert execute_plan(LOCAL_CONFIG, "Warszawa", p_any).answer is False

    p_tpn = analyze_question("Czy w powiecie znajduje się Tatrzański Park Narodowy?", LOCAL_CONFIG, use_cache=False)
    assert p_tpn.valid is True and p_tpn.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat tatrzański", p_tpn).answer is True
    assert execute_plan(LOCAL_CONFIG, "Powiat hajnowski", p_tpn).answer is False

    p_bpn = analyze_question("Czy w powiecie leży Białowieski Park Narodowy?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Powiat hajnowski", p_bpn).answer is True


@live_planner_eval
def test_powiat_major_lakes():
    from local_kb_question import analyze_question, execute_plan

    p_sniardwy = analyze_question("Czy w powiecie znajduje się jezioro Śniardwy?", LOCAL_CONFIG, use_cache=False)
    assert p_sniardwy.valid is True and p_sniardwy.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat piski", p_sniardwy).answer is True
    assert execute_plan(LOCAL_CONFIG, "Kraków", p_sniardwy).answer is False

    p_solina = analyze_question("Czy w powiecie leży jezioro Solina?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Powiat leski", p_solina).answer is True

    p_goplo = analyze_question("Czy w powiecie znajduje się jezioro Gopło?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Powiat inowrocławski", p_goplo).answer is True


@live_planner_eval
def test_powiat_unesco_sites():
    from local_kb_question import analyze_question, execute_plan

    p_any = analyze_question("Czy w powiecie znajduje się obiekt z listy UNESCO?", LOCAL_CONFIG, use_cache=False)
    assert p_any.valid is True and p_any.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat wielicki", p_any).answer is True
    assert execute_plan(LOCAL_CONFIG, "Toruń", p_any).answer is True
    assert execute_plan(LOCAL_CONFIG, "Zamość", p_any).answer is True
    assert execute_plan(LOCAL_CONFIG, "Powiat chojnicki", p_any).answer is False

    p_malbork = analyze_question("Czy w powiecie znajduje się zamek w Malborku?", LOCAL_CONFIG, use_cache=False)
    assert execute_plan(LOCAL_CONFIG, "Powiat malborski", p_malbork).answer is True


@live_planner_eval
def test_powiat_health_resorts():
    from local_kb_question import analyze_question, execute_plan

    p_spa = analyze_question("Czy w powiecie znajduje się uzdrowisko?", LOCAL_CONFIG, use_cache=False)
    assert p_spa.valid is True and p_spa.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat aleksandrowski", p_spa).answer is True  # Ciechocinek
    assert execute_plan(LOCAL_CONFIG, "Powiat kołobrzeski", p_spa).answer is True     # Kołobrzeg
    assert execute_plan(LOCAL_CONFIG, "Powiat nowosądecki", p_spa).answer is True     # Krynica-Zdrój
    assert execute_plan(LOCAL_CONFIG, "Sopot", p_spa).answer is True                  # Sopot
    assert execute_plan(LOCAL_CONFIG, "Powiat pińczowski", p_spa).answer is False


@pytest.mark.parametrize("relation, operator, value, expected_answers", [
    ("borders_country", "contains_exact", "Czechy", {"Powiat cieszyński": True, "Powiat chojnicki": False}),
    ("borders_country", "contains_exact", "Słowacja", {"Powiat żywiecki": True, "Powiat chojnicki": False}),
    ("name", "equals", "Powiat chojnicki", {"Powiat chojnicki": True, "Powiat cieszyński": False}),
    ("historical_partitions", "contains_exact", "Zabór pruski", {"Poznań": True, "Warszawa": False}),
    ("historical_partitions", "contains_exact", "Zabór rosyjski", {"Warszawa": True, "Poznań": False}),
    ("historical_partitions", "contains_exact", "Ziemie Odzyskane", {"Wrocław": True, "Kraków": False}),
    ("historical_regions", "contains_exact", "Mazowsze", {"Płock": True, "Gdańsk": False}),
    ("historical_regions", "contains_exact", "Śląsk", {"Gliwice": True, "Warszawa": False}),
    ("historical_regions", "contains_exact", "Małopolska", {"Kraków": True, "Poznań": False}),
    ("national_parks", "exists", None, {"Powiat tatrzański": True, "Warszawa": False}),
    ("national_parks", "contains_exact", "Tatrzański Park Narodowy", {"Powiat tatrzański": True, "Powiat hajnowski": False}),
    ("national_parks", "contains_exact", "Białowieski Park Narodowy", {"Powiat hajnowski": True, "Powiat tatrzański": False}),
    ("major_lakes", "contains_exact", "Śniardwy", {"Powiat piski": True, "Kraków": False}),
    ("major_lakes", "contains_exact", "Solina", {"Powiat leski": True, "Kraków": False}),
    ("major_lakes", "contains_exact", "Gopło", {"Powiat inowrocławski": True, "Kraków": False}),
    ("unesco_sites", "exists", None, {"Powiat wielicki": True, "Toruń": True, "Zamość": True, "Powiat chojnicki": False}),
    ("unesco_sites", "contains_partial", "Malbork", {"Powiat malborski": True, "Powiat chojnicki": False}),
    ("health_resorts", "exists", None, {"Powiat aleksandrowski": True, "Powiat kołobrzeski": True, "Powiat nowosądecki": True, "Sopot": True, "Powiat pińczowski": False}),
])
def test_enriched_relations_execute_supplied_predicates_offline(relation, operator, value, expected_answers):
    """Exercise real enrichment/execution, not natural-language interpretation."""
    from local_kb_question import QuestionPlan

    predicate = {"operator": operator, "left": {"entity": "target_powiat", "relation": relation}}
    if value is not None:
        predicate["right"] = {"value": value}
    plan = QuestionPlan(
        original_question="Executor fixture predicate", valid=True, supported=True,
        improved_question=None, explanation=None, plan=predicate,
    )
    for target, expected in expected_answers.items():
        result = execute_plan(LOCAL_CONFIG, target, plan)
        assert result is not None, (relation, target)
        assert result.answer is expected, (relation, target)


@pytest.mark.parametrize("operator, relation, reference, expected_answers", [
    ("west_of", "longitude", "Warszawa", {"Powiat słubicki": True, "Białystok": False}),
    ("south_of", "latitude", "Poznań", {"Powiat wolsztyński": True, "Białystok": False}),
])
def test_relative_direction_executor_uses_named_reference_offline(operator, relation, reference, expected_answers):
    from local_kb_question import QuestionPlan

    plan = QuestionPlan(
        original_question="Representative-point comparison", valid=True, supported=True,
        improved_question=None, explanation=None,
        plan={"operator": operator, "left": {"entity": "target_powiat", "relation": relation},
              "right": {"entity": reference, "relation": relation}},
    )
    for target, expected in expected_answers.items():
        result = execute_plan(LOCAL_CONFIG, target, plan)
        assert result is not None
        assert result.answer is expected


@pytest.mark.parametrize("question, positive, negative", [
    ("Czy powiat graniczy z Czechami?", "Powiat cieszyński", "Powiat chojnicki"),
    ("Czy powiat graniczy ze Słowacją?", "Powiat żywiecki", "Powiat chojnicki"),
])
def test_country_border_templates_execute_without_provider(monkeypatch, question, positive, negative):
    import local_kb_question

    def unexpected_provider(*args, **kwargs):
        pytest.fail("A deterministic border template must not request a provider")

    monkeypatch.setattr(local_kb_question, "gemini_json", unexpected_provider)
    planned = local_kb_question.analyze_question(question, LOCAL_CONFIG, use_cache=False)
    assert planned.valid is True and planned.supported is True
    assert execute_plan(LOCAL_CONFIG, positive, planned).answer is True
    assert execute_plan(LOCAL_CONFIG, negative, planned).answer is False


def test_province_direction_executor_uses_named_reference_offline():
    from local_kb_question import QuestionPlan
    from wojewodztwodle.utils import LOCAL_CONFIG as config

    planned = QuestionPlan(
        original_question="Representative-point comparison", valid=True, supported=True,
        improved_question=None, explanation=None,
        plan={"operator": "west_of", "left": {"entity": "target_voivodeship", "relation": "longitude"},
              "right": {"entity": "Mazowieckie", "relation": "longitude"}},
    )
    assert execute_plan(config, "Śląskie", planned).answer is True
    assert execute_plan(config, "Mazowieckie", planned).answer is False
