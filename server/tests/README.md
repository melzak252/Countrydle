# Backend test guide

This directory contains the backend regression suite. Keep tests in the existing
flat `tests/` directory and organize them by concern in `test_*.py` modules. The
Python runner and environment assumptions live under `server/`.

## Install and regenerate dependencies

Use Python 3.12. From `server/`, create a clean environment and install the
committed, hash-verified lock (the container uses the same command):

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --no-deps -r requirements.txt
```

`requirements.in` contains the direct requirements; `requirements.txt` contains
their fully pinned transitive closure and distribution hashes. The initial lock
preserves the versions in the existing Python 3.12 QA environment, including
the existing pytest dependencies. No separate development dependency convention
is introduced. Do not edit transitive pins or hashes manually.

Regenerate with **uv 0.12.2**, Python 3.12, and the existing lock present:

```bash
# Install the lock generator in a separate tooling environment, if needed.
python3.12 -m venv /tmp/countrydle-lock-tools
/tmp/countrydle-lock-tools/bin/python -m pip install uv==0.12.2
/tmp/countrydle-lock-tools/bin/uv pip compile --python-version 3.12 --generate-hashes --no-emit-index-url requirements.in --output-file requirements.txt
```

Normal regeneration reuses existing pins. For an intentional dependency update,
change its direct pin in `requirements.in`, then regenerate and review both files.
To intentionally update one transitive dependency, add `--upgrade-package NAME`.
Use the same generator version and package index for deterministic regeneration;
do not delete the existing lock or use an unbounded `--upgrade`.

Build the locked backend container from `server/` with
`docker build -t countrydle-backend-hardening .`. Installation/build verification
must use disposable environments and data, never the live player database.

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
separate: run `bun run test` from `client/` for the complete Bun/Node-test suite.

`--changed BASE` compares the branch with `BASE` and includes staged, unstaged,
and untracked files. It selects a changed test file directly; known source paths
select their mapped groups. Unknown backend `.py` or `.sql` paths fail closed and
print the files that need a mapping. Client-only, documentation-only, and other
non-backend changes do not run backend tests. The mapping is maintained in
`server/scripts/test_module.py` (`TEST_GROUPS` and `SOURCE_GROUPS`).

### Countrydle English semantic preservation

The active Countrydle planner tries whole-entity compilation, then strict English
templates, before consulting the plan cache or Gemini. Deterministic plans report
`provider="template"` and `contract_version="countrydle-strict-v2"`. The English
path does not use the shared slot masker or legacy substring matching.

Supported skeletons cover exact entity identity/region names, single-country
borders, island status, coastline/landlocked status, hemisphere membership,
equator crossing or north/south position, catalogued seas/oceans, and three
typed country-reference families:

- `Does <subject> have a population/area greater/less than <country>?`
  (also larger/higher and smaller/lower);
- `Is <subject> north/south/east/west of <country>?`
  (also farther/further and `than`);
- `Does <subject> share a/any continent with <country>?` or
  `Does <subject> have a/any continent in common with <country>?`.

Exact leading `this country`, `the hidden country`, and `hidden country` target
subjects reuse the existing `it` skeletons. Standalone population/area thresholds
also accept strict, inclusive, and equality comparisons, grouped/decimal numbers,
and thousand/million/billion scales. Area means stored square kilometres;
incompatible units and malformed numbers decline. Capital-name length supports
longer/shorter, equality, and inclusive bounds using the existing game convention
that excludes spaces and hyphens. Named-country possessives are not rewritten.

An explicitly named country **subject** still denotes the hidden target;
named comparison/object references remain named. Directions use matching
latitude/longitude operands, and shared continents use an OR of per-continent
AND predicates rather than binding continent strings as countries.
Every token must be consumed. Additional clauses, negations, qualifiers,
temporal modifiers, and symbolic comparisons decline compilation rather than
answer a partial predicate. Other English forms—including historical
membership, neighbor counts and comparisons outside these exact
skeletons—retain the model-planner/fallback route. Conjunctions or hyphens in
border-country names also conservatively use that route. Polish compilation
remains a separate legacy path and is not newly enabled in the active planner;
generic game-mode compilers are unchanged.

Identity and location are distinct: `Is it Italy?` checks the name, whereas
`Is it in Italy?` declines local compilation because country containment is not
a local fact relation. `Is it in Micronesia?` checks the geographic area;
`Is it Micronesia?` checks Federated States of Micronesia identity.
Local template records retain factual country names for post-game review.
Countrydle, continental and Flagdle public serializers suppress answered
explanations during play; explicit terminal context enables disclosure.
Invalid/unverified feedback is target-free in both active and terminal responses,
including rewritten questions and evidence. Fallback answer sanitization is unchanged.

`test_countrydle_factual_explanations.py` covers coordinate equality, bound
directional references, language counts, capital hyphen facts and punctuated
character-count units with isolated SQLite facts.
`test_local_mode_explanation_facts.py` covers localized stored facts, inverted
coastal predicates, named operands, logical/quantified facts, list text counts
and decisive short-circuit boundaries for `and`/`or`/`any`/`all`.
`test_question_context_privacy.py` checks public disclosure and nested terminal
state serialization. The real PostgreSQL Flagdle regression also verifies questions
asked after a win, since that mode allows unlimited post-game questions.

Countrydle fallback uses the same subject/reference policy. Before the provider
call, bounded English auxiliary/country/predicate prefixes replace a named
country subject with `the country`, retaining the complete predicate, negation,
date, and named comparison objects. Property subjects (`the population of
France`), possessives, quoted names, and named features/species such as the
Jordan River or Canada goose remain literal. Unrecognized prefixes are not
rewritten; their interpretation still depends on the provider. Only provider
inputs change, not the stored original question. Answer-cache keys include the
rendered prompts, so answers produced under older binding rules are not reused.
The shared fallback keeps its 15-second total deadline, persistent Boolean
answer cache (including `False`), report invalidation, and private retrieval
context.

The English catalog excludes Polish-only country and continent spellings;
shared English spellings/abbreviations such as `USA`, `UK`, and `DRC` still work.
`America` and `Congo` decline both identity and border compilation rather than
silently select one country. The separately invoked legacy Polish compiler
remains available.

Landlocked status means no coastline connected to the open sea. Its plan uses
`NOT EXISTS(marine_access)`, a derived view of `water_access` that excludes
inland bodies such as the Caspian, Aral, and Dead Seas. Named inland-water
queries retain their facts; generic coastline queries still include inland
shorelines. Model-planned Countrydle questions use prompt revision
`compact-v8-continent-borders-t1024`, invalidating older country plans without changing other
modes. Model plans reject non-coordinate directional operands, list/list
`contains`, country-item references over primitive lists, and plans that omit
the hidden target when the question has a hidden/named country subject.
Explicit parentheses are retained in the player-facing question instead of
accepting a flattened paraphrase. Numeric explanations distinguish equality
from strict inequality and retain threshold precision.

Touching/bordering a continent means `ANY(borders_country, item.continent contains
continent)`, not the target's continental membership. Bounded English questions
compile deterministically for every supported continent, preserving negation and
hidden-target subject binding. Qualified, compound, and unknown-place questions
decline the template rather than lose modifiers. Polish questions and spelling
repairs use the model; its prompt preserves the border relation and quantifier
scope. “In/part of a continent” remains a target-membership question.

Reported-answer regressions cover Americas within disjunctions and negations,
neighbor-item bindings, and preservation of North/South qualifiers. US Statedle
regressions distinguish broad Atlantic access through the Gulf of Mexico from
direct Atlantic coastline and East Coast membership; they also exercise Northeast
spelling aliases, negation, and compound conditions against real local facts.
The shared planner contract is `27`, excluding previous cached interpretations
in all modes. This does not rewrite persisted answers or review reports.

```bash
python -m pytest -q tests/test_countrydle_audit_regressions.py tests/test_local_kb_other_modes.py tests/test_generic_template_compiler.py tests/test_slot_template_engine.py
```

```bash
python -m pytest -q tests/test_template_compiler.py tests/test_countrydle_semantic_preservation.py tests/test_countrydle_audit_regressions.py tests/test_countrydle_english_corpus.py
```

`test_countrydle_semantic_preservation.py` covers positive skeleton controls,
generated modifier perturbations, isolated SQLite execution, offline planner
routing, operator-text parity, player-response name redaction, and fallback
subject/reference boundaries. New English coverage exercises actual answers at
strict/inclusive numeric boundaries, exact decimal scales, compatible/incompatible
units, and space/hyphen-insensitive capital-name length rather than pinning ASTs.
`test_countrydle_audit_regressions.py` guards target binding, typed spatial and
quantifier operands, shared continents, displayed grouping, named-object
references, truthful equality explanations, and continent-border versus target
membership semantics, including negation and countries with no land neighbors.
`test_countrydle_english_corpus.py` covers all 3,803 collected adversarial/control
questions plus 88 captured real-provider responses across 229 target scenarios,
through the actual planner, SQLite evaluator and player helper. Its committed
JSON fixtures contain reviewed expected plans/answers and a minimal frozen fact
snapshot; these tests need neither a live provider nor mutable application
fact databases. Both `countrydle` and `question-engine` groups include the new
regression modules. Optional live/integration tests remain separate verification
and are not implied by passing these deterministic regressions.

`country_planner_acceptance.json` also includes five production-derived
development cases for continent borders: English, Polish, compound, misspelled,
and negated questions. Live interpretation comparison is opt-in and requires
explicit approved pricing and call/cost caps. Development-only comparison does
not establish held-out accuracy or approve a release:

```bash
python scripts/benchmark_country_planner.py --live --variant current --corpus tests/country_planner_acceptance.json --split development --repeat 3 --env-file /path/to/private/.env --pricing /path/to/reviewed-pricing.json --max-provider-calls 100 --max-cost-usd 1 --output /tmp/country-planner-continent-borders.json
```

The three opt-in real-provider fallback regressions cover historical membership,
hidden-subject population comparison, and literal named-country property
comparison. They use controlled retrieval facts and no persistent answer cache:

```bash
COUNTRYDLE_RUN_LIVE_FALLBACK_EVAL=1 python -m pytest -q tests/test_countrydle_fallback.py::test_live_fallback_binds_named_subject_but_keeps_named_references
```

Supply a working `GEMINI_API_KEY` in addition to the normal backend environment.
Run this specific node rather than enabling all optional integration tests;
other live tests can require PostgreSQL, Qdrant, and additional provider keys.

## Answer-quality release gates

`scripts/benchmark_country_planner.py` defaults to the frozen
`tests/answer_quality_corpus.json`, split into development and held-out EN/PL
cases with multiple targets, negation, compounds, temporal qualifiers,
unsupported facts and unresolved/disputed expectations.
It reports **template**, **model-planned local** and **fallback** separately.
Correct answers, wrong answers, correct abstentions, missing answers, route/
interpretation errors, fact issues, unreviewed targets and provider failures
remain distinct. Evaluation correctness, factual correctness, interpretation
and grounding are separate fields, not one inferred success flag.

```bash
# Key-free deterministic semantics; no env file, providers, history or caches.
python scripts/benchmark_country_planner.py --offline --repeat 3 --output /tmp/answer-quality-offline.json

