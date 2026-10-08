-- Offline browser-journey snapshot, deliberately not a complete knowledge base.
-- Reviewed 2026-10-07: stable names/ISO codes and continent membership only.
-- Geographic classification source: United Nations M49 standard country list,
-- https://unstats.un.org/unsd/methodology/m49/ (Europe: Poland, Germany, France,
-- Italy; Asia: Japan; South America: Brazil; Africa: Egypt).
-- Formal names: UN terminology database, https://unterm.un.org/ (English).
-- France's Europe membership does not assert its entire territory is in Europe.
-- No temporal officeholders, memberships, rankings, or invented absent facts.
-- PostgreSQL identities and dropdown IDs are derived from these rows, not mocks.
-- The canonical countrydle/local_kb/schema.sql supplies the production schema.
-- Explore's post-game endpoint also reads the optional enrichment tables.
-- Their production schema is defined in populate_country_flags_and_history.py.
-- Empty tables mean this fixture supplies no flag/history evidence.
CREATE TABLE IF NOT EXISTS country_flag_colors (
    country_id INTEGER NOT NULL REFERENCES countries(id),
    color TEXT NOT NULL,
    PRIMARY KEY (country_id, color)
);
CREATE TABLE IF NOT EXISTS country_flag_symbols (
    country_id INTEGER NOT NULL REFERENCES countries(id),
    symbol TEXT NOT NULL,
    PRIMARY KEY (country_id, symbol)
);
CREATE TABLE IF NOT EXISTS country_historical_unions (
    country_id INTEGER NOT NULL REFERENCES countries(id),
    union_name TEXT NOT NULL,
    PRIMARY KEY (country_id, union_name)
);


INSERT INTO countries (id, app_country_name, official_name, cca2, cca3, source, updated_at) VALUES
    (1, 'Poland', 'Republic of Poland', 'PL', 'POL', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (2, 'Germany', 'Federal Republic of Germany', 'DE', 'DEU', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (3, 'France', 'French Republic', 'FR', 'FRA', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (4, 'Italy', 'Italian Republic', 'IT', 'ITA', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (5, 'Japan', 'Japan', 'JP', 'JPN', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (6, 'Brazil', 'Federative Republic of Brazil', 'BR', 'BRA', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z'),
    (7, 'Egypt', 'Arab Republic of Egypt', 'EG', 'EGY', 'e2e-reviewed-un-m49-unterm', '2026-10-07T00:00:00Z');

INSERT INTO country_continents (country_id, continent) VALUES
    (1, 'Europe'), (2, 'Europe'), (3, 'Europe'), (4, 'Europe'),
    (5, 'Asia'), (6, 'South America'), (7, 'Africa');
