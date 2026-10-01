# Backend test guide

This directory contains the backend regression suite. Keep tests in the existing
flat `tests/` directory and organize them by concern in `test_*.py` modules. The
Python runner and environment assumptions live under `server/`.

## Run only the affected tests

Run commands from `server/` with the backend virtual environment active and its
normal environment configured (at minimum `DATABASE_URL`, `SECRET_KEY`,
`ALGORITHM`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, and `NOREPLY_EMAIL`).

```bash
# One test function or one pytest module
python -m pytest -q tests/test_powiat_names.py::test_catalog_adjective_forms_resolve_to_county_not_city
python -m pytest -q tests/test_powiat_names.py

# A feature-area group (groups can include shared-engine regressions)
python scripts/test_module.py powiatdle -- -q
python scripts/test_module.py question-engine -- -q

# Select groups based on source/test files changed from the base branch
python scripts/test_module.py --changed main -- -q

# Show available groups and the modules each group runs
python scripts/test_module.py --list

# Explicit full suite; use when a change is cross-cutting or as a release gate
python -m pytest -q tests
```

Prefer the narrowest command that covers the changed behavior. A change to one
game mode normally needs its mode group and the affected test module, not the
full suite. Changes to `server/app.py`, shared request wiring, common database
models/repositories, or cross-mode question evaluation need the broader groups
selected by `--changed` and may justify the full suite. Frontend tests are
separate: run them from `client/`, for example
`bun test tests/gameActionComposer.test.ts`.

`--changed BASE` compares the branch with `BASE` and includes staged, unstaged,
and untracked files. It selects a changed test file directly; known source paths
select their mapped groups. Unknown backend `.py` or `.sql` paths fail closed and
print the files that need a mapping. Client-only, documentation-only, and other
non-backend changes do not run backend tests. The mapping is maintained in
`server/scripts/test_module.py` (`TEST_GROUPS` and `SOURCE_GROUPS`).

## Where tests belong

Use the existing module for the behavior under test; split a file only when it
has multiple independent concerns that are easier to select and understand
separately. Do not move tests into nested directories without a concrete need:
shared `conftest.py` fixtures and existing path-based data resolution assume the
flat layout.

Common modules:

| Concern | Test modules |
|---|---|
| Countrydle facts and question behavior | `test_countrydle_local_kb.py`, `test_countrydle_fallback.py`, `test_countrydle_pipeline_eval_csv.py` |
| Generic planner/compiler and local-KB modes | `test_planner_contract.py`, `test_generic_template_compiler.py`, `test_local_kb_other_modes.py`, `test_template_compiler.py`, `test_slot_template_engine.py` |
| Powiat facts and boundaries | `test_powiat_facts_enrichment.py`, `test_powiat_borders.py`, `test_powiat_border_source.py`, `test_powiat_names.py` |
| Voivodeship names and facts | `test_voivodeship_names.py`, `test_local_kb_other_modes.py` |
| HTTP routes and game behavior | `test_game.py`, `test_new_games.py`, `test_continental.py`, `test_flagdle.py`, `test_explore.py` |
| Guest state and participation | `test_guest_*.py`, `test_guest_participation*.py` |
| Friend matches | `test_friend_matches.py`, `test_friend_match_providers.py`, `test_friend_matches_postgres.py` |
| Shared state, scoring, and reporting | `test_game_logic.py`, `test_scoring_streaks.py`, `test_question_accounting.py`, `test_participation_reporting.py`, `test_answer_reports.py` |
| Focused test selection tooling | `test_test_module.py` |

For all current module-to-group assignments, use `python scripts/test_module.py --list`.
Update the runner when adding a test module or a source area that should select it.
A module can belong to multiple groups when it protects a shared contract. The
runner deduplicates module paths when groups overlap.

## Adding or changing a test

1. Find the production contract and nearest test module. Reuse its fixture and
   naming conventions; do not create a parallel test framework or fixture stack.
2. For a bug or behavior change, add the smallest regression assertion first
   and run it to establish the expected failure. Implement the change, then run
   the test and its focused module/group.
3. Assert observable behavior: result values, response status/body, persistence,
   state transitions, or an invariant at a meaningful boundary. Cover relevant
   true/false/unknown, limits, precedence, and error behavior. Avoid tests that
   only check forwarding, mock echoes, source text, incidental defaults, or
   “does not throw.”
4. Keep scenarios independent and deterministic. Use `monkeypatch`, `tmp_path`,
   in-memory SQLite, controlled HTTP/model responses, and existing fixtures.
   Do not call real providers or depend on a developer's live database in routine
   tests. Restore global state/dependency overrides through `monkeypatch`, a
   fixture finalizer, or `try/finally`.
5. Keep a test when it verifies a distinct input, boundary, or transition, even
   if the setup resembles another case. Remove only proven dead or duplicate
   coverage; do not collapse independent cases just to reduce pytest's reported
   count. Parameterize related inputs when each case expresses the same
   contract and remains easy to diagnose.
6. Update `TEST_GROUPS` for the new module and `SOURCE_GROUPS` for any new
   production path that `--changed` should recognize. Add a test path to every
   relevant group; shared planner, evaluator, database, and API contracts often
   span multiple modes.

Use descriptive names such as
`test_<condition>_<expected_behavior>`. Keep comments for non-obvious setup or
invariants, not for narrating each assertion.

## Fixtures, databases, and external services

`tests/conftest.py` provides `async_client`, async test setup, and an autouse
fixture that replaces common repositories for hermetic endpoint tests. Tests
marked `@pytest.mark.real_database` opt out of those repository mocks; use that
marker only when the real persistence behavior is the contract being tested.

PostgreSQL integration tests must use an explicitly disposable database URL and
create isolated schemas. They must never fall back to `DATABASE_URL`:

| Environment variable | Test area |
|---|---|
| `QUESTION_TEST_DATABASE_URL` (or `FRIEND_TEST_DATABASE_URL`) | Question accounting |
| `PARTICIPATION_TEST_DATABASE_URL` | Guest participation |
| `FRIEND_TEST_DATABASE_URL` | Friend-match locking and transactions |
| `PROFILE_STATS_TEST_DATABASE_URL` | Profile statistics |

These tests skip when their dedicated URL is unset. Configure one only for a
disposable test database; never point it at development or production data.

Tests using repository fact databases (`server/data/*.sqlite`) need those local
facts present. Some modules explicitly skip when a database is missing. Keep
path resolution compatible with both the server container and host environment;
use the existing data-path pattern in adjacent tests rather than hard-coding a
new location.

Live Countrydle fallback evaluation is opt-in via
`COUNTRYDLE_RUN_LIVE_FALLBACK_EVAL=1` and requires PostgreSQL, Qdrant, and valid
provider keys. It is an evaluation, not a deterministic regression test; do not
enable it for routine focused runs.

The planner and endpoint evaluations in `test_micronesia_alias.py` are skipped
unless `COUNTRYDLE_RUN_LIVE_PLANNER_EVAL=1`. They can call Gemini and OpenAI and
incur provider charges; enabling the flag requires valid provider credentials
and local facts. Keep it unset for routine group runs. This is separate from the
live fallback evaluation flag above.

## Full-suite policy

The number of collected cases includes parameterized inputs and distinct
per-mode contracts. Do not remove valid coverage solely to lower the count.
Run a focused module/group during implementation. Use the full suite for
cross-cutting changes, test infrastructure/fixture changes, or an explicit
release check; CI/release policy remains authoritative.
