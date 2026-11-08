import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from schemas.blog import (
    CandidateFunnelStep,
    DeductionAnalysis,
    WrongGuessComparison,
    WrongGuessStat,
)


@pytest.fixture
def sample_facts_db(tmp_path):
    """Create a minimal, representative SQLite database matching country_facts schema."""
    db_path = tmp_path / "country_facts.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE countries (
            id INTEGER PRIMARY KEY,
            app_country_name TEXT UNIQUE NOT NULL,
            official_name TEXT,
            cca2 TEXT,
            cca3 TEXT,
            region TEXT,
            subregion TEXT,
            capital TEXT,
            population INTEGER,
            area_km2 REAL
        );
        CREATE TABLE country_continents (
            id INTEGER PRIMARY KEY,
            country_id INTEGER,
            continent TEXT
        );
        CREATE TABLE country_borders (
            id INTEGER PRIMARY KEY,
            country_id INTEGER,
            border_country_name TEXT
        );
        CREATE TABLE country_water_access (
            id INTEGER PRIMARY KEY,
            country_id INTEGER,
            water_body TEXT
        );
        CREATE TABLE country_subregions (
            id INTEGER PRIMARY KEY,
            country_id INTEGER,
            subregion_name TEXT
        );
    """)

    # Populate 5 countries: Poland (coastal, Europe), Czechia (landlocked, Europe),
    # Germany (coastal, Europe), Zambia (landlocked, Africa), Israel (ineligible)
    countries = [
        (1, "Poland", "Republic of Poland", "PL", "POL", "Europe", "Central Europe", "Warsaw", 37392000, 312679.0),
        (2, "Czechia", "Czech Republic", "CZ", "CZE", "Europe", "Central Europe", "Prague", 10700000, 78866.0),
        (3, "Germany", "Federal Republic of Germany", "DE", "DEU", "Europe", "Western Europe", "Berlin", 83200000, 357114.0),
        (4, "Zambia", "Republic of Zambia", "ZM", "ZMB", "Africa", "Eastern Africa", "Lusaka", 19610769, 752618.0),
        (5, "Israel", "State of Israel", "IL", "ISR", "Asia", "Western Asia", "Jerusalem", 9000000, 20770.0),
    ]
    conn.executemany("INSERT INTO countries VALUES (?,?,?,?,?,?,?,?,?,?)", countries)

    continents = [
        (1, 1, "Europe"),
        (2, 2, "Europe"),
        (3, 3, "Europe"),
        (4, 4, "Africa"),
        (5, 5, "Asia"),
    ]
    conn.executemany("INSERT INTO country_continents VALUES (?,?,?)", continents)

    borders = [
        (1, 1, "Germany"),
        (2, 1, "Czechia"),
        (3, 2, "Poland"),
        (4, 2, "Germany"),
        (5, 3, "Poland"),
        (6, 3, "Czechia"),
    ]
    conn.executemany("INSERT INTO country_borders VALUES (?,?,?)", borders)

    water = [
        (1, 1, "Baltic Sea"),
        (2, 3, "Baltic Sea"),
        (3, 3, "North Sea"),
        (4, 5, "Mediterranean Sea"),
    ]
    conn.executemany("INSERT INTO country_water_access VALUES (?,?,?)", water)
    subregions = [
        (1, 1, "Central Europe"),
        (2, 2, "Central Europe"),
        (3, 3, "Western Europe"),
        (4, 4, "Eastern Africa"),
        (5, 5, "Western Asia"),
    ]
    conn.executemany("INSERT INTO country_subregions VALUES (?,?,?)", subregions)

    conn.commit()
    conn.close()
    return db_path


def test_candidate_funnel_monotonic_narrowing_and_eligibility(sample_facts_db):
    from blog.deduction import compute_candidate_funnel

    funnel = compute_candidate_funnel(sample_facts_db, "Poland")
    assert len(funnel) >= 3

    # Invariant 1: Initial pool contains only eligible playable countries (4 out of 5; Israel excluded)
    assert funnel[0].remaining_count == 4
    assert all("israel" not in cand.lower() for cand in funnel[0].sample_candidates)

    # Invariant 2: Monotonic narrowing (remaining_count non-increasing)
    counts = [step.remaining_count for step in funnel]
    assert all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1))


def test_ambiguity_retention_when_candidates_indistinguishable(tmp_path):
    """Verify that when 2 countries share identical catalog traits, funnel does NOT fake remaining_count=1."""
    db_path = tmp_path / "ambiguous_facts.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE countries (
            id INTEGER PRIMARY KEY,
            app_country_name TEXT UNIQUE NOT NULL,
            official_name TEXT,
            cca2 TEXT,
            cca3 TEXT,
            region TEXT,
            subregion TEXT,
            capital TEXT,
            population INTEGER,
            area_km2 REAL
        );
        CREATE TABLE country_continents (id INTEGER PRIMARY KEY, country_id INTEGER, continent TEXT);
        CREATE TABLE country_borders (id INTEGER PRIMARY KEY, country_id INTEGER, border_country_name TEXT);
        CREATE TABLE country_water_access (id INTEGER PRIMARY KEY, country_id INTEGER, water_body TEXT);
        CREATE TABLE country_subregions (id INTEGER PRIMARY KEY, country_id INTEGER, subregion_name TEXT);
    """)

    # Two identical island states with no borders and same Pacific Ocean access
    conn.executemany("INSERT INTO countries VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, "IslandAlpha", "Alpha", "IA", "IAA", "Oceania", "Micronesia", "AlphaCity", 100000, 500.0),
        (2, "IslandBeta", "Beta", "IB", "IBB", "Oceania", "Micronesia", "BetaCity", 120000, 600.0),
    ])
    conn.executemany("INSERT INTO country_continents VALUES (?,?,?)", [
        (1, 1, "Oceania"),
        (2, 2, "Oceania"),
    ])
    conn.executemany("INSERT INTO country_water_access VALUES (?,?,?)", [
        (1, 1, "Pacific Ocean"),
        (2, 2, "Pacific Ocean"),
    ])
    conn.commit()
    conn.executemany("INSERT INTO country_subregions VALUES (?,?,?)", [
        (1, 1, "Micronesia"),
        (2, 2, "Micronesia"),
    ])
    conn.close()

    from blog.deduction import compute_candidate_funnel

    funnel = compute_candidate_funnel(db_path, "IslandAlpha")
    assert len(funnel) > 0
    # The final step must be 2, truthfully reflecting ambiguity without forcing remaining_count=1
    assert funnel[-1].remaining_count == 2


