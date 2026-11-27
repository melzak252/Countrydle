"""Read/write store for static RAG text fragments in local SQLite (`data/rag_fragments.sqlite`).

Vectors live in Qdrant; keeping static Wikipedia text fragments in SQLite instead of
PostgreSQL keeps PostgreSQL lean (~80 MB instead of 430+ MB) and shrinks routine
`pg_dump` backups by >90%.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    entity_name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fragments_type_entity_id
    ON fragments (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_fragments_type_entity_name
    ON fragments (entity_type, entity_name);
"""


def default_fragments_db_path() -> Path:
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data" if (base / "data").exists() else base.parent / "data"
    return data_dir / "rag_fragments.sqlite"


def init_fragments_db(db_path: Optional[Path] = None) -> Path:
    path = db_path or default_fragments_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return path


def get_entity_fragments(
    entity_type: str,
    *,
    entity_id: Optional[int] = None,
    entity_name: Optional[str] = None,
    limit: int = 25,
    db_path: Optional[Path] = None,
) -> List[str]:
    """Return up to `limit` text fragments for an entity from SQLite, or [] if absent."""
    path = db_path or default_fragments_db_path()
    if not path.is_file():
        return []
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except Exception:
        return []
    try:
        rows: List[tuple] = []
        if entity_id is not None:
            rows = conn.execute(
                "SELECT text FROM fragments WHERE entity_type = ? AND entity_id = ? ORDER BY id LIMIT ?",
                (entity_type, int(entity_id), int(limit)),
            ).fetchall()
        if not rows and entity_name:
            rows = conn.execute(
                "SELECT text FROM fragments WHERE entity_type = ? AND lower(entity_name) = lower(?) ORDER BY id LIMIT ?",
                (entity_type, entity_name.strip(), int(limit)),
            ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def replace_entity_fragments(
    entity_type: str,
    entity_id: int,
    entity_name: str,
    texts: Iterable[str],
    *,
    db_path: Optional[Path] = None,
) -> int:
    """Replace all fragments for one entity in SQLite and return inserted row count."""
    path = init_fragments_db(db_path)
    clean_texts = [t for t in texts if t and t.strip()]
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "DELETE FROM fragments WHERE entity_type = ? AND entity_id = ?",
            (entity_type, int(entity_id)),
        )
        conn.executemany(
            "INSERT INTO fragments (entity_type, entity_id, entity_name, text) VALUES (?, ?, ?, ?)",
            [(entity_type, int(entity_id), entity_name, t) for t in clean_texts],
        )
        conn.commit()
        return len(clean_texts)
    finally:
        conn.close()
