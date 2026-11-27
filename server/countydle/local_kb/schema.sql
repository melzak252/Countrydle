DROP TABLE IF EXISTS english_county_regional_labels;
DROP TABLE IF EXISTS english_county_major_cities;
DROP TABLE IF EXISTS english_county_major_rivers;
DROP TABLE IF EXISTS english_county_water_access;
DROP TABLE IF EXISTS english_county_borders_countries;
DROP TABLE IF EXISTS english_county_borders_counties;
DROP TABLE IF EXISTS english_counties;

CREATE TABLE english_counties (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    county_town TEXT NOT NULL,
    region TEXT NOT NULL,
    is_coastal INTEGER NOT NULL DEFAULT 0,
    is_metropolitan INTEGER NOT NULL DEFAULT 0,
    population INTEGER NOT NULL,
    area_km2 REAL NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE english_county_borders_counties (
    county_id INTEGER NOT NULL,
    border_county_name TEXT NOT NULL,
    PRIMARY KEY (county_id, border_county_name),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE TABLE english_county_borders_countries (
    county_id INTEGER NOT NULL,
    country_name TEXT NOT NULL,
    PRIMARY KEY (county_id, country_name),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE TABLE english_county_water_access (
    county_id INTEGER NOT NULL,
    water_body TEXT NOT NULL,
    PRIMARY KEY (county_id, water_body),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE TABLE english_county_major_rivers (
    county_id INTEGER NOT NULL,
    river_name TEXT NOT NULL,
    PRIMARY KEY (county_id, river_name),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE TABLE english_county_major_cities (
    county_id INTEGER NOT NULL,
    city_name TEXT NOT NULL,
    PRIMARY KEY (county_id, city_name),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE TABLE english_county_regional_labels (
    county_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (county_id, label),
    FOREIGN KEY (county_id) REFERENCES english_counties(id) ON DELETE CASCADE
);

CREATE INDEX idx_english_county_name ON english_counties(name);
CREATE INDEX idx_english_county_town ON english_counties(county_town);
CREATE INDEX idx_english_county_region ON english_counties(region);
CREATE INDEX idx_english_county_population ON english_counties(population);
CREATE INDEX idx_english_county_area ON english_counties(area_km2);
CREATE INDEX idx_english_county_border ON english_county_borders_counties(border_county_name);
CREATE INDEX idx_english_county_country_border ON english_county_borders_countries(country_name);
CREATE INDEX idx_english_county_water ON english_county_water_access(water_body);
CREATE INDEX idx_english_county_river ON english_county_major_rivers(river_name);
CREATE INDEX idx_english_county_city ON english_county_major_cities(city_name);
CREATE INDEX idx_english_county_regional_label ON english_county_regional_labels(label);
