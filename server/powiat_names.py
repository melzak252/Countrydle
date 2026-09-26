"""Canonical county-name aliases and indexed SQLite resolution."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections.abc import Iterable, Mapping

_PREFIX_RE = re.compile(r"^(?:powiat|powiatu|powiatem|powiecie)\s+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.replace("ł", "l")
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return _PREFIX_RE.sub("", _SPACE_RE.sub(" ", value).strip(), count=1)


def _inflect_adjectives(value: str, ending: str) -> str | None:
    """Inflect recognized adjective tokens, including multiword compounds."""
    matches = list(re.finditer(r"[\w]+", value, flags=re.UNICODE))
    replacements: list[tuple[int, int, str]] = []
    for match in matches:
        word = match.group()
        if word.casefold().endswith("i"):
            suffix = "im" if ending == "instr" else "iego"
        elif word.casefold().endswith("y"):
            suffix = "ym" if ending == "instr" else "ego"
        else:
            continue
        replacements.append((match.start(), match.end(), word[:-1] + suffix))
    if not replacements:
        return None
    result = value
    for start, end, replacement in reversed(replacements):
        result = result[:start] + replacement + result[end:]
    return result


def _county_aliases(name: str, voivodeship: str, is_city_county: bool) -> set[str]:
    aliases = {name}
    if not is_city_county and name.casefold().startswith("powiat "):
        base = re.sub(r"\s*\([^)]*\)", "", name[7:]).strip()
        aliases.add(base)
        instr = _inflect_adjectives(base, "instr")
        genitive = _inflect_adjectives(base, "genitive")
        if instr:
            aliases.add(instr)
        if genitive:
            aliases.add(genitive)
    elif is_city_county and name.casefold().endswith(("awa", "owa")):
        aliases.update({name[:-1] + "y", name[:-1] + "ie", name[:-1] + "ą"})
    if voivodeship:
        unqualified = tuple(aliases)
        aliases.update(f"{alias} {voivodeship}" for alias in unqualified)
        aliases.update(f"{alias} województwo {voivodeship}" for alias in unqualified)
    return aliases


def build_powiat_aliases(rows: Iterable[Mapping[str, object]]) -> dict[str, set[int]]:
    """Build normalized aliases from catalog rows, retaining all collisions."""
    aliases: dict[str, set[int]] = {}
    for row in rows:
        powiat_id = int(row["id"])
        name = row["name"]
        voivodeship = row["voivodeship"]
        is_city_county = row["is_city_county"]
        if not isinstance(name, str) or not isinstance(voivodeship, str):
            raise ValueError("County catalog names and voivodeships must be strings")
        names = _county_aliases(name, voivodeship, bool(is_city_county))
        for alias in sorted(names):
            normalized = _normalize(alias)
            if normalized:
                aliases.setdefault(normalized, set()).add(powiat_id)
    return aliases


def resolve_powiat_name(conn: sqlite3.Connection, value: object) -> str | None:
    """Resolve a catalog alias to a canonical county name only if unique."""
    if not isinstance(value, str):
        return None
    normalized = _normalize(value)
    if not normalized:
        return None
    rows = conn.execute(
        "SELECT p.name FROM powiat_name_aliases AS a "
        "JOIN powiats AS p ON p.id = a.powiat_id "
        "WHERE a.alias = ? LIMIT 2",
        (normalized,),
    ).fetchall()
    if len(rows) != 1:
        return None
    return rows[0][0]
