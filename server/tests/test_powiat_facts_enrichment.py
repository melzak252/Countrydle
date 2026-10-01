"""Test suite verifying accuracy and completeness of enriched Powiatdle facts.

Covers:
1. Accurate international borders (zero false positives like Podlaskie bordering Germany;
   real border counties like Świnoujście, Słubice, Głubczyce present).
2. Major river coverage (Wisła in Płock/Warszawa/Toruń/Kraków/Gdańsk; Odra, Warta, Bug, San).
3. Motorways and Expressways (A1-A18, S1-S86 correctly intersecting traversed counties).
4. Baltic Sea water access for coastal counties.
"""
from pathlib import Path
import sqlite3
import pytest

from local_kb_question import execute_plan
from powiatdle.utils import LOCAL_CONFIG

DB_PATH = LOCAL_CONFIG.db_path


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


def test_wojewodztwodle_relative_directions():
    from wojewodztwodle.utils import LOCAL_CONFIG as WOJ_CONFIG
    from local_kb_question import analyze_question, execute_plan

    p = analyze_question("Czy województwo leży na zachód od Mazowsza?", WOJ_CONFIG, use_cache=False)
    assert p.valid is True and p.supported is True
    ans = execute_plan(WOJ_CONFIG, "śląskie", p)
    assert ans.answer is True
    assert "Śląskie leży na długości geograficznej" in ans.explanation


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


def test_powiat_health_resorts():
    from local_kb_question import analyze_question, execute_plan

    p_spa = analyze_question("Czy w powiecie znajduje się uzdrowisko?", LOCAL_CONFIG, use_cache=False)
    assert p_spa.valid is True and p_spa.supported is True
    assert execute_plan(LOCAL_CONFIG, "Powiat aleksandrowski", p_spa).answer is True  # Ciechocinek
    assert execute_plan(LOCAL_CONFIG, "Powiat kołobrzeski", p_spa).answer is True     # Kołobrzeg
    assert execute_plan(LOCAL_CONFIG, "Powiat nowosądecki", p_spa).answer is True     # Krynica-Zdrój
    assert execute_plan(LOCAL_CONFIG, "Sopot", p_spa).answer is True                  # Sopot
    assert execute_plan(LOCAL_CONFIG, "Powiat pińczowski", p_spa).answer is False