def test_caspian_sea_littoral_states_are_not_marine_coastal(tmp_path):
    """Verify that littoral states of endorheic inland waters (Caspian Sea) are not treated as marine coastal nations."""
    db_path = tmp_path / "caspian_facts.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE countries (
            id INTEGER PRIMARY KEY,
            app_country_name TEXT UNIQUE NOT NULL,
            official_name TEXT,
            cca2 TEXT,
            cca3 TEXT,
            region TEXT,
            subregion TEXT,
            capital TEXT,
            population INTEGER,
            area_km2 REAL
        );
        CREATE TABLE country_continents (id INTEGER PRIMARY KEY, country_id INTEGER, continent TEXT);
        CREATE TABLE country_borders (id INTEGER PRIMARY KEY, country_id INTEGER, border_country_name TEXT);
        CREATE TABLE country_water_access (id INTEGER PRIMARY KEY, country_id INTEGER, water_body TEXT);
        CREATE TABLE country_subregions (id INTEGER PRIMARY KEY, country_id INTEGER, subregion_name TEXT);
    """)

    # Kazakhstan (Caspian Sea only) vs Japan (Pacific Ocean)
    conn.executemany("INSERT INTO countries VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, "Kazakhstan", "Republic of Kazakhstan", "KZ", "KAZ", "Asia", "Central Asia", "Astana", 19000000, 2724900.0),
        (2, "Japan", "Japan", "JP", "JPN", "Asia", "Eastern Asia", "Tokyo", 125000000, 377975.0),
    ])
    conn.executemany("INSERT INTO country_continents VALUES (?,?,?)", [
        (1, 1, "Asia"),
        (2, 2, "Asia"),
    ])
    conn.executemany("INSERT INTO country_water_access VALUES (?,?,?)", [
        (1, 1, "Caspian Sea"),
        (2, 2, "Pacific Ocean"),
    ])
    conn.commit()
    conn.executemany("INSERT INTO country_subregions VALUES (?,?,?)", [
        (1, 1, "Central Asia"),
        (2, 2, "Eastern Asia"),
    ])
    conn.close()

    from blog.deduction import compute_candidate_funnel, _load_catalog

    conn = sqlite3.connect(db_path)
    catalog = _load_catalog(conn)
    conn.close()

    kaz = catalog[1]
    assert kaz.marine_status == "inland_only"

    jpn = catalog[2]
    assert jpn.marine_status == "coastal"

    funnel = compute_candidate_funnel(catalog, "Kazakhstan")
    inland_step = next(s for s in funnel if "Inland Water Only" in s.criterion)
    assert "Caspian Sea" in inland_step.criterion


def test_unknown_continent_and_borders_are_conservatively_retained(tmp_path):
    """Verify that countries with unknown continent or unrecorded borders are retained during filtering."""
    db_path = tmp_path / "unknowns_facts.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE countries (
            id INTEGER PRIMARY KEY,
            app_country_name TEXT UNIQUE NOT NULL,
            official_name TEXT,
            cca2 TEXT,
            cca3 TEXT,
            region TEXT,
            subregion TEXT,
            capital TEXT,
            population INTEGER,
            area_km2 REAL
        );
        CREATE TABLE country_continents (id INTEGER PRIMARY KEY, country_id INTEGER, continent TEXT);
        CREATE TABLE country_borders (id INTEGER PRIMARY KEY, country_id INTEGER, border_country_name TEXT);
        CREATE TABLE country_water_access (id INTEGER PRIMARY KEY, country_id INTEGER, water_body TEXT);
        CREATE TABLE country_subregions (id INTEGER PRIMARY KEY, country_id INTEGER, subregion_name TEXT);
    """)

    # Country 1: Known in Europe, borders Germany, has water
    # Country 2: Unknown continent (empty), unrecorded borders (empty), has water
    # Country 3: Known in Asia, borders China
    conn.executemany("INSERT INTO countries VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, "KnownEurope", "Known", "KE", "KEE", "Europe", "Central Europe", "CapitalA", 10000000, 100000.0),
        (2, "MysteryLand", "Mystery", "ML", "MLL", "Europe", None, "CapitalM", 5000000, 50000.0),
        (3, "KnownAsia", "AsiaLand", "KA", "KAA", "Asia", "Eastern Asia", "CapitalB", 20000000, 200000.0),
    ])
    conn.executemany("INSERT INTO country_continents VALUES (?,?,?)", [
        (1, 1, "Europe"),
        (2, 3, "Asia"),
    ])
    conn.executemany("INSERT INTO country_borders VALUES (?,?,?)", [
        (1, 1, "Germany"),
        (2, 3, "China"),
    ])
    conn.executemany("INSERT INTO country_water_access VALUES (?,?,?)", [
        (1, 1, "Baltic Sea"),
        (2, 2, "Baltic Sea"),
        (3, 3, "Yellow Sea"),
    ])
    conn.executemany("INSERT INTO country_subregions VALUES (?,?,?)", [
        (1, 1, "Central Europe"),
        (2, 3, "Eastern Asia"),
    ])
    conn.commit()
    conn.close()

    from blog.deduction import compute_candidate_funnel

    funnel = compute_candidate_funnel(db_path, "KnownEurope")
    assert len(funnel) > 0

    # Step 1 (Continent: Europe): MysteryLand must be retained because its continent is unknown!
    cont_step = next(s for s in funnel if "Continent: Europe" in s.criterion)
    assert cont_step.remaining_count == 2  # KnownEurope + MysteryLand (KnownAsia eliminated)

    # Final step cannot claim uniqueness because MysteryLand is still a candidate!
    assert funnel[-1].remaining_count == 2