# Opt-in actual interpretation and actual fallback answer stage; single worker.
python scripts/benchmark_country_planner.py --live --variant current --workers 1 --repeat 3 \
  --env-file /path/to/private/.env --pricing /path/to/reviewed-pricing.json \
  --max-provider-calls 100 --max-cost-usd 1 --execute-fallback \
  --fallback-model gemini-2.5-flash-lite \
  --retrieval-snapshot /path/to/reviewed-retrieval.json \
  --output /tmp/answer-quality-live.json
```

Offline supplied/captured plans are **not** current end-to-end accuracy evidence.
Release fail/insufficient returns nonzero, including for a successful semantic
run on a corpus too small to approve a release. Do not disable CI regressions
because this opt-in release assessment correctly declines approval.

The policy is frozen before executing held-out cases: zero template errors;
local answer/route rate at least 0.95; conditional fallback answer rate at least
0.90; at least 20 held-out targets per path, five cases per language/path and
three live repeats. Unreviewed expectations, absent revision/usage/cost or
grounding evidence are insufficient. The committed small corpus cannot certify
these denominators; independent adjudication and a larger reviewed cohort are
prerequisites, not permission to tune thresholds against observed scores.

Pricing JSON must contain `approved: true`, `currency: "USD"`, `as_of`, and a
`models` entry for every executing model, with nonnegative
`input_usd_per_million`, `cached_input_usd_per_million`,
`output_usd_per_million` and an approved positive `max_input_tokens`.
Verify the dated rates against the
[provider's published pricing](https://ai.google.dev/gemini-api/docs/pricing).
The token bound is an operator-approved conservative reservation bound, not an
assertion of the model's context window. Every provider retry reserves a call
and worst-case input/output/thought cost before transmission; reservations are
never refunded. Caps cannot exceed 100 calls or USD 1 in this adapter.
Missing cached/thought usage is unknown, not silently zero or a fully observed
bill. Actual observed costs and conservative reservations are reported separately.

Fallback uses the production pure prompt builder and real answer adapter,
conditional on immutable **pre-retrieved** context. The JSON has
`schema_version: 1` and `contexts[case_id][target]` records with explicit `text`,
citation/retrieval facts and their review status; every attempted case/target
must be present. Empty/unreviewed context stays missing evidence.
This does not measure live embeddings, vector retrieval or answer-cache reuse.
Only a reviewed grounding assessment can certify grounding; a provider's
self-report or a cited URL alone cannot.

Reports record corpus/fact/source/cache identity, requested and observed model
revision, repeated attempts, latency, usage missingness and bounded spend.
Facts are read from a private SQLite snapshot; cache adapters and provider
configuration are isolated without application imports or gameplay writes.
Report output cannot alias inputs, source, credentials or SQLite sidecars.
Generic-mode plan-cache identity includes semantic/prompt/configuration version:
change that identity when interpretation semantics change, never reuse a stale
plan merely because the question string matches.

## Hardening regression and publication boundary

The mandatory workflow runs the complete offline backend suite with a disposable
non-superuser PostgreSQL role, regular frontend Bun/Python tests, both matching
desktop/mobile Playwright projects and both container builds.
Publication needs all four job groups; failed/cancelled/skipped gates block it.
Fork/PR jobs use read-only repository permission and cannot log into the registry
or publish. Live evaluations remain separate opt-in bounded operator commands,
not mandatory CI secrets or evidence implied by deterministic regressions.
Local command/image proof does not mean the remote workflow or registry was run.

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
