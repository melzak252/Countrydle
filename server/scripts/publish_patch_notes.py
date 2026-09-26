import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

from version import SERVER_VERSION

_FIELDS = {"version", "title", "body"}
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_DEFAULT_FILE = Path(__file__).resolve().parents[1] / "release_notes.json"


class ManifestError(ValueError):
    pass


def load_manifest(path: Path) -> Dict[str, str]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read release manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("release manifest must be a JSON object")
    extra = set(payload) - _FIELDS
    missing = _FIELDS - set(payload)
    if extra or missing:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if extra:
            details.append("unexpected " + ", ".join(sorted(extra)))
        raise ManifestError("invalid release manifest fields: " + "; ".join(details))
    for field in _FIELDS:
        value = payload[field]
        max_length = 32 if field == "version" else (200 if field == "title" else 20000)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
            raise ManifestError(f"{field} must be nonempty text of at most {max_length} characters")
        payload[field] = value.strip()
    if not _VERSION.fullmatch(payload["version"]):
        raise ManifestError("version must be canonical X.Y.Z")
    if payload["version"] != SERVER_VERSION:
        raise ManifestError(f"manifest version {payload['version']} does not match deployed SERVER_VERSION {SERVER_VERSION}")
    return payload


async def publish(session, payload: Dict[str, str]) -> str:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from db.models.patch_note import PatchNote

    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError(f"patch-note publication is unsupported for database dialect {dialect}")
    async with session.begin():
        statement = insert(PatchNote).values(**payload).on_conflict_do_nothing(index_elements=["version"])
        result = await session.execute(statement)
        if result.rowcount == 1:
            return "published"
        existing = await session.scalar(select(PatchNote).where(PatchNote.version == payload["version"]))
        if existing is None:
            raise RuntimeError("version conflict occurred but the existing release could not be read")
        if existing.title != payload["title"] or existing.body != payload["body"]:
            raise ManifestError(f"version {payload['version']} is already published with different content")
        return "already published; original publication timestamp retained"


async def _publish_to_database(payload: Dict[str, str]) -> str:
    from db import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as session:
            return await publish(session, payload)
    finally:
        await engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish the deployed release's patch notes")
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE, help="JSON release manifest")
    parser.add_argument("--check", action="store_true", help="validate without connecting to the database")
    args = parser.parse_args(argv)
    try:
        payload = load_manifest(args.file)
        if args.check:
            print(f"Validated patch notes for {payload['version']}")
            return 0
        result = asyncio.run(_publish_to_database(payload))
        print(f"Patch notes {payload['version']}: {result}")
        return 0
    except ManifestError as exc:
        print(f"Patch-note publication rejected: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"Patch-note publication failed: database unavailable or write failed ({type(exc).__name__}); check DATABASE_URL, connectivity, and Alembic migrations", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
