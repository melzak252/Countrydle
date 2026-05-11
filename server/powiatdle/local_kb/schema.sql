DROP TABLE IF EXISTS powiat_landform_regions;
DROP TABLE IF EXISTS powiat_major_roads;
DROP TABLE IF EXISTS powiat_major_rivers;
DROP TABLE IF EXISTS powiat_registration_plates;
DROP TABLE IF EXISTS powiat_borders_countries;
DROP TABLE IF EXISTS powiat_borders_voivodeships;
DROP TABLE IF EXISTS powiat_borders_powiats;
DROP TABLE IF EXISTS powiats;

CREATE TABLE powiats (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    voivodeship TEXT NOT NULL,
    is_city_county INTEGER NOT NULL CHECK (is_city_county IN (0, 1)),
    seat TEXT,
    terc TEXT,
    population INTEGER,
    area_km2 REAL,
    population_density REAL,
    urbanization_percent REAL,
    gmina_count INTEGER,
    urban_gmina_count INTEGER,
    rural_gmina_count INTEGER,
    urban_rural_gmina_count INTEGER,
    md_file TEXT NOT NULL
);

CREATE TABLE powiat_borders_powiats (
    powiat_id INTEGER NOT NULL,
    border_powiat_name TEXT NOT NULL,
    PRIMARY KEY (powiat_id, border_powiat_name),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_borders_voivodeships (
    powiat_id INTEGER NOT NULL,
    voivodeship TEXT NOT NULL,
    PRIMARY KEY (powiat_id, voivodeship),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_borders_countries (
    powiat_id INTEGER NOT NULL,
    country_name TEXT NOT NULL,
    PRIMARY KEY (powiat_id, country_name),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_registration_plates (
    powiat_id INTEGER NOT NULL,
    plate_code TEXT NOT NULL,
    PRIMARY KEY (powiat_id, plate_code),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_major_rivers (
    powiat_id INTEGER NOT NULL,
    river_name TEXT NOT NULL,
    PRIMARY KEY (powiat_id, river_name),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_major_roads (
    powiat_id INTEGER NOT NULL,
    road_name TEXT NOT NULL,
    PRIMARY KEY (powiat_id, road_name),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE TABLE powiat_landform_regions (
    powiat_id INTEGER NOT NULL,
    region_name TEXT NOT NULL,
    PRIMARY KEY (powiat_id, region_name),
    FOREIGN KEY (powiat_id) REFERENCES powiats(id) ON DELETE CASCADE
);

CREATE INDEX idx_powiat_voivodeship ON powiats(voivodeship);
CREATE INDEX idx_powiat_city_county ON powiats(is_city_county);
CREATE INDEX idx_powiat_population ON powiats(population);
CREATE INDEX idx_powiat_area ON powiats(area_km2);
CREATE INDEX idx_powiat_density ON powiats(population_density);
CREATE INDEX idx_powiat_plate ON powiat_registration_plates(plate_code);
CREATE INDEX idx_powiat_border ON powiat_borders_powiats(border_powiat_name);
CREATE INDEX idx_powiat_border_voivodeship ON powiat_borders_voivodeships(voivodeship);
CREATE INDEX idx_powiat_border_country ON powiat_borders_countries(country_name);
CREATE INDEX idx_powiat_river ON powiat_major_rivers(river_name);
CREATE INDEX idx_powiat_road ON powiat_major_roads(road_name);
CREATE INDEX idx_powiat_landform ON powiat_landform_regions(region_name);
