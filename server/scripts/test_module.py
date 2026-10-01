"""Run one focused backend test group, or groups related to changed files."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = SERVER_DIR / "tests"

# Files intentionally overlap where a shared engine or contract affects modes.
TEST_GROUPS: dict[str, tuple[str, ...]] = {
    "countrydle": (
        "test_countrydle_local_kb.py",
        "test_countrydle_fallback.py",
        "test_countrydle_pipeline_eval_csv.py",
        "test_expansions.py",
        "test_game.py",
        "test_zero_500.py",
        "test_country_fact_editor.py",
        "test_country_facts_builder.py",
        "test_country_eligibility.py",
        "test_micronesia_alias.py",
    ),
    "powiatdle": (
        "test_powiat_borders.py",
        "test_powiat_border_source.py",
        "test_powiat_facts_enrichment.py",
        "test_powiat_names.py",
        "test_local_kb_other_modes.py",
        "test_zero_500.py",
    ),
    "wojewodztwodle": (
        "test_voivodeship_names.py",
        "test_local_kb_other_modes.py",
        "test_zero_500.py",
        "test_new_games.py",
    ),
    "us-statedle": (
        "test_generic_template_compiler.py",
        "test_local_kb_other_modes.py",
        "test_zero_500.py",
        "test_new_games.py",
    ),
    "continental": (
        "test_continental.py",
        "test_country_eligibility.py",
        "test_scoring_streaks.py",
        "test_zero_500.py",
    ),
    "flagdle": (
        "test_flagdle.py",
        "test_expansions.py",
        "test_scoring_streaks.py",
        "test_zero_500.py",
    ),
    "friend-matches": (
        "test_friend_matches.py",
        "test_friend_matches_postgres.py",
        "test_friend_match_providers.py",
    ),
    "question-engine": (
        "test_ai_clients.py",
        "test_countrydle_fallback.py",
        "test_countrydle_local_kb.py",
        "test_generic_template_compiler.py",
        "test_local_kb_other_modes.py",
        "test_plan_cache.py",
        "test_planner_contract.py",
        "test_question_accounting.py",
        "test_question_nonblocking.py",
        "test_shadow_audit.py",
        "test_slot_template_engine.py",
        "test_template_compiler.py",
    ),
    "auth": ("test_auth.py",),
    "guests": (
        "test_guest_guesses_db.py",
        "test_guest_participation.py",
        "test_guest_participation_routes.py",
        "test_guest_sync.py",
        "test_guest_system.py",
    ),
    "admin": (
        "test_admin_question_tests.py",
        "test_answer_reports.py",
        "test_country_fact_editor.py",
        "test_shadow_audit.py",
    ),
    "leaderboards": (
        "test_active_players_count.py",
        "test_leaderboard_activity.py",
        "test_participation_reporting.py",
        "test_profile_statistics.py",
        "test_scoring_streaks.py",
    ),
    "content": (
        "test_blog.py",
        "test_explore.py",
        "test_patch_notes.py",
        "test_sitemap.py",
    ),
    "api": (
        "test_admin_question_tests.py",
        "test_answer_reports.py",
        "test_archive_all_games.py",
        "test_auth.py",
        "test_blog.py",
        "test_continental.py",
        "test_explore.py",
        "test_flagdle.py",
        "test_game.py",
        "test_guest_participation_routes.py",
        "test_guest_sync.py",
        "test_new_games.py",
        "test_zero_500.py",
    ),
    "game-rules": ("test_game_logic.py", "test_scoring_streaks.py"),
    "geo": ("test_geo_hints.py", "test_game_logic.py"),
    "test-selection": ("test_test_module.py",),
}

# More specific paths precede shared infrastructure. Unmapped application changes
# intentionally require an explicit choice rather than silently running too little.
SOURCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("server/countrydle/", ("countrydle", "question-engine")),
    ("server/powiatdle/", ("powiatdle", "question-engine")),
    ("server/wojewodztwodle/", ("wojewodztwodle", "question-engine")),
    ("server/us_statedle/", ("us-statedle", "question-engine")),
    ("server/continental/", ("continental",)),
    ("server/flagdle/", ("flagdle",)),
    ("server/friend_matches/", ("friend-matches",)),
    ("server/users/", ("auth",)),
    ("server/utils/guest_session.py", ("guests",)),
    ("server/utils/plan_cache.py", ("question-engine",)),
    ("server/utils/ai_clients.py", ("question-engine",)),
    ("server/utils/geo.py", ("geo",)),
    ("server/qdrant/", ("question-engine",)),
    ("server/game_logic.py", ("game-rules", "api")),
    ("server/local_kb_question.py", ("question-engine",)),
    ("server/generic_template_compiler.py", ("question-engine",)),
    ("server/slot_template_engine.py", ("question-engine",)),
    ("server/app.py", ("api",)),
    ("server/utils/app.py", ("api",)),
    ("server/db/models/", ("api", "guests", "friend-matches", "leaderboards", "question-engine")),
    ("server/db/repositories/", ("api", "guests", "friend-matches", "leaderboards", "question-engine")),
    ("server/db/", ("api",)),
    ("server/schemas/", ("api",)),
    ("server/admin/", ("admin", "api")),
    ("server/tests/", ()),
    ("server/scripts/test_module.py", ("test-selection",)),
    ("client/", ()),
)


def changed_paths(base: str) -> list[str]:
    commands = (
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard", "--full-name"],
    )
    paths: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=SERVER_DIR, check=True, text=True, capture_output=True)
        paths.update(line for line in result.stdout.splitlines() if line)
    return sorted(paths)


def groups_for_changes(paths: list[str]) -> tuple[set[str], list[str]]:
    selected: set[str] = set()
    unmapped: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized.startswith("server/tests/"):
            test_name = Path(normalized).name
            if test_name.startswith("test_") and test_name.endswith(".py"):
                test_path = TEST_DIR / test_name
                if test_path.is_file():
                    selected.add(str(test_path))
            elif test_name.endswith(".py") or test_name == "pytest.ini":
                unmapped.append(normalized)
            continue
        if normalized == "server/pytest.ini":
            unmapped.append(normalized)
            continue
        if not normalized.startswith("server/"):
            continue
        matches = [groups for prefix, groups in SOURCE_GROUPS if normalized.startswith(prefix)]
        if matches:
            for groups in matches:
                selected.update(groups)
        elif normalized.endswith((".py", ".sql")):
            unmapped.append(normalized)
    return selected, unmapped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", nargs="?", choices=sorted(TEST_GROUPS))
    parser.add_argument("--list", action="store_true", help="list focused test groups")
    parser.add_argument("--changed", metavar="BASE", help="run test groups affected since BASE (default comparison includes working-tree changes)")
    raw_args = sys.argv[1:]
    if "--" in raw_args:
        separator = raw_args.index("--")
        forwarded = raw_args[separator + 1:]
        raw_args = raw_args[:separator]
    else:
        forwarded = []
    args = parser.parse_args(raw_args)

    if args.list:
        for name, files in TEST_GROUPS.items():
            print(f"{name}: {', '.join(files)}")
        print("all: use python -m pytest -q tests")
        return 0

    if args.group and args.changed:
        parser.error("choose a named group or --changed, not both")

    if args.changed:
        paths = changed_paths(args.changed)
        selected, unmapped = groups_for_changes(paths)
        if unmapped:
            print("No focused test mapping for changed application files:", file=sys.stderr)
            print("\n".join(f"  {path}" for path in unmapped), file=sys.stderr)
            print("Run an explicit group or the full suite; update SOURCE_GROUPS when appropriate.", file=sys.stderr)
            return 2
        targets = sorted(
            {str(TEST_DIR / filename) for group in selected for filename in TEST_GROUPS.get(group, ())}
            | {entry for entry in selected if entry.startswith(str(TEST_DIR))}
        )
        if not targets:
            print("No backend application or test files changed; no backend tests selected.")
            return 0
        print("Selected groups/files:", ", ".join(sorted(selected)))
    elif args.group:
        targets = [str(TEST_DIR / filename) for filename in TEST_GROUPS[args.group]]
    else:
        parser.error("provide a group, --changed BASE, or --list")

    missing = [target for target in targets if not Path(target).is_file()]
    if missing:
        parser.error("test module is missing: " + ", ".join(missing))

    return subprocess.run([sys.executable, "-m", "pytest", *forwarded, *targets], cwd=SERVER_DIR).returncode


if __name__ == "__main__":
    raise SystemExit(main())
