from pathlib import Path

from utils.rag_fragments_store import (
    get_entity_fragments,
    init_fragments_db,
    replace_entity_fragments,
)


def test_rag_fragments_sqlite_roundtrip(tmp_path: Path):
    db_path = tmp_path / "rag_fragments.sqlite"
    init_fragments_db(db_path)

    inserted = replace_entity_fragments(
        "country",
        531,
        "Taiwan",
        ["Taiwan is an island in East Asia.", "Taipei is the capital."],
        db_path=db_path,
    )
    assert inserted == 2

    by_id = get_entity_fragments("country", entity_id=531, db_path=db_path)
    assert by_id == ["Taiwan is an island in East Asia.", "Taipei is the capital."]

    by_name = get_entity_fragments("country", entity_name="taiwan", db_path=db_path)
    assert by_name == by_id

    # Replace overwrites cleanly without duplicating
    replace_entity_fragments("country", 531, "Taiwan", ["Updated fragment."], db_path=db_path)
    assert get_entity_fragments("country", entity_id=531, db_path=db_path) == ["Updated fragment."]
