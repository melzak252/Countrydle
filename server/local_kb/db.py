"""SQLite entity loading and relation reference resolution for local KB modes."""

from __future__ import annotations

import sqlite3
from typing import Any

from voivodeship_names import resolve_voivodeship_name

from .aliases import _resolve_english_county_alias, norm
from .models import (
    LocalModeConfig,
    _VOIVODESHIP_DB_PATH,
    _VOIVODESHIP_LIST_QUERIES,
    _VOIVODESHIP_SCALAR_RELATIONS,
    _safe_identifier,
)


def _get_parent_voivodeship_relation(row: sqlite3.Row, relation: str) -> Any:
    if "voivodeship" not in row.keys() or not row["voivodeship"] or not _VOIVODESHIP_DB_PATH.is_file():
        return None
    voiv_name = str(row["voivodeship"])
    with sqlite3.connect(_VOIVODESHIP_DB_PATH) as v_conn:
        v_conn.row_factory = sqlite3.Row
        v_row = v_conn.execute(
            "SELECT * FROM voivodeships WHERE name = ? COLLATE NOCASE",
            (voiv_name,),
        ).fetchone()
        if v_row is None:
            return None
        if relation in _VOIVODESHIP_SCALAR_RELATIONS:
            return v_row[_VOIVODESHIP_SCALAR_RELATIONS[relation]]
        if relation in _VOIVODESHIP_LIST_QUERIES:
            return [
                r[0]
                for r in v_conn.execute(
                    _VOIVODESHIP_LIST_QUERIES[relation],
                    (v_row["id"],),
                ).fetchall()
            ]
    return None


def get_entity_row(conn: sqlite3.Connection, config: LocalModeConfig, entity_name: str) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    table = _safe_identifier(config.table)
    name_col = _safe_identifier(config.name_column)
    row = conn.execute(
        " ".join(["SELECT * FROM", table, "WHERE", name_col, "= ? COLLATE NOCASE"]),
        (entity_name,),
    ).fetchone()
    if row:
        return row
    if config.mode_name == "Wojewodztwodle":
        resolved_v = resolve_voivodeship_name(entity_name)
        if resolved_v:
            row = conn.execute(
                " ".join(["SELECT * FROM", table, "WHERE", name_col, "= ?"]),
                (resolved_v,),
            ).fetchone()
            if row:
                return row
    if config.mode_name == "Countydle":
        resolved_c = _resolve_english_county_alias(entity_name)
        if resolved_c != entity_name:
            row = conn.execute(
                " ".join(["SELECT * FROM", table, "WHERE", name_col, "= ? COLLATE NOCASE"]),
                (resolved_c,),
            ).fetchone()
            if row:
                return row
    target_norm = norm(entity_name)
    all_rows = conn.execute(" ".join(["SELECT * FROM", table])).fetchall()
    for r in all_rows:
        if norm(r[config.name_column]) == target_norm:
            return r
        if "seat" in r.keys() and r["seat"] and norm(r["seat"]) == target_norm:
            return r
        if "county_town" in r.keys() and r["county_town"] and norm(r["county_town"]) == target_norm:
            return r
    return None


def get_relation_value(conn: sqlite3.Connection, config: LocalModeConfig, row: sqlite3.Row, relation: str) -> Any:
    if relation in config.scalar_relations:
        col = config.scalar_relations[relation]
        return row[col]
    if relation in config.list_relations:
        raw_table, raw_column = config.list_relations[relation]
        table = _safe_identifier(raw_table)
        column = _safe_identifier(raw_column)
        fk_column = _safe_identifier(config.fk_column or "".join([config.table[:-1], "_id"]))
        if config.mode_name == "Powiatdle" and relation in {"borders_powiat", "borders_voivodeship"}:
            query = " ".join([
                "SELECT", ".".join(["facts", column]),
                "FROM powiat_border_coverage AS coverage LEFT JOIN", table,
                "AS facts ON", ".".join(["facts", fk_column]), "= coverage.powiat_id",
                "WHERE coverage.powiat_id = ?",
            ])
            values = conn.execute(query, (row["id"],)).fetchall()
            return [value[0] for value in values if value[0] is not None] if values else None
        waters = [
            r[0]
            for r in conn.execute(
                " ".join(["SELECT", column, "FROM", table, "WHERE", fk_column, "= ?"]),
                (row["id"],),
            ).fetchall()
        ]
        if relation == "water_access":
            from utils.water_hierarchy import expand_water_bodies
            return list(expand_water_bodies(waters))
        return waters
    return None


def _reference_row(
    conn: sqlite3.Connection,
    config: LocalModeConfig,
    row: sqlite3.Row,
    node: Any,
    item_value: Any,
) -> sqlite3.Row | None:
    if isinstance(node, dict):
        if node.get("entity") == config.target_entity:
            return row
        if node.get("entity") == "item" and isinstance(item_value, sqlite3.Row):
            return item_value
        entity_name = node.get("entity")
        if entity_name and entity_name not in {config.target_entity, "item"}:
            return get_entity_row(conn, config, entity_name)
    return None


def resolve_ref(
    conn: sqlite3.Connection,
    config: LocalModeConfig,
    row: sqlite3.Row,
    node: Any,
    item_value: Any = None,
) -> Any:
    if isinstance(node, dict) and set(node.keys()) == {"value"}:
        return node.get("value")
    if (
        config.mode_name == "Powiatdle"
        and isinstance(node, dict)
        and node.get("entity") in {"target_voivodeship", "voivodeship", "wojewodztwo"}
    ):
        return _get_parent_voivodeship_relation(row, str(node.get("relation") or ""))
    entity_row = _reference_row(conn, config, row, node, item_value)
    if entity_row is not None:
        return get_relation_value(conn, config, entity_row, node.get("relation", ""))
    if isinstance(node, dict) and node.get("entity") == "item":
        return item_value if node.get("relation") == "name" else None
    return node
