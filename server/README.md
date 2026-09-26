# Guess Your Country - Server

This is the backend server for the "Guess Your Country" (and related games) application. It is built using **FastAPI**, **PostgreSQL** (via SQLAlchemy + AsyncPG), and **Qdrant** (Vector Database).

## 🏗 Project Structure

```text
server/
├── alembic/                # Database migration configurations and versions
├── countrydle/             # Logic specific to the "Country" game
├── powiatdle/              # Logic specific to the "Powiat" game
├── us_statedle/            # Logic specific to the "US State" game
├── wojewodztwodle/         # Logic specific to the "Województwo" game
├── data/                   # Raw data files
│   ├── pages/              # Markdown files containing descriptions/context
│   └── *.csv               # CSV files mapping entities to markdown files
├── db/                     # Database layer
│   ├── models/             # SQLAlchemy ORM models (Tables)
│   ├── repositories/       # CRUD operations for database entities
│   └── base.py             # Database connection and session handling
├── qdrant/                 # Vector Database utilities (Embeddings, Search)
├── schemas/                # Pydantic models (Request/Response validation)
├── scripts/                # Utility scripts for data population and maintenance
├── utils/                  # General utilities (Auth, Email, etc.)
├── app.py                  # Main FastAPI application entry point
└── requirements.txt        # Python dependencies
```

## 🚀 Getting Started

### Prerequisites
1.  **Docker & Docker Compose**: For running PostgreSQL and Qdrant.
2.  **Python 3.11+**: For running the server and scripts.

### Environment Setup
Create a `.env` file in the `server/` directory:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/guess_country
QDRANT_HOST=localhost
QDRANT_PORT=6333
COLLECTION_NAME=countries
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_SIZE=1536
OPENAI_API_KEY=sk-...
QUIZ_MODEL=gpt-4o-mini
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Running Services
Start the database and vector store:
```bash
docker-compose up -d
```

### Running the Server
```bash
uvicorn app:app --reload --port 8080
```

---

## 💾 Database & Data Population

### 1. Resetting the Database
If you need to wipe everything and start fresh:

1.  **Drop all SQL tables:**
    ```bash
    python scripts/drop_all_tables.py
    ```
2.  **Clear Qdrant collections:**
    ```bash
    python scripts/clear_qdrant.py
    ```
3.  **Recreate SQL Schema (Migrations):**
    ```bash
    alembic upgrade head
    ```

### 2. Populating Data
The system uses CSV files in `server/data/` to populate the database and generate embeddings for Qdrant.

**CSV Format:**
Files (e.g., `countries.csv`, `us_states.csv`) must have two columns:
*   `name`: The name of the entity.
*   `md_file`: Relative path to the markdown file inside `server/data/` (e.g., `pages/Poland.md`).

**Run the population script:**
```bash
python scripts/populate_all.py
```
*This script reads the CSVs, creates DB entries, reads the Markdown files, chunks them, generates OpenAI embeddings, and upserts them to Qdrant.*

### Country availability and Kosovo rollout

Game eligibility is separate from factual geography and historical results.
Israel is excluded from all country-game targets and guesses. Azerbaijan is
excluded only from Europedle; it remains available worldwide and in Asia.
Kosovo is available worldwide, in Europe, in Flagdle, and in country friend duels.

Startup applies the PostgreSQL migration and provisions Kosovo's sourced SQLite
facts, CSV entry, and article into the existing mounted data directory. Repeated
startup preserves subsequent fact edits. Unplayed current/future disabled targets
are replaced; past results and recorded play are retained. An already-played
disabled daily target is unavailable for further play rather than silently
changing its answer. Active duels with disabled secrets are interrupted.

After deploying and starting the server, populate Kosovo's retrieval data from
the `server` directory (or inside the backend container):

```bash
python -m scripts.country_additions
```

This requires a funded `OPENAI_API_KEY` and the configured PostgreSQL/Qdrant
services. It generates real embeddings, stores fragments in PostgreSQL, and
upserts them into Qdrant's `countries` collection. Reruns reuse stored embeddings.
Failures are reported rather than replaced with fabricated vectors. This is
separate from startup so an exhausted embedding quota does not prevent the game
server from running. Until it succeeds, Kosovo has local facts but no new RAG
fragments.

