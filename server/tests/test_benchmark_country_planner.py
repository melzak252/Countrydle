from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "server" / "scripts" / "benchmark_country_planner.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("benchmark_country_planner_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shape_module():
    return SimpleNamespace(
        SUPPORTED_RELATIONS={"name", "official_languages", "borders_country"},
        PLANNER_OPERATORS={"equals", "contains"},
        local_answering=SimpleNamespace(
            LIST_RELATION_QUERIES={"official_languages", "borders_country"},
            find_country=lambda conn, name: None,
        ),
    )


@pytest.mark.parametrize("hardlink", [False, True])
def test_output_collision_preserves_database_and_stops_cli_before_provider(tmp_path, hardlink):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps({
            "description": "collision regression",
            "cases": [{
                "id": "clarify-only", "split": "development", "category": "clarify",
                "question": "Unclear question", "route": "clarify", "gold_plan": None,
                "required_atoms": [], "notes": "",
            }],
        }),
        encoding="utf-8",
    )
    database = tmp_path / "facts.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE countries (app_country_name TEXT)")
        conn.execute("INSERT INTO countries VALUES ('Exampleland')")
    original = database.read_bytes()
    output = tmp_path / "report.json" if hardlink else database
    if hardlink:
        os.link(database, output)
    env = os.environ.copy()
    # Keep dotenv from restoring live credentials if the collision guard regresses.
    env["GEMINI_API_KEY"] = ""
    env["OPENAI_API_KEY"] = "benchmark-disabled"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(corpus),
            "--database",
            str(database),
            "--output",
            str(output),
            "--variant",
            "current",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 2
    assert database.read_bytes() == original


def test_gold_item_operand_requires_its_quantifier_scope():
    harness = _load_harness()
    module = _shape_module()
    free_item = {
        "operator": "equals",
        "left": {"entity": "item", "relation": "name"},
        "right": {"value": "English"},
    }
    predicate_without_bound_item = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "official_languages"},
        "condition": {
            "operator": "equals",
            "left": {"entity": "target_country", "relation": "name"},
            "right": {"value": "Germany"},
        },
    }

    free_item_errors = harness._check_plan_shape(free_item, module, None)
    predicate_errors = harness._check_plan_shape(predicate_without_bound_item, module, None)

    assert any(issue.get("code") == "unbound_item" for issue in free_item_errors)
    assert any(issue.get("code") == "missing_bound_item" for issue in predicate_errors)


def test_nested_quantifier_item_uses_the_nearest_binding():
    harness = _load_harness()
    nested = {
        "operator": "any",
        "items": {"entity": "target_country", "relation": "borders_country"},
        "condition": {
            "operator": "any",
            "items": {"entity": "item", "relation": "official_languages"},
            "condition": {
                "operator": "equals",
                "left": {"entity": "item", "relation": "name"},
                "right": {"value": "English"},
            },
        },
    }

    assert harness._check_plan_shape(nested, _shape_module(), None) == []
