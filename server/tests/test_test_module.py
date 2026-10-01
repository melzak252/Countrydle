import subprocess

import pytest

import scripts.test_module as test_module
from scripts.test_module import TEST_GROUPS, groups_for_changes


@pytest.mark.parametrize(
    ("source_path", "mode_group", "api_test_module"),
    [
        ("server/countrydle/__init__.py", "countrydle", "test_game.py"),
        ("server/powiatdle/__init__.py", "powiatdle", "test_zero_500.py"),
        ("server/wojewodztwodle/__init__.py", "wojewodztwodle", "test_new_games.py"),
        ("server/us_statedle/__init__.py", "us-statedle", "test_new_games.py"),
    ],
)
def test_mode_route_changes_select_mode_api_contracts(source_path, mode_group, api_test_module):
    selected, unmapped = groups_for_changes([source_path])

    assert not unmapped
    assert mode_group in selected
    assert api_test_module in TEST_GROUPS[mode_group]

@pytest.mark.parametrize(
    "source_path",
    [
        "server/db/models/question.py",
        "server/db/repositories/question.py",
    ],
)
def test_question_persistence_changes_select_question_engine_contracts(source_path):
    selected, unmapped = groups_for_changes([source_path])

    assert not unmapped
    assert "question-engine" in selected


def test_countrydle_group_includes_countrydle_expansion_regressions():
    assert "test_expansions.py" in TEST_GROUPS["countrydle"]


def test_runner_changes_select_runner_regressions():
    selected, unmapped = groups_for_changes(["server/scripts/test_module.py"])

    assert not unmapped
    assert "test-selection" in selected


def test_changed_paths_keeps_untracked_paths_repository_relative(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    server_dir = repo / "server"
    (server_dir / "tests").mkdir(parents=True)
    tracked_file = server_dir / "tracked.py"
    tracked_file.write_text("before = True\n")

    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Pytest"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    tracked_file.write_text("after = True\n")
    (server_dir / "tests" / "test_new.py").write_text("def test_new(): pass\n")
    monkeypatch.setattr(test_module, "SERVER_DIR", server_dir)

    paths = test_module.changed_paths("main")

    assert "server/tracked.py" in paths
    assert "server/tests/test_new.py" in paths
