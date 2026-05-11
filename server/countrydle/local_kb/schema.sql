PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS countries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_country_name TEXT NOT NULL UNIQUE,
    official_name TEXT,
    cca2 TEXT,
    cca3 TEXT UNIQUE,
    region TEXT,
    subregion TEXT,
    capital TEXT,
    population INTEGER,
    area_km2 REAL,
    latitude REAL,
    longitude REAL,
    is_island INTEGER,
    driving_side TEXT,
    government_type TEXT,
    dominant_religion TEXT,
    source TEXT NOT NULL DEFAULT 'restcountries',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS country_continents (
    country_id INTEGER NOT NULL,
    continent TEXT NOT NULL,
    PRIMARY KEY (country_id, continent),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_regions (
    country_id INTEGER NOT NULL,
    region_name TEXT NOT NULL,
    PRIMARY KEY (country_id, region_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_subregions (
    country_id INTEGER NOT NULL,
    subregion_name TEXT NOT NULL,
    PRIMARY KEY (country_id, subregion_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_borders (
    country_id INTEGER NOT NULL,
    border_country_name TEXT NOT NULL,
    border_cca3 TEXT,
    PRIMARY KEY (country_id, border_country_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_water_access (
    country_id INTEGER NOT NULL,
    water_body TEXT NOT NULL,
    PRIMARY KEY (country_id, water_body),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_currencies (
    country_id INTEGER NOT NULL,
    currency_code TEXT,
    currency_name TEXT NOT NULL,
    currency_symbol TEXT,
    PRIMARY KEY (country_id, currency_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_languages (
    country_id INTEGER NOT NULL,
    language_code TEXT,
    language_name TEXT NOT NULL,
    PRIMARY KEY (country_id, language_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_memberships (
    country_id INTEGER NOT NULL,
    organization TEXT NOT NULL,
    PRIMARY KEY (country_id, organization),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS country_major_rivers (
    country_id INTEGER NOT NULL,
    river_name TEXT NOT NULL,
    PRIMARY KEY (country_id, river_name),
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_countries_name ON countries(app_country_name);
CREATE INDEX IF NOT EXISTS idx_countries_cca3 ON countries(cca3);
CREATE INDEX IF NOT EXISTS idx_country_region ON country_regions(region_name);
CREATE INDEX IF NOT EXISTS idx_country_subregion ON country_subregions(subregion_name);
CREATE INDEX IF NOT EXISTS idx_borders_country ON country_borders(border_country_name);
CREATE INDEX IF NOT EXISTS idx_water_body ON country_water_access(water_body);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON country_memberships(organization);
