PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS us_state_major_highways;
DROP TABLE IF EXISTS us_state_regional_labels;
DROP TABLE IF EXISTS us_state_mountain_ranges;
DROP TABLE IF EXISTS us_state_major_rivers;
DROP TABLE IF EXISTS us_state_water_access;
DROP TABLE IF EXISTS us_state_borders_countries;
DROP TABLE IF EXISTS us_state_borders_states;
DROP TABLE IF EXISTS us_states;

CREATE TABLE us_states (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    division TEXT NOT NULL,
    population INTEGER,
    area_sq_mi REAL,
    latitude REAL,
    longitude REAL,
    is_coastal INTEGER NOT NULL DEFAULT 0,
    admission_year INTEGER,
    admission_order INTEGER,
    nickname TEXT,
    civil_war_side TEXT,
    md_file TEXT
);

CREATE TABLE us_state_borders_states (
    state_id INTEGER NOT NULL,
    border_state_name TEXT NOT NULL,
    border_state_code TEXT,
    PRIMARY KEY (state_id, border_state_name),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_borders_countries (
    state_id INTEGER NOT NULL,
    country_name TEXT NOT NULL,
    PRIMARY KEY (state_id, country_name),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_water_access (
    state_id INTEGER NOT NULL,
    water_body TEXT NOT NULL,
    PRIMARY KEY (state_id, water_body),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_major_rivers (
    state_id INTEGER NOT NULL,
    river_name TEXT NOT NULL,
    PRIMARY KEY (state_id, river_name),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_mountain_ranges (
    state_id INTEGER NOT NULL,
    range_name TEXT NOT NULL,
    PRIMARY KEY (state_id, range_name),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_major_highways (
    state_id INTEGER NOT NULL,
    highway_name TEXT NOT NULL,
    PRIMARY KEY (state_id, highway_name),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE TABLE us_state_regional_labels (
    state_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (state_id, label),
    FOREIGN KEY (state_id) REFERENCES us_states(id) ON DELETE CASCADE
);

CREATE INDEX idx_us_state_region ON us_states(region);
CREATE INDEX idx_us_state_division ON us_states(division);
CREATE INDEX idx_us_state_population ON us_states(population);
CREATE INDEX idx_us_state_area ON us_states(area_sq_mi);
CREATE INDEX idx_us_state_admission_year ON us_states(admission_year);
CREATE INDEX idx_us_state_admission_order ON us_states(admission_order);
CREATE INDEX idx_us_state_civil_war_side ON us_states(civil_war_side);
CREATE INDEX idx_us_state_border_state ON us_state_borders_states(border_state_name);
CREATE INDEX idx_us_state_border_country ON us_state_borders_countries(country_name);
CREATE INDEX idx_us_state_water ON us_state_water_access(water_body);
CREATE INDEX idx_us_state_river ON us_state_major_rivers(river_name);
CREATE INDEX idx_us_state_mountain ON us_state_mountain_ranges(range_name);
CREATE INDEX idx_us_state_highway ON us_state_major_highways(highway_name);
CREATE INDEX idx_us_state_regional_label ON us_state_regional_labels(label);