---

## Daily question execution and accounting

- The configured Gemini/OpenAI model names are unchanged. `planner_protocol.py` supplies a nonrecursive JSON Schema: the provider emits an array of predicate/logical nodes with zero-based child indices. Prompts request children before parents and the root last; the compiler still accepts any valid node order. It validates routing, operator arity, allowed relations/entities, a single connected tree, and quantifier item scope before creating the existing executor AST or caching it. Malformed JSON, cycles, reused/unused nodes, and unexpected fields are errors, not repaired interpretations.
- The planner wire format has one decision: `route="local"` requires a plan, `route="fallback"` handles a clear predicate whose facts or required operations are unavailable locally, and `route="clarify"` rejects an underspecified question. Non-local routes require `plan=null`. The existing application/API fields `valid` and `supported` are derived from this decision; callers and HTTP responses retain their contract.
- Plan cache entries are isolated by game mode, normalized question, configured model, and planner contract version. Provider failures and malformed responses are not cached. A cached interpretation is still evaluated against the current target's facts.
- Planners allow 2,048 total output tokens. Gemini 2.5 Flash Lite planners use a bounded 1,024-token thinking budget to preserve compound predicates. Countrydle's daily/explicit-target fallback also allows 2,048 total output tokens and a 1,024-token thinking budget for Gemini 2.5 models. This adds latency and billed thought tokens without changing the configured model or adding retries. Other models retain their provider-default thinking settings. Existing usage diagnostics include actual `thought_tokens` when reported by Gemini.
- Generic-mode `any`/`all` binds neighboring entity rows only for configured same-type lists: `borders_powiat`, `borders_voivodeship` in Wojewodztwodle, and `borders_state`. `item.is_city_county`, for example, reads the neighboring county's classification, not its name or the hidden target's classification. Other lists and literal arrays remain primitive values accessible through `item.name`. Nested quantifiers retain the original target and restore the enclosing item scope. Missing facts remain unknown; decisive `and`/`or`/`any`/`all` results short-circuit without turning unknown into false.
- Question validity is independent of local fact and operator coverage: a precise historical, biographical, landmark, or character-position question can be valid but require fallback. Underspecified criteria require clarification; the planner must not invent a numeric threshold. Present membership and past membership remain distinct even when the organization is dissolved.
- Numeric predicates distinguish strict comparisons from `greater_than_or_equal` / `less_than_or_equal`. `has_space` and `has_hyphen` are unary text predicates; a hyphen is not an en/em dash. Country text predicates preserve punctuation and whitespace instead of normalizing punctuation into an empty search string. SQLite numeric boolean values compare numerically with JSON booleans; factual explanations use the stored property rather than the truth of a possibly inverted comparison.
- A valid question outside the local relations can continue through Qdrant retrieval and the existing answer model. Retrieval uses the planner's rewritten question when provided, otherwise the original player text; an omitted optional rewrite must not bypass fragment lookup.
- Countrydle does not pass planner coverage notes to the answer model as factual evidence. Missing SQLite coverage is not proof that a historical association or geographic concept does not exist. Fallback preserves the original predicate and may use reliable general knowledge when retrieved fragments are irrelevant; genuinely undetermined answers remain `null`.
- Country list relations require membership/nonemptiness operators, not scalar `equals`. Unknown historical-union names remain unknown; active organizations such as Benelux use `membership`, not the closed set of dissolved `historical_union` associations. Logical `and` is never rewritten to `or`. Explanations describe the evaluated entity and bound neighbor facts, including under negation.
- Cardinal region aliases retain their regional scope (`East Africa` → `Eastern Africa`), without conflating Southern Africa with the country South Africa. Generic ocean access covers recorded ocean coastlines; a coastline on a sea does not automatically imply a direct coastline on its parent ocean. Area/population comparisons explain the facts of both countries.
- Geographic plan literals match a whole supported category, not a substring: an unknown qualifier is never dropped to obtain a broader region. North/South America use complete continent coverage, and Middle East/Scandinavia retain their own stored classifications. Unrepresented directional quadrants use fallback rather than a guessed union of broad regions.
- Current `membership` and dissolved `historical_union` facts are separate. Historical associations are not copied into current memberships by the population script. Language prevalence is not inferred from legal official-language status; underspecified proximity, fame, and importance require clarification rather than an invented criterion.
- Country island status comes from the builder's sourced classification, not absence of land borders: shared-island countries can have borders, while Australia is a continent. The builder also restores active Benelux membership on rebuild.
- Synchronous model, embedding, Qdrant, and local SQLite work runs off the event loop. HTTP/SDK clients reuse connections and close during application shutdown; SQLAlchemy async sessions remain on the event-loop thread.
- Only a valid question with an actual boolean answer consumes a question: both `true` and `false` count. `null`, invalid questions, malformed provider answers, and technical failures do not enter the counted history or spend a turn. Provider strings such as `"false"` are not coerced into accepted answers.
- Countrydle returns HTTP `503` for valid-but-unverified answers and operational/provider failures, without recording a question or charging a turn. These are distinct from genuinely invalid questions, which retain the existing HTTP `200`, `valid=false` rejection response.
- Authenticated question persistence and quota consumption share a PostgreSQL transaction, with a refreshed, locked quota check after provider work. Concurrent requests cannot both consume the last slot. Guest imports keep guess insertion and state updates in the same locked transaction, preventing duplicate imports. Offloading provider work does not itself release request-scoped database connections; read transactions may still remain open while the provider responds.
- Guest question totals are rebuilt from resolved history, not trusted local counters. Synchronization only claims resolved, unowned question records from the requested day. The client retains snapshots when synchronization fails and does not delete a newer snapshot written while a request was in flight.
- Flagdle keeps unlimited verified questions, including after the guessing game ends; unresolved attempts still do not count as participation.

