DROP TABLE IF EXISTS voivodeship_historical_regions;
DROP TABLE IF EXISTS voivodeship_landform_regions;
DROP TABLE IF EXISTS voivodeship_regional_labels;
DROP TABLE IF EXISTS voivodeship_mountain_ranges;
DROP TABLE IF EXISTS voivodeship_major_rivers;
DROP TABLE IF EXISTS voivodeship_water_access;
DROP TABLE IF EXISTS voivodeship_borders_countries;
DROP TABLE IF EXISTS voivodeship_borders_voivodeships;
DROP TABLE IF EXISTS voivodeships;

CREATE TABLE voivodeships (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    seat TEXT NOT NULL,
    teryt TEXT NOT NULL UNIQUE,
    macroregion TEXT NOT NULL,
    population INTEGER NOT NULL,
    area_km2 REAL NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    is_coastal INTEGER NOT NULL DEFAULT 0,
    urbanization_percent REAL,
    powiat_count INTEGER,
    city_count INTEGER,
    city_count_with_powiat_rights INTEGER,
    md_file TEXT NOT NULL
);

CREATE TABLE voivodeship_borders_voivodeships (
    voivodeship_id INTEGER NOT NULL,
    border_voivodeship_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, border_voivodeship_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_borders_countries (
    voivodeship_id INTEGER NOT NULL,
    country_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, country_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_water_access (
    voivodeship_id INTEGER NOT NULL,
    water_body TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, water_body),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_major_rivers (
    voivodeship_id INTEGER NOT NULL,
    river_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, river_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_mountain_ranges (
    voivodeship_id INTEGER NOT NULL,
    range_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, range_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_historical_regions (
    voivodeship_id INTEGER NOT NULL,
    region_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, region_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_landform_regions (
    voivodeship_id INTEGER NOT NULL,
    region_name TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, region_name),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE TABLE voivodeship_regional_labels (
    voivodeship_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (voivodeship_id, label),
    FOREIGN KEY (voivodeship_id) REFERENCES voivodeships(id) ON DELETE CASCADE
);

CREATE INDEX idx_voivodeship_name ON voivodeships(name);
CREATE INDEX idx_voivodeship_seat ON voivodeships(seat);
CREATE INDEX idx_voivodeship_macroregion ON voivodeships(macroregion);
CREATE INDEX idx_voivodeship_population ON voivodeships(population);
CREATE INDEX idx_voivodeship_area ON voivodeships(area_km2);
CREATE INDEX idx_voivodeship_urbanization ON voivodeships(urbanization_percent);
CREATE INDEX idx_voivodeship_border ON voivodeship_borders_voivodeships(border_voivodeship_name);
CREATE INDEX idx_voivodeship_country_border ON voivodeship_borders_countries(country_name);
CREATE INDEX idx_voivodeship_water ON voivodeship_water_access(water_body);
CREATE INDEX idx_voivodeship_river ON voivodeship_major_rivers(river_name);
CREATE INDEX idx_voivodeship_mountain ON voivodeship_mountain_ranges(range_name);
CREATE INDEX idx_voivodeship_historical_region ON voivodeship_historical_regions(region_name);
CREATE INDEX idx_voivodeship_landform_region ON voivodeship_landform_regions(region_name);
CREATE INDEX idx_voivodeship_regional_label ON voivodeship_regional_labels(label);
