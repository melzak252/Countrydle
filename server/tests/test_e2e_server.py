"""Fail-closed guards for the test-only browser API bootstrap."""
import pytest

from scripts.e2e_server import build_private_fact_snapshot, validate_database_target, validate_port


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://e2e:password@db.example/countrydle_e2e",
    "postgresql+asyncpg://e2e:password@localhost/guess_country",
    "postgresql+asyncpg://e2e:password@127.0.0.1/countrydle_e2e_production",
    "postgresql+asyncpg://postgres:password@127.0.0.1/countrydle_e2e",
    "sqlite+aiosqlite:///:memory:",
    "postgresql+asyncpg://e2e:password@127.0.0.1/countrydle_e2e?host=db.example",
])
def test_bootstrap_refuses_non_disposable_database_targets(url):
    with pytest.raises(ValueError):
        validate_database_target(url, "countrydle_e2e_0123456789abcdef")


@pytest.mark.parametrize("schema", ["public", "countrydle_e2e", 'countrydle_e2e_";DROP SCHEMA public', "countrydle_e2e_live"])
def test_bootstrap_refuses_unowned_schema_names(schema):
    with pytest.raises(ValueError):
        validate_database_target("postgresql+asyncpg://e2e:password@127.0.0.1/countrydle_e2e", schema)


def test_bootstrap_accepts_only_explicit_loopback_test_database_and_random_owned_schema():
    target = validate_database_target(
        "postgresql+asyncpg://e2e:password@127.0.0.1:55498/countrydle_e2e",
        "countrydle_e2e_0123456789abcdef",
    )
    assert target.database == "countrydle_e2e"
    assert target.host == "127.0.0.1"


@pytest.mark.parametrize("port", [0, -1, 65536, 8080, 8086, 5179])
def test_bootstrap_refuses_invalid_or_reserved_preview_ports(port):
    with pytest.raises(ValueError):
        validate_port(port)


def test_private_fact_builder_refuses_existing_database_without_modifying_it(tmp_path):
    existing = tmp_path / "country_facts.sqlite"
    existing.write_bytes(b"preexisting database that the harness does not own")
    with pytest.raises(FileExistsError):
        build_private_fact_snapshot(tmp_path)
    assert existing.read_bytes() == b"preexisting database that the harness does not own"