Set `QUESTION_TEST_DATABASE_URL` to an explicitly disposable PostgreSQL database
(`FRIEND_TEST_DATABASE_URL` is also accepted). Accounting regressions create and
remove isolated schemas, never using `DATABASE_URL` as a fallback:

```bash
python -m pytest -q tests/test_question_accounting.py tests/test_question_nonblocking.py tests/test_planner_contract.py tests/test_plan_cache.py
```

These regressions use controlled provider responses; they do not measure live
model accuracy or latency. SQLite regressions require the normal local fact data
and country-additions provisioning.

## County border facts

Powiatdle uses the repository snapshot `powiatdle/local_kb/borders.json`, derived
from full-resolution [GUGiK/PRG county polygons](https://www.geoportal.gov.pl/pl/dane/panstwowy-rejestr-granic-prg/).
Counties are joined by their four-digit TERYT codes, not map feature IDs or
potentially ambiguous names. A border requires a shared line of positive length;
point contacts do not count. Polygon holes and detached parts are preserved.
The snapshot records the WFS URL, response timestamp and source SHA-256.

**Before deploying this change against an existing SQLite database**, run from
`server/` with that environment's actual fact database mounted:

```bash
python scripts/build_powiat_facts_sqlite.py --refresh-borders --output data/powiat_facts.sqlite
```

This validates the snapshot against the complete county catalog, then replaces
county borders, derived borders with other voivodeships, the name-alias index and
coverage markers. Other facts and manual edits to them are preserved. The default
builder without `--refresh-borders` recreates the whole database instead; use it
only when a full rebuild is intended. Deploying code alone does not update an
existing mounted SQLite file.

Exact county references accept catalog-derived Polish inflections such as
`częstochowskim` and `pszczyńskim`. City counties remain distinct from the
surrounding land counties. Ambiguous or unrecognized names and unverified border
lists are not interpreted as negative facts by the local evaluator; the existing
fallback policy applies. Verified empty cross-voivodeship lists can answer `false`.

Questions about a neighboring county's properties use a quantified predicate,
not merely `exists(borders_powiat)`: the latter only proves that some neighbor
exists. A city-or-city-neighbor question combines the target's `is_city_county`
with `any` neighbor whose `is_city_county` is true. Rural county names retain
their adjective and `Powiat` prefix; a county's seat must not replace its identity.

To regenerate the snapshot from a new official response:

```bash
curl --fail --location --output /tmp/prg-powiaty.gml \
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms%3AA02_Granice_powiatow&count=380&srsName=urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180'
python scripts/build_powiat_borders.py --input /tmp/prg-powiaty.gml
python scripts/build_powiat_facts_sqlite.py --refresh-borders
python -m pytest -q tests/test_powiat_borders.py tests/test_powiat_names.py tests/test_powiat_border_source.py
```

## Answer Reports

After a game ends (win or loss), players can report a saved question result from its history card in any game mode. Reporting controls are hidden while the game is in progress. A report requires a comment of 1–2,000 characters after trimming whitespace; reporting does not change the answer, score, or remaining turns.

- `POST /answer-reports` accepts `mode`, `question_id`, `comment`, and an optional `report_token`. Modes are `countrydle`, `us_statedle`, `powiatdle`, and `wojewodztwodle`. Success returns only `{ "id": ... }`, never the hidden target or diagnostic context.
- Question responses include a signed `report_token` for guests. The token is bound to the mode and saved question ID and remains usable after guest progress is synced to an account. An authenticated question owner can also report without a token. Older guest histories without a token cannot be reported; synthetic unsaved error responses are not reportable.
- The server snapshots the original and interpreted question, validity, answer, explanation, retrieval context, game date, target, and recorded server version from the database. Clients cannot supply or override this context.
- Each saved question can have one report. Repeat or concurrent submissions return `409`; inaccessible or missing questions return `404`.
- Admin's **Reports** tab lists reports with status/mode filters and pagination. `GET /admin/answer-reports` supports `status=open|reviewed|all`, optional `mode`, `page`, and `limit` (maximum 100). `PATCH /admin/answer-reports/{id}` accepts `{ "reviewed": true }` to mark reviewed or `false` to reopen. Both endpoints require admin authentication.

The `answer_reports` table is created by Alembic revision `4c9f2a1b8d60`, applied through the existing startup migration process. Report tokens use `SECRET_KEY`; keep it stable across replicas. Rotating it invalidates previously issued guest report tokens.

### Admin question tests

The admin **Test pytań** tab evaluates a question against an explicitly selected entity in any of the nine game modes. **Testuj pytanie** on a report prefills its original question and selects the target only when its name matches exactly one entity. Historical and current results are shown separately; automatic comparison requires the same mode, uniquely matched target, and original question.

- `GET /admin/question-tests/entities?mode=...` lists entity names and actual PostgreSQL IDs, with continent-specific membership where applicable.
- `POST /admin/question-tests` accepts `{ "mode": "powiatdle", "entity_id": 123, "question": "Czy ten powiat ma tablice ST?" }`. The entity ID must be a positive integer; questions are trimmed, nonempty, and limited to 100 characters. Both endpoints require admin authentication.
- Evaluation reuses the daily question pipeline with fresh, uncached planning and current facts/models. Flagdle remains local-only. The response includes validity, answer, interpretation, explanation, source, context, structured plan, server version, and duration. Operational failures return an error rather than a fabricated answer.
- `diagnostics` exposes measured planner, local evaluation, retrieval, and fallback durations in milliseconds. Model diagnostics include provider/model, planner contract version, cache hit status, and token usage when supplied by the provider. Missing measurements remain `null`; token counts are not estimated from text. The **Czasy etapów i zużycie tokenów (JSON)** disclosure displays these values without prompts, messages, credentials, or raw provider responses.
- Tests do not create daily targets or save questions, attempts, progress, points, report status, or Qdrant data. They do not replay a historical server version and require no new database migration.

### Admin cache monitoring

The admin **Cache** tab displays planner-cache hits, misses, hit rate, stored plans, and capacity from the existing aggregate `GET /cache-stats` endpoint. It is read-only: no entries, question text, or cache-clearing controls are exposed.

- Automatic refresh runs 15 seconds after each completed request while the tab is open. It can be paused; manual refresh remains available. Requests time out after 10 seconds and are cancelled when leaving the tab.
- Empty counters show no hit rate rather than an artificial success/failure score. Failed refreshes retain the last successful values with a stale-data warning and the last-read timestamp.
- Statistics are process-local, not aggregated across workers. Counts and entries reset on process restart or cache clearing, not at midnight; entries have no TTL. At capacity, LRU eviction replaces the least recently used plans.
- A hit avoids planner generation, but a cached plan may still require AI fallback. A miss does not guarantee a paid model call. Admin question tests and friend-duel questions bypass this cache, and these counters do not measure Google's token caching or billing.

---

## Player profiles

`GET /users/{username}/stats` exposes daily statistics for Countrydle, Powiatdle,
US Statedle, Województwodle, Flagdle, and each continent, plus casual friend-match
results. Daily mode objects include active games, completed games, wins, points,
win rate, current and best streaks, averages, and completed-game history ordered
newest puzzle date first. Today's and future targets are hidden from public
profiles using the UTC puzzle date. Friend-match history includes only finished
solved, forfeit, and draw results; it has no points or leaderboard ranking.

## Patch notes

The public **More → Patch notes** page at `/patch-notes` shows English release history stored in PostgreSQL. Entries display their release version, title, plain-text changes, and UTC publication date; historical entries do not imply which version is currently running.

- `GET /patch-notes?page=1&limit=10` returns `{ "items": [...], "total": 0, "page": 1, "limit": 10 }`. Each item has `id`, `version`, `title`, `body`, and `published_at`. Pages start at 1; the maximum page size is 50. Entries are ordered newest-first with a stable ID tiebreak.
- `patch_notes` has one immutable publication per version. Identical publication retries preserve its original timestamp; conflicting content is rejected. There is no public write endpoint.
- `server/release_notes.json` contains the English release text and must match `SERVER_VERSION`. Application startup and migrations never publish release announcements.
- Migration `f1e2d3c4b5a6` creates the table without inserting release history. Exact operational instructions are deliberately kept in the ignored, local-only `DEPLOY.local.md`, not in tracked documentation.

---

## Active participation counts

Blog player statistics and the admin overview use `db/repositories/participation.py`.

A player must have an accepted question or guess for that puzzle; merely opening
the game or having a daily state created by the streak job does not count.
Blog statistics are scoped to the article's Countrydle puzzle date and are
recomputed when an existing article is fetched, without rewriting its text.

Guests are identified by a signed, HttpOnly, SameSite=Lax `guest_identity` cookie
with a two-day lifetime (Secure on HTTPS). Opening a solo game's state endpoint
establishes the cookie but creates no participation row. Accepted actions update
`guest_participations` in the same database transaction as the saved action.
Guest-to-account sync links that browser's puzzle so it is not counted twice.
No IP address or browser fingerprint is used.

The admin overview covers all nine daily challenges. Its player total counts
distinct accounts and guest browser identities across modes; games won and the
win rate are calculated per puzzle played, not per unique person. These are
browser/account counts, not a claim to identify real people: clearing or expiring
cookies, using multiple browsers, or sharing a browser affects uniqueness.
Historical anonymous guesses have no usable player identity and are **not**
backfilled as people. Historical guest participation therefore remains incomplete.

Alembic revision `d9e0f1a2b3c4` adds the guest table and
`flagdle_states.questions_asked`. Apply it through the normal migration process
before running this code; do not run the new code against the old schema.
The PostgreSQL regression tests require an explicitly disposable
`PARTICIPATION_TEST_DATABASE_URL`; they create and remove isolated schemas:

```bash
python -m pytest -q tests/test_guest_participation.py tests/test_guest_participation_routes.py tests/test_participation_reporting.py tests/test_blog.py
```

### Leaderboards

The leaderboard page covers Countrydle, Powiatdle, US States, Województwa,
Europe, Asia, Africa, Americas, and Flagdle. A compact game picker groups the
nine daily challenges into World & flags, Continents, and Regional games.
Username search covers every eligible player, not just the current 25-row page,
and preserves global ranks. Signed-in players can use **Find me** to jump to
their highlighted row.

Daily-game endpoints accept `type=monthly|average`:

- `/countrydle/statistics/leaderboard`
- `/powiatdle/leaderboard`, `/us_statedle/leaderboard`, `/wojewodztwodle/leaderboard`
- `/continental/{europe|asia|africa|americas}/leaderboard`
- `/flagdle/leaderboard`

Rows contain `id`, `username`, total `points`, `wins`, `games_played`, and
`average_points`. Monthly rankings include actual play in the current UTC
calendar month, including active zero-point players; empty daily states do not
qualify. Average rankings use completed, active games across all time, with at
least five games required for the classic modes and Flagdle, or three for each
continental mode. The selected score determines rank, then wins, then user ID.
Continental totals are isolated by continent.

Friend games are casual: no points awards and no public leaderboard or ranked
win-rate competition. Their match results remain part of the friend-game flow,
separate from daily-game scoring and rankings.

Rankings remain account-based. Guest participation contributes to statistics,
not anonymous ranked entries.

### Daily-game scoring and guest sync

Streak bonuses count consecutive winning puzzle dates in the same game (and
the same continent), ending yesterday. The current win is excluded from the
history before its bonus is calculated; losses and missing dates break the
streak. Playing another mode does not increase that mode's scoring bonus.

Guest sync validates attempt counts, budgets, the final winning guess, and
terminal state before awarding points. Timing comes from the final submitted
attempt, and the client retains it through login. Flagdle shows calculated
guest points and refreshes authenticated results from the persisted server
state. Repeating a completed sync does not award points again.

These corrections apply to new scoring and sync operations; historical
awards are not recalculated.

---

## 🛠 How to Add a New Game

To add a new game mode (e.g., "Cities"), follow these steps:

### 1. Prepare Data
1.  Add `cities.csv` to `server/data/`. Columns: `name`, `md_file`.
2.  Add corresponding Markdown files to `server/data/pages/`.

### 2. Create Database Models
Create `server/db/models/city.py` and `server/db/models/citydle.py`.
*   **Entity Model (`city.py`)**: The table storing the list of cities.
*   **Game Models (`citydle.py`)**:
    *   `CitydleDay`: Which city is the target for a specific date.
    *   `CitydleState`: User progress for that day.
    *   `CitydleGuess`: History of user guesses.
    *   `CitydleQuestion`: History of user questions (RAG).
*   **Export**: Add them to `server/db/models/__init__.py`.

### 3. Create Schemas
Create `server/schemas/citydle.py`. Define Pydantic models for:
*   `CityGuessCreate` / `CityGuessDisplay`
*   `CityQuestionCreate` / `CityQuestionDisplay`
*   `CitydleStateResponse`

### 4. Create Repositories
Create `server/db/repositories/citydle.py`. Implement classes for:
*   `CityRepository`: `get_all`, `get_by_name`.
*   `CitydleDayRepository`: `get_today`, `generate_new`.
*   `CitydleStateRepository`: `get_state`, `create_state`.
*   `CitydleGuessRepository`: `add_guess`.
*   `CitydleQuestionRepository`: `create_question`.

### 5. Implement Game Logic (RAG)
Create `server/citydle/utils.py`.
*   Implement `enhance_question`: Uses LLM to validate/rephrase user input.
*   Implement `ask_question`:
    1.  Calls `qdrant.utils.get_fragments_matching_question` filtering by `city_id`.
    2.  Sends retrieved context + question to LLM.
    3.  Returns the answer.

### 6. Create Population Script
Create `server/scripts/populate_cities.py`.
*   Read `cities.csv`.
*   Insert into SQL DB.
*   Read Markdown -> Split -> Embed -> Upsert to Qdrant (Payload: `city_id`, `fragment_text`).
*   Import and add this function to `server/scripts/populate_all.py`.

### 7. Database Migration
Generate the new tables:
```bash
alembic revision --autogenerate -m "add_citydle"
alembic upgrade head
```

### 8. API Router
Create `server/citydle/__init__.py` (Router).
*   Define endpoints: `/state`, `/guess`, `/question`.
*   Register the router in `server/app.py`.

---

## 🧠 Key Concepts

### RAG (Retrieval-Augmented Generation)
The game uses RAG to answer "True/False" questions about entities.
1.  **Ingestion**: Markdown files are split into chunks and vectorized (OpenAI Embeddings). Stored in Qdrant.
2.  **Retrieval**: When a user asks a question, it is vectorized. We search Qdrant for the most similar chunks **filtered by the specific entity ID** (e.g., `us_state_id=5`).
3.  **Generation**: The retrieved text chunks are passed as "Context" to GPT-4o-mini, which answers the user's question based *only* on that context.

### Game State
*   **Day Table**: Determines the "Answer" for the current 24h period.
*   **State Table**: Tracks a specific user's progress (guesses made, questions asked, won/lost) for that specific Day.