def test_candidate_funnel_handles_unknown_country(sample_facts_db):
    from blog.deduction import compute_candidate_funnel

    funnel = compute_candidate_funnel(sample_facts_db, "NonExistentCountry")
    assert isinstance(funnel, list)
    assert len(funnel) == 0


def test_wrong_guess_comparisons_with_known_and_unknown_guesses(sample_facts_db):
    from blog.deduction import compute_wrong_guess_comparisons

    wrong_guesses = [
        WrongGuessStat(guess="Czechia", count=25),
        WrongGuessStat(guess="Atlantis", count=3),
    ]
    comparisons = compute_wrong_guess_comparisons(sample_facts_db, "Poland", wrong_guesses)
    assert len(comparisons) == 2

    # Czechia comparison
    cze_cmp = comparisons[0]
    assert cze_cmp.guess == "Czechia"
    assert cze_cmp.count == 25
    assert cze_cmp.target_facts.get("capital") == "Warsaw"
    assert cze_cmp.guess_facts.get("capital") == "Prague"

    # Atlantis comparison (unknown entity in catalog)
    atl_cmp = comparisons[1]
    assert atl_cmp.guess == "Atlantis"
    assert atl_cmp.count == 3
    assert any("unknown" in d.lower() or "not found" in d.lower() for d in atl_cmp.differences)
    assert atl_cmp.guess_facts.get("capital") == "Unknown"


def test_deduction_analysis_gate_for_past_day_vs_preview(sample_facts_db):
    from blog.deduction import get_deduction_analysis

    wrong_guesses = [WrongGuessStat(guess="Czechia", count=10)]

    # Current or future day: MUST be suppressed (no leaks)
    preview = get_deduction_analysis(sample_facts_db, "Poland", wrong_guesses, is_past_day=False)
    assert isinstance(preview, DeductionAnalysis)
    assert preview.has_analysis is False
    assert preview.candidate_funnel == []
    assert preview.wrong_guess_comparisons == []

    # Past day: MUST be computed with explicit provenance and illustrative disclaimer
    past = get_deduction_analysis(sample_facts_db, "Poland", wrong_guesses, is_past_day=True)
    assert past.has_analysis is True
    assert len(past.candidate_funnel) > 0
    assert len(past.wrong_guess_comparisons) == 1


