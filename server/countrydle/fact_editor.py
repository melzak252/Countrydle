"""Read and edit the Countrydle local SQLite knowledge base.

This module intentionally keeps the editor deterministic and small: it exposes
only the relations used by the local Countrydle answerer and writes directly to
``country_facts.sqlite``. Audit logging is handled by the API layer in
PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from countrydle.local_answering import DEFAULT_DB_PATH


@dataclass(frozen=True)
class ScalarRelation:
    relation: str
    column: str
    value_type: str = "text"


@dataclass(frozen=True)
class ListRelation:
    relation: str
    table: str
    value_column: str
    metadata_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactModeConfig:
    game_type: str
    db_path: Path
    entity_table: str
    name_column: str
    fk_column: str
    scalar_relations: dict[str, ScalarRelation]
    list_relations: dict[str, ListRelation]


SCALAR_RELATIONS: dict[str, ScalarRelation] = {
    "official_name": ScalarRelation("official_name", "official_name"),
    "cca2": ScalarRelation("cca2", "cca2"),
    "cca3": ScalarRelation("cca3", "cca3"),
    "region": ScalarRelation("region", "region"),
    "subregion": ScalarRelation("subregion", "subregion"),
    "capital": ScalarRelation("capital", "capital"),
    "population": ScalarRelation("population", "population", "integer"),
    "area_km2": ScalarRelation("area_km2", "area_km2", "float"),
    "latitude": ScalarRelation("latitude", "latitude", "float"),
    "longitude": ScalarRelation("longitude", "longitude", "float"),
    "is_island": ScalarRelation("is_island", "is_island", "boolean"),
    "driving_side": ScalarRelation("driving_side", "driving_side"),
    "government_type": ScalarRelation("government_type", "government_type"),
    "dominant_religion": ScalarRelation("dominant_religion", "dominant_religion"),
}


LIST_RELATIONS: dict[str, ListRelation] = {
    "continent": ListRelation("continent", "country_continents", "continent"),
    "region": ListRelation("region", "country_regions", "region_name"),
    "subregion": ListRelation("subregion", "country_subregions", "subregion_name"),
    "borders_country": ListRelation("borders_country", "country_borders", "border_country_name", ("border_cca3",)),
    "water_access": ListRelation("water_access", "country_water_access", "water_body"),
    "currency": ListRelation("currency", "country_currencies", "currency_name", ("currency_code", "currency_symbol")),
    "official_language": ListRelation("official_language", "country_languages", "language_name", ("language_code",)),
    "membership": ListRelation("membership", "country_memberships", "organization"),
    "major_rivers": ListRelation("major_rivers", "country_major_rivers", "river_name"),
}


def _typed_scalar_relations(mapping: dict[str, str]) -> dict[str, ScalarRelation]:
    typed: dict[str, ScalarRelation] = {}
    for relation, column in mapping.items():
        if relation == "name":
            continue
        value_type = "text"
        if relation in {
            "population",
            "admission_year",
            "admission_order",
            "gmina_count",
            "urban_gmina_count",
            "rural_gmina_count",
            "urban_rural_gmina_count",
            "powiat_count",
            "city_count",
            "city_count_with_powiat_rights",
        }:
            value_type = "integer"
        elif relation in {"area", "latitude", "longitude", "population_density", "urbanization"}:
            value_type = "float"
        elif relation.startswith("is_"):
            value_type = "boolean"
        typed[relation] = ScalarRelation(relation, column, value_type)
    return typed


ROOT_DIR = DEFAULT_DB_PATH.parents[1] if DEFAULT_DB_PATH.parent.name == "data" else DEFAULT_DB_PATH.parent


FACT_MODE_CONFIGS: dict[str, FactModeConfig] = {
    "countrydle": FactModeConfig(
        game_type="countrydle",
        db_path=DEFAULT_DB_PATH,
        entity_table="countries",
        name_column="app_country_name",
        fk_column="country_id",
        scalar_relations=SCALAR_RELATIONS,
        list_relations=LIST_RELATIONS,
    ),
    "powiatdle": FactModeConfig(
        game_type="powiatdle",
        db_path=ROOT_DIR / "data" / "powiat_facts.sqlite",
        entity_table="powiats",
        name_column="name",
        fk_column="powiat_id",
        scalar_relations=_typed_scalar_relations(
            {
                "voivodeship": "voivodeship",
                "is_city_county": "is_city_county",
                "seat": "seat",
                "population": "population",
                "area": "area_km2",
                "population_density": "population_density",
                "urbanization": "urbanization_percent",
                "gmina_count": "gmina_count",
                "urban_gmina_count": "urban_gmina_count",
                "rural_gmina_count": "rural_gmina_count",
                "urban_rural_gmina_count": "urban_rural_gmina_count",
            }
        ),
        list_relations={
            "borders_powiat": ListRelation("borders_powiat", "powiat_borders_powiats", "border_powiat_name"),
            "borders_voivodeship": ListRelation("borders_voivodeship", "powiat_borders_voivodeships", "voivodeship"),
            "borders_country": ListRelation("borders_country", "powiat_borders_countries", "country_name"),
            "registration_plates": ListRelation("registration_plates", "powiat_registration_plates", "plate_code"),
            "major_rivers": ListRelation("major_rivers", "powiat_major_rivers", "river_name"),
            "major_roads": ListRelation("major_roads", "powiat_major_roads", "road_name"),
            "landform_regions": ListRelation("landform_regions", "powiat_landform_regions", "region_name"),
            "regional_labels": ListRelation("regional_labels", "powiat_landform_regions", "region_name"),
        },
    ),
    "us_statedle": FactModeConfig(
        game_type="us_statedle",
        db_path=ROOT_DIR / "data" / "us_state_facts.sqlite",
        entity_table="us_states",
        name_column="name",
        fk_column="state_id",
        scalar_relations=_typed_scalar_relations(
            {
                "region": "region",
                "division": "division",
                "is_coastal": "is_coastal",
                "population": "population",
                "area": "area_sq_mi",
                "latitude": "latitude",
                "longitude": "longitude",
                "admission_year": "admission_year",
                "admission_order": "admission_order",
                "nickname": "nickname",
                "civil_war_side": "civil_war_side",
            }
        ),
        list_relations={
            "borders_state": ListRelation("borders_state", "us_state_borders_states", "border_state_name", ("border_state_code",)),
            "borders_country": ListRelation("borders_country", "us_state_borders_countries", "country_name"),
            "water_access": ListRelation("water_access", "us_state_water_access", "water_body"),
            "major_rivers": ListRelation("major_rivers", "us_state_major_rivers", "river_name"),
            "mountain_ranges": ListRelation("mountain_ranges", "us_state_mountain_ranges", "range_name"),
            "major_highways": ListRelation("major_highways", "us_state_major_highways", "highway_name"),
            "regional_labels": ListRelation("regional_labels", "us_state_regional_labels", "label"),
        },
    ),
    "wojewodztwodle": FactModeConfig(
        game_type="wojewodztwodle",
        db_path=ROOT_DIR / "data" / "voivodeship_facts.sqlite",
        entity_table="voivodeships",
        name_column="name",
        fk_column="voivodeship_id",
        scalar_relations=_typed_scalar_relations(
            {
                "seat": "seat",
                "macroregion": "macroregion",
                "is_coastal": "is_coastal",
                "population": "population",
                "area": "area_km2",
                "latitude": "latitude",
                "longitude": "longitude",
                "urbanization": "urbanization_percent",
                "powiat_count": "powiat_count",
                "city_count": "city_count",
                "city_count_with_powiat_rights": "city_count_with_powiat_rights",
            }
        ),
        list_relations={
            "borders_voivodeship": ListRelation("borders_voivodeship", "voivodeship_borders_voivodeships", "border_voivodeship_name"),
            "borders_country": ListRelation("borders_country", "voivodeship_borders_countries", "country_name"),
            "water_access": ListRelation("water_access", "voivodeship_water_access", "water_body"),
            "major_rivers": ListRelation("major_rivers", "voivodeship_major_rivers", "river_name"),
            "mountain_ranges": ListRelation("mountain_ranges", "voivodeship_mountain_ranges", "range_name"),
            "historical_region": ListRelation("historical_region", "voivodeship_historical_regions", "region_name"),
            "landform_regions": ListRelation("landform_regions", "voivodeship_landform_regions", "region_name"),
            "regional_labels": ListRelation("regional_labels", "voivodeship_regional_labels", "label"),
        },
    ),
}


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DEFAULT_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_fact_mode_config(game_type: str) -> FactModeConfig:
    config = FACT_MODE_CONFIGS.get(game_type)
    if config is None:
        raise KeyError(f"Unsupported local facts game type: {game_type}")
    return config


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _convert_scalar_value(value: Any, value_type: str):
    if value is None or value == "":
        return None
    if value_type == "integer":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "boolean":
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return 1 if value else 0
        lowered = str(value).strip().lower()
        if lowered in {"1", "true", "yes", "y", "tak"}:
            return 1
        if lowered in {"0", "false", "no", "n", "nie"}:
            return 0
        raise ValueError("Boolean value must be true/false")
    return _normalize_text(str(value))


def find_country_fact_id(country_name: str, db_path: Path | str | None = None) -> int:
    wanted = _normalize_text(country_name).lower()
    with _connect(db_path) as conn:
        direct = conn.execute(
            "SELECT id FROM countries WHERE lower(app_country_name)=lower(?)",
            (country_name,),
        ).fetchone()
        if direct is not None:
            return direct["id"]
        for row in conn.execute("SELECT id, app_country_name FROM countries"):
            if _normalize_text(row["app_country_name"]).lower() == wanted:
                return row["id"]
    raise KeyError(f"Country facts not found for name={country_name}")


def find_entity_fact_id(config: FactModeConfig, entity_name: str) -> int:
    wanted = _normalize_text(entity_name).lower()
    with _connect(config.db_path) as conn:
        direct = conn.execute(
            f"SELECT id FROM {config.entity_table} WHERE lower({config.name_column})=lower(?)",
            (entity_name,),
        ).fetchone()
        if direct is not None:
            return direct["id"]
        for row in conn.execute(f"SELECT id, {config.name_column} FROM {config.entity_table}"):
            if _normalize_text(row[config.name_column]).lower() == wanted:
                return row["id"]
    raise KeyError(f"Facts not found for name={entity_name}")


def get_local_facts(game_type: str, entity_id: int | None = None, entity_name: str | None = None) -> dict[str, Any]:
    config = get_fact_mode_config(game_type)
    if entity_name:
        entity_id = find_entity_fact_id(config, entity_name)
    if entity_id is None:
        raise ValueError("entity_id or entity_name is required")
    with _connect(config.db_path) as conn:
        entity = conn.execute(f"SELECT * FROM {config.entity_table} WHERE id=?", (entity_id,)).fetchone()
        if entity is None:
            raise KeyError(f"Facts not found for id={entity_id}")
        scalars = [
            {
                "relation": relation.relation,
                "column": relation.column,
                "value_type": relation.value_type,
                "value": entity[relation.column],
            }
            for relation in config.scalar_relations.values()
        ]
        lists: list[dict[str, Any]] = []
        for relation in config.list_relations.values():
            columns = [relation.value_column, *relation.metadata_columns]
            rows = conn.execute(
                f"SELECT {', '.join(columns)} FROM {relation.table} WHERE {config.fk_column}=? ORDER BY {relation.value_column}",
                (entity_id,),
            ).fetchall()
            lists.append(
                {
                    "relation": relation.relation,
                    "table": relation.table,
                    "value_column": relation.value_column,
                    "metadata_columns": list(relation.metadata_columns),
                    "values": [
                        {
                            "value": row[relation.value_column],
                            "metadata": {column: row[column] for column in relation.metadata_columns},
                        }
                        for row in rows
                    ],
                }
            )
        return {
            "game_type": config.game_type,
            "entity": {
                "id": entity["id"],
                "name": entity[config.name_column],
            },
            "country": {
                "id": entity["id"],
                "name": entity[config.name_column],
                "official_name": entity["official_name"] if "official_name" in entity.keys() else None,
            },
            "scalar_facts": scalars,
            "list_facts": lists,
        }


def update_local_scalar_fact(game_type: str, entity_id: int, relation_name: str, value: Any) -> tuple[Any, Any, str]:
    config = get_fact_mode_config(game_type)
    relation = config.scalar_relations.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported scalar relation: {relation_name}")
    converted = _convert_scalar_value(value, relation.value_type)
    with _connect(config.db_path) as conn:
        row = conn.execute(f"SELECT {relation.column} FROM {config.entity_table} WHERE id=?", (entity_id,)).fetchone()
        if row is None:
            raise KeyError(f"Facts not found for id={entity_id}")
        old_value = row[relation.column]
        conn.execute(f"UPDATE {config.entity_table} SET {relation.column}=? WHERE id=?", (converted, entity_id))
        conn.commit()
    return old_value, converted, "update"


def add_local_list_fact(game_type: str, entity_id: int, relation_name: str, value: str, metadata: dict[str, Any] | None = None) -> tuple[None, str, str]:
    config = get_fact_mode_config(game_type)
    relation = config.list_relations.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported list relation: {relation_name}")
    clean_value = _normalize_text(value)
    if not clean_value:
        raise ValueError("Value cannot be empty")
    metadata = metadata or {}
    columns = [config.fk_column, relation.value_column, *relation.metadata_columns]
    values = [entity_id, clean_value, *[metadata.get(column) for column in relation.metadata_columns]]
    placeholders = ", ".join("?" for _ in columns)
    with _connect(config.db_path) as conn:
        conn.execute(f"SELECT 1 FROM {config.entity_table} WHERE id=?", (entity_id,)).fetchone() or (_ for _ in ()).throw(
            KeyError(f"Facts not found for id={entity_id}")
        )
        try:
            conn.execute(f"INSERT INTO {relation.table} ({', '.join(columns)}) VALUES ({placeholders})", values)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Value already exists for this relation: {clean_value}") from exc
    return None, clean_value, "add"


def delete_local_list_fact(game_type: str, entity_id: int, relation_name: str, value: str) -> tuple[str, None, str]:
    config = get_fact_mode_config(game_type)
    relation = config.list_relations.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported list relation: {relation_name}")
    clean_value = _normalize_text(value)
    with _connect(config.db_path) as conn:
        cursor = conn.execute(
            f"DELETE FROM {relation.table} WHERE {config.fk_column}=? AND {relation.value_column}=?",
            (entity_id, clean_value),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Value not found for this relation: {clean_value}")
        conn.commit()
    return clean_value, None, "delete"


def get_local_relation_storage(game_type: str, relation_name: str, *, list_relation: bool) -> tuple[str, str]:
    config = get_fact_mode_config(game_type)
    if list_relation:
        relation = config.list_relations[relation_name]
        return relation.table, relation.value_column
    relation = config.scalar_relations[relation_name]
    return config.entity_table, relation.column


def get_country_facts(country_id: int, db_path: Path | str | None = None) -> dict[str, Any]:
    with _connect(db_path) as conn:
        country = conn.execute("SELECT * FROM countries WHERE id=?", (country_id,)).fetchone()
        if country is None:
            raise KeyError(f"Country facts not found for id={country_id}")

        scalars = [
            {
                "relation": relation.relation,
                "column": relation.column,
                "value_type": relation.value_type,
                "value": country[relation.column],
            }
            for relation in SCALAR_RELATIONS.values()
        ]

        lists: list[dict[str, Any]] = []
        for relation in LIST_RELATIONS.values():
            columns = [relation.value_column, *relation.metadata_columns]
            rows = conn.execute(
                f"SELECT {', '.join(columns)} FROM {relation.table} WHERE country_id=? ORDER BY {relation.value_column}",
                (country_id,),
            ).fetchall()
            lists.append(
                {
                    "relation": relation.relation,
                    "table": relation.table,
                    "value_column": relation.value_column,
                    "metadata_columns": list(relation.metadata_columns),
                    "values": [
                        {
                            "value": row[relation.value_column],
                            "metadata": {column: row[column] for column in relation.metadata_columns},
                        }
                        for row in rows
                    ],
                }
            )

        return {
            "country": {
                "id": country["id"],
                "name": country["app_country_name"],
                "official_name": country["official_name"],
            },
            "scalar_facts": scalars,
            "list_facts": lists,
        }


def get_country_facts_by_name(country_name: str, db_path: Path | str | None = None) -> dict[str, Any]:
    return get_country_facts(find_country_fact_id(country_name, db_path=db_path), db_path=db_path)


def update_scalar_fact(country_id: int, relation_name: str, value: Any, db_path: Path | str | None = None) -> tuple[Any, Any, str]:
    relation = SCALAR_RELATIONS.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported scalar relation: {relation_name}")
    converted = _convert_scalar_value(value, relation.value_type)
    with _connect(db_path) as conn:
        row = conn.execute(f"SELECT {relation.column} FROM countries WHERE id=?", (country_id,)).fetchone()
        if row is None:
            raise KeyError(f"Country facts not found for id={country_id}")
        old_value = row[relation.column]
        conn.execute(
            f"UPDATE countries SET {relation.column}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (converted, country_id),
        )
        conn.commit()
    return old_value, converted, "update"


def add_list_fact(
    country_id: int,
    relation_name: str,
    value: str,
    metadata: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
) -> tuple[None, str, str]:
    relation = LIST_RELATIONS.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported list relation: {relation_name}")
    clean_value = _normalize_text(value)
    if not clean_value:
        raise ValueError("Value cannot be empty")
    metadata = metadata or {}
    columns = ["country_id", relation.value_column, *relation.metadata_columns]
    values = [country_id, clean_value, *[metadata.get(column) for column in relation.metadata_columns]]
    placeholders = ", ".join("?" for _ in columns)
    with _connect(db_path) as conn:
        conn.execute("SELECT 1 FROM countries WHERE id=?", (country_id,)).fetchone() or (_ for _ in ()).throw(
            KeyError(f"Country facts not found for id={country_id}")
        )
        try:
            conn.execute(
                f"INSERT INTO {relation.table} ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            conn.execute("UPDATE countries SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (country_id,))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Value already exists for this relation: {clean_value}") from exc
    return None, clean_value, "add"


def delete_list_fact(country_id: int, relation_name: str, value: str, db_path: Path | str | None = None) -> tuple[str, None, str]:
    relation = LIST_RELATIONS.get(relation_name)
    if relation is None:
        raise KeyError(f"Unsupported list relation: {relation_name}")
    clean_value = _normalize_text(value)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"DELETE FROM {relation.table} WHERE country_id=? AND {relation.value_column}=?",
            (country_id, clean_value),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Value not found for this relation: {clean_value}")
        conn.execute("UPDATE countries SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (country_id,))
        conn.commit()
    return clean_value, None, "delete"


def get_relation_storage(relation_name: str, *, list_relation: bool) -> tuple[str, str]:
    if list_relation:
        relation = LIST_RELATIONS[relation_name]
        return relation.table, relation.value_column
    relation = SCALAR_RELATIONS[relation_name]
    return "countries", relation.column