def test_malformed_catalog_schema_raises_error(tmp_path):
    """Verify that missing catalog tables raise OperationalError without silent suppression."""
    db_path = tmp_path / "broken.sqlite"
    conn = sqlite3.connect(db_path)
    # Create countries table without country_continents table
    conn.execute("CREATE TABLE countries (id INTEGER PRIMARY KEY, app_country_name TEXT, official_name TEXT, cca2 TEXT, cca3 TEXT, region TEXT, subregion TEXT, capital TEXT, population INT, area_km2 REAL)")
    conn.execute("INSERT INTO countries VALUES (1, 'BrokenLand', 'Broken', 'BL', 'BLL', 'Europe', 'Central', 'Cap', 10, 10)")
    conn.commit()

    from blog.deduction import _load_catalog
    with pytest.raises(sqlite3.OperationalError):
        _load_catalog(conn)
    conn.close()


def test_mixed_border_aliases_are_canonicalized_and_not_falsely_distinguished(tmp_path):
    """Verify that mixed border names (e.g. Czechia vs Czech Republic) canonicalize to the same country."""
    db_path = tmp_path / "alias_facts.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE countries (
            id INTEGER PRIMARY KEY, app_country_name TEXT UNIQUE NOT NULL, official_name TEXT,
            cca2 TEXT, cca3 TEXT, region TEXT, subregion TEXT, capital TEXT, population INTEGER, area_km2 REAL
        );
        CREATE TABLE country_continents (id INTEGER PRIMARY KEY, country_id INTEGER, continent TEXT);
        CREATE TABLE country_borders (id INTEGER PRIMARY KEY, country_id INTEGER, border_country_name TEXT);
        CREATE TABLE country_water_access (id INTEGER PRIMARY KEY, country_id INTEGER, water_body TEXT);
        CREATE TABLE country_subregions (id INTEGER PRIMARY KEY, country_id INTEGER, subregion_name TEXT);
    """)

    # Target is Poland (id 1).
    # Czech Republic is canonical in catalog (id 2).
    # CandidateA (id 3) lists border as 'Czechia'
    # CandidateB (id 4) lists border as 'Czech Republic'
    conn.executemany("INSERT INTO countries VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, "Poland", "Republic of Poland", "PL", "POL", "Europe", "Central Europe", "Warsaw", 37392000, 312679.0),
        (2, "Czech Republic", "Czech Republic", "CZ", "CZE", "Europe", "Central Europe", "Prague", 10700000, 78866.0),
        (3, "CandidateA", "Candidate A", "CA", "CAA", "Europe", "Central Europe", "CapA", 5000000, 50000.0),
        (4, "CandidateB", "Candidate B", "CB", "CBB", "Europe", "Central Europe", "CapB", 6000000, 60000.0),
        (5, "CandidateC", "Candidate C", "CC", "CCC", "Europe", "Central Europe", "CapC", 7000000, 70000.0),
    ])
    for cid in (1, 2, 3, 4, 5):
        conn.execute("INSERT INTO country_continents VALUES (?,?,?)", (cid, cid, "Europe"))
        conn.execute("INSERT INTO country_water_access VALUES (?,?,?)", (cid, cid, "Baltic Sea"))
        conn.execute("INSERT INTO country_subregions VALUES (?,?,?)", (cid, cid, "Central Europe"))

    conn.executemany("INSERT INTO country_borders VALUES (?,?,?)", [
        (1, 1, "Czech Republic"),
        (2, 3, "Czechia"),
        (3, 4, "Czech Republic"),
        (4, 5, "Germany"),
        (5, 2, "Germany"),
    ])
    conn.commit()
    conn.close()

    from blog.deduction import compute_candidate_funnel, compute_wrong_guess_comparisons

    funnel = compute_candidate_funnel(db_path, "Poland")
    border_step = next((s for s in funnel if "Border Neighbor: Shares land border with Czech Republic" in s.criterion), None)
    assert border_step is not None
    # Both CandidateA and CandidateB are retained; CandidateC eliminated
    assert border_step.remaining_count == 3  # Poland + CandidateA + CandidateB

    # Guessing alias 'Czechia' must find catalog facts for Czech Republic, not Unknown
    comparisons = compute_wrong_guess_comparisons(db_path, "Poland", [WrongGuessStat(guess="Czechia", count=10)])
    assert len(comparisons) == 1
    cze_cmp = comparisons[0]
    assert cze_cmp.guess == "Czech Republic"
    assert cze_cmp.guess_facts.get("capital") == "Prague"
    assert not any("unknown entity" in d.lower() for d in cze_cmp.differences)

