# AGENTS.md — Developer & Autonomous Agent Guide to Countrydle

## 1. Project Overview & Purpose

**Countrydle** is a full-stack, daily geography guessing game platform inspired by *Wordle* and *20 Questions*. Players attempt to identify a secret geographical entity by asking natural language questions in English or Polish and submitting bounded guesses.

### Supported Game Modes
| Mode | Target Entities | Question Limit | Guess Limit | Client URL | API Route Prefix | Local Fact DB |
|---|---|---|---|---|---|---|
| **Countrydle** | World Countries | 10 | 3 | `/game` | `/countrydle` | `data/country_facts.sqlite` |
| **Wojewodztwodle** | 16 Polish Voivodeships (*województwa*) | 5 | 2 | `/wojewodztwa` | `/wojewodztwodle` | `data/voivodeship_facts.sqlite` |
| **Powiatdle** | 380 Polish Counties (*powiaty*) | 15 | 3 | `/powiaty` | `/powiatdle` | `data/powiat_facts.sqlite` |
| **US Statedle** | 50 US States | 8 | 3 | `/us-states` | `/us_statedle` | `data/us_state_facts.sqlite` |

### Core Mechanics
- **Daily Rotation**: Daily targets are rotated deterministically at midnight (00:00 UTC) via an APScheduler cron job (`server/utils/__init__.py`), pre-generating targets up to 5 days ahead.
- **Guest vs. Authenticated Play**:
  - **Guests**: State is tracked client-side in `localStorage` under `guess_game_{mode}_{date}`. Server endpoints accept guest submissions without requiring credentials.
  - **Authenticated Users**: State is persisted in PostgreSQL (`CountrydleState`, `PowiatdleState`, etc.), tracking streaks, points, question histories, and global/monthly leaderboards.
  - **Guest Data Sync**: When a guest logs in or registers, their local guest progress is synced to the backend via `POST /{mode}/sync`.
- **Fact Editing & Audit**: Admins can edit local facts through `/countrydle/admin/facts/...` with audit logs stored in PostgreSQL (`country_fact_change_log`).

---

## 2. System Architecture

```
                                  +---------------------------------------+
                                  |         Web Browser (Client)          |
                                  |  React 19 + TypeScript + Vite + Nginx |
                                  |  (Zustand Stores, Leaflet / SVG Maps) |
                                  +---------------------------------------+
                                                      |
                                     HTTP Requests (:5173 / :8080)
                                                      v
                                  +---------------------------------------+
                                  |         FastAPI Server (:8080)        |
                                  |  (Uvicorn, Async SQLAlchemy, Pydantic)|
                                  +---------------------------------------+
                                         /            |             \
                                        /             |              \
                                       v              v               v
            +----------------------------------+  +---------+   +-------------------+
            |  Primary: Local KB Answering     |  | Postgres|   | Fallback: Vector  |
            |  - Gemini 2.5 Flash Lite Planner |  |  pg17   |   | RAG Pipeline      |
            |  - Deterministic AST Evaluator   |  | (:5434) |   | - Qdrant (:6351)  |
            |  - SQLite Databases (data/*.db)  |  +---------+   | - OpenAI RAG      |
            +----------------------------------+                +-------------------+
```

### 2.1 Hybrid Question-Answering Pipeline

When a user submits a natural-language question (`POST /{mode}/question`):

1. **Step 1: Local Knowledge Base (Primary)**
   - Handled by `server/local_kb_question.py` (generic engine for Voivodeships, Powiaty, US States) and `server/countrydle/local_planner.py` + `server/countrydle/local_answering.py` (Countrydle).
   - The question is passed to Gemini (`LOCAL_QUESTION_MODEL`, defaults to `gemini-2.5-flash-lite`) which generates a structured JSON query plan containing abstract syntax trees (operators: `equals`, `contains`, `contains_exact`, `contains_partial`, `exists`, `greater_than`, `less_than`, `west_of`, `east_of`, `north_of`, `south_of`, `starts_with`, `ends_with`, `has_space`, boolean combinations `and`, `or`, `any`, `all`).
   - The executor evaluates the plan directly against local SQLite fact tables (`data/country_facts.sqlite`, etc.).
   - Returns a verified boolean answer with an exact human-readable fact explanation and relation tag (e.g. `local_kb:continent`, `local_kb:water_access`).
   - **Response time**: ~1.0–1.2s, deterministic, 0 hallucination.

2. **Step 2: Vector Search & LLM Fallback (Secondary)**
   - If the question is outside supported local facts (`plan.supported is False` or `execute_plan` returns `None`), the system falls back to Qdrant vector retrieval.
   - Text is embedded via OpenAI `text-embedding-3-small` (1536 dims), queried against Qdrant collections (`countries`, `powiaty`, `wojewodztwa`, `us_states`), and answered using OpenAI (`QUIZ_MODEL`, e.g. `gpt-4o-mini`).

---

## 3. Directory Cartography & Navigation Matrix

```
/home/melzak/dev/Countrydle/
├── client/                     # Frontend SPA (React 19, TypeScript, Vite)
│   ├── src/
│   │   ├── components/         # Map components (USStatesMap, WojewodztwaMap, PowiatyMap), QuestionInput, etc.
│   │   ├── pages/              # Game pages (GamePage, PowiatyGamePage, etc.), Auth, Admin
│   │   ├── services/api.ts     # Axios HTTP client and API service wrappers
│   │   ├── stores/             # Zustand stores (gameStore.ts, authStore.ts)
│   │   ├── types/index.ts      # TypeScript interfaces and game state definitions
│   │   ├── App.tsx             # React Router layout and guest sync listeners
│   │   └── i18n.ts             # Multilingual localization (EN / PL)
│   ├── Dockerfile              # Multi-stage Node 20 build -> Nginx Alpine
│   └── nginx.conf              # SPA routing fallback (try_files $uri /index.html)
│
├── server/                     # Backend API (FastAPI, Python 3.12)
│   ├── app.py                  # App factory, CORS, request middleware, route mounting
│   ├── game_logic.py           # Shared domain GameConfig, GameRules, GameState
│   ├── local_kb_question.py    # Generic Gemini planner + SQLite query evaluator
│   ├── countrydle/             # Countrydle mode (routes, crud, local planner & answerer, facts editor)
│   ├── wojewodztwodle/         # Wojewodztwodle mode routes, crud, utils
│   ├── powiatdle/              # Powiatdle mode routes, crud, utils
│   ├── us_statedle/            # US Statedle mode routes, crud, utils
│   ├── users/                  # User authentication (JWT, Google OAuth, password hashing)
│   ├── db/
│   │   ├── base.py / __init__.py  # Async SQLAlchemy engine & AsyncSessionLocal
│   │   ├── models/             # SQLAlchemy ORM models (Country, Day, Guess, Question, User, etc.)
│   │   └── repositories/       # Async repository classes for DB interactions
│   ├── qdrant/                 # Qdrant client, collections management, OpenAI embedding generation
│   ├── schemas/                # Pydantic schemas for request/response validation
│   ├── scripts/                # SQLite builder scripts and data enrichment scripts
│   ├── templates/              # Jinja2 HTML email templates
│   ├── tests/                  # Pytest test suite (274 tests)
│   ├── alembic/                # Alembic database migrations
│   ├── requirements.txt        # Python pip dependencies
│   └── Dockerfile              # Python 3.12-slim container image
│
├── data -> server/data/        # Symlinked data root containing SQLite DBs, CSVs, and markdown
│   ├── country_facts.sqlite    # SQLite fact base for World Countries
│   ├── voivodeship_facts.sqlite# SQLite fact base for Polish Voivodeships
│   ├── powiat_facts.sqlite     # SQLite fact base for Polish Counties
│   ├── us_state_facts.sqlite   # SQLite fact base for US States
│   ├── countries.csv           # Country definitions
│   ├── wojewodztwa.csv         # Voivodeship definitions
│   ├── powiaty.csv             # Powiat definitions
│   └── us_states.csv           # US State definitions
│
├── docker-compose.yml          # Primary development/local composition
├── docker-compose.prod.yml     # Production configuration
├── docker-compose.test-db-only.yml # Isolated PostgreSQL for host testing
└── nginx.conf                  # Production reverse proxy config
```

### Developer Navigation Matrix ("Where do I find / modify X?")
| Task | Target File(s) |
|---|---|
| Modify question evaluation or AST logic | `server/local_kb_question.py` & `server/countrydle/local_answering.py` |
| Add or adjust a supported game relation | `server/{mode}/utils.py` (`LOCAL_CONFIG.scalar_relations` / `list_relations`) |
| Add new entity facts | `server/scripts/build_{mode}_facts_sqlite.py` or Admin API (`server/countrydle/fact_editor.py`) |
| Modify game rules (questions/guesses limits) | `server/game_logic.py`, `server/{mode}/__init__.py`, `client/src/stores/gameStore.ts` |
| Update frontend UI or styling | `client/src/pages/`, `client/src/components/`, `client/src/index.css` |
| Add new API endpoint | `server/{mode}/__init__.py` and wire in `client/src/services/api.ts` |
| Modify database tables/columns | `server/db/models/`, then create migration with `alembic revision --autogenerate` |
| Change startup tasks (scheduler, migrations) | `server/utils/app.py` (`lifespan()`) and `server/utils/__init__.py` |

---

## 4. Environment Variables Configuration (`.env`)

The project uses a root `.env` file passed into Docker Compose:

```env
# PostgreSQL Database
POSTGRES_DB=guess_country
POSTGRES_USER=postgres
POSTGRES_PASSWORD=root
POSTGRES_PORT=5434   # Configurable host port (5434 avoids collisions with default 5432)
DATABASE_URL=postgresql+asyncpg://postgres:root@db:5432/guess_country

# AI & LLM Models
OPENAI_API_KEY=sk-...           # Required for Qdrant RAG fallback and vector embeddings
QUIZ_MODEL=gpt-4o-mini          # Model used for RAG fallback reasoning
GEMINI_API_KEY=AIzaSy...        # Required for Local KB Question Planner (Google Generative AI)
GEMINI_PROJECT_NUMBER=...
LOCAL_QUESTION_MODEL=gemini-2.5-flash-lite
GEMINI_QUESTION_MODEL=gemini-2.5-flash-lite

# Authentication & Security
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
GOOGLE_CLIENT_ID=...            # Google OAuth client ID

# Qdrant Vector Database
QDRANT_HOST=qdrant
QDRANT_PORT=6333
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_SIZE=1536

# Frontend Build Args
VITE_API_URL=http://localhost:8080
VITE_RYBBIT_SCRIPT_URL=https://tafeen.me/rybbit/api/script.js
VITE_RYBBIT_SITE_ID=YOUR_SITE_ID
VITE_GOOGLE_ADSENSE_ID=ca-pub-XXXXXXXXXXXXXXXX
```

---

## 5. How to Run Locally

### Option A: Running with Docker Compose (Full Stack in Containers)

#### Prerequisites
- Docker & Docker Compose v2+ installed.
- Ensure the `data` symlink exists at the root: `ln -s server/data data`.
- Valid `GEMINI_API_KEY` in `.env` for the local question answering engine.

#### Launching Services
```bash
# Start all 4 containers in detached mode
docker compose up -d

# Verify container status
docker compose ps

# View live unbuffered logs
docker compose logs -f backend
```

#### Exposed Host Ports
| Service | Host Port | Internal Container Port | Description |
|---|---|---|---|
| **frontend** | `http://localhost:5173` | `80` | Client application (React via Nginx) |
| **backend** | `http://localhost:8080` | `8080` | FastAPI server (`/docs` for OpenAPI UI) |
| **database** | `localhost:5434` | `5432` | PostgreSQL 17 + pgvector |
| **qdrant** | `http://localhost:6351` | `6333` | Qdrant vector database HTTP API |

#### Stopping Services
```bash
docker compose down
```

---

### Option B: Running Bare-Metal / Local Dev (Host Python + Vite)

Use this for active development with fast HMR (Hot Module Replacement) and debugger support:

#### 1. Start Background Services (Postgres & Qdrant only)
```bash
# Launch database and Qdrant in Docker
docker compose up -d db qdrant
```

#### 2. Backend (FastAPI with Uvicorn)
```bash
# From project root or server/ directory
cd server

# Activate your virtual environment (e.g. python 3.12)
source .venv/bin/activate  # or /tmp/countrydle-friend-venv/bin/activate

# Ensure dependencies are installed
pip install -r requirements.txt

# Run the development server with live reload
python -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload

# Or if running on a custom port (e.g. 8105) alongside Vite proxy:
python -m uvicorn app:app --host 127.0.0.1 --port 8105
```

#### 3. Frontend (React 19 + TypeScript + Vite)
```bash
cd client

# Install npm dependencies
npm install  # or bun install

# Start Vite dev server on port 5173 (proxies /api to the backend)
npm run dev -- --host 0.0.0.0 --port 5173

# If your backend runs on port 8105, configure Vite proxy:
API_PROXY_TARGET=http://127.0.0.1:8105 npm run dev -- --host 0.0.0.0 --port 5173
```

#### 4. Access Local Application
- **Frontend**: `http://localhost:5173`
- **Multiplayer Friend Duels**: `http://localhost:5173/friends`
- **FastAPI Interactive Docs**: `http://localhost:8080/docs` (or `http://localhost:8105/docs`)
---

## 6. Testing & Quality Assurance

### Running Backend Tests
All tests run inside the `backend` container or against the local environment:

```bash
# Run the complete test suite (274 tests)
docker compose exec backend pytest

# Run a specific test module
docker compose exec backend pytest tests/test_countrydle_local_kb.py -v

# Run other modes' local KB tests
docker compose exec backend pytest tests/test_local_kb_other_modes.py -v
```

### Smoke-Testing API Endpoints via cURL
```bash
# 1. Health & Server Info
curl -s http://localhost:8080/version
curl -s http://localhost:8080/time

# 2. Get Daily Game States
curl -s http://localhost:8080/countrydle/state
curl -s http://localhost:8080/wojewodztwodle/state
curl -s http://localhost:8080/powiatdle/state
curl -s http://localhost:8080/us_statedle/state

# 3. Ask Questions (Local KB Pipeline)
curl -s -X POST http://localhost:8080/countrydle/question \
  -H "Content-Type: application/json" \
  -d '{"question": "Is the country in Europe?"}'

curl -s -X POST http://localhost:8080/wojewodztwodle/question \
  -H "Content-Type: application/json" \
  -d '{"question": "Czy to województwo ma dostęp do morza?"}'

curl -s -X POST http://localhost:8080/powiatdle/question \
  -H "Content-Type: application/json" \
  -d '{"question": "Czy ten powiat ma tablice KR?"}'

curl -s -X POST http://localhost:8080/us_statedle/question \
  -H "Content-Type: application/json" \
  -d '{"question": "Does this state have access to the Pacific Ocean?"}'

# 4. Make Guesses
curl -s -X POST http://localhost:8080/countrydle/guess \
  -H "Content-Type: application/json" \
  -d '{"guess": "Poland"}'
```

---

## 7. Key Invariants & Modification Hazards

1. **Unary Operators in `local_kb_question.py`**:
   - Operators like `exists` and `has_space` take only a `left` operand. In `server/local_kb_question.py`, do **not** guard unary operators with `right is None` checks, as `right` will always evaluate to `None`.
2. **Data Directory Resolution**:
   - Both `server/data/` and root `data/` must point to the same content (`data -> server/data`).
   - In Python scripts and tests, resolve data directories by checking `(parents[1] / "data").exists()` before `(parents[2] / "data")` so code executes identically inside Docker (`/usr/src/app`) and on the host workstation.
3. **Database Migrations on Startup**:
   - Alembic migrations are executed automatically during FastAPI `lifespan` startup via `init_models()` in `server/utils/app.py`. There is no need to run manual `alembic upgrade head` inside container entrypoints.
4. **Unbuffered Logging**:
   - Ensure `PYTHONUNBUFFERED=1` is set in `docker-compose.yml` for the `backend` service so error tracebacks and question logs stream immediately to Docker stdout.
5. **Scheduler & UTC Time**:
   - Game targets rotate at midnight UTC (`00:00:00 UTC`). Never change the server timezone without coordinating with client countdown logic in `client/src/components/CountdownTimer.tsx`.
6. **Host Port Collisions**:
   - `docker-compose.yml` maps PostgreSQL to `${POSTGRES_PORT:-5432}:5432`. Set `POSTGRES_PORT=5434` in `.env` if host port 5432 is already bound by another database instance. Internal container-to-container communication always uses `db:5432`.

---

## 8. Git Workflow, Worktrees & Release Rules

All autonomous agents and developers working on Countrydle MUST strictly adhere to the following Git workflow:

### 8.1 Worktree & Branch Isolation
- **Always use Git Worktrees**: New features, refactors, and bugfixes MUST be developed in a separate worktree and dedicated branch.
  ```bash
  git worktree add ../Countrydle-<feature-name> -b feature/<feature-name>
  ```
- **Never commit directly to `main` during development**: Keep `main` clean, stable, and deployable at all times.

### 8.2 User Approval Gate (Mandatory)
- **No unapproved pushes or merges**: Agents must NEVER push branches to remote (`git push`) or merge branches into `main` without explicit approval from the user.
- **Approval Procedure**:
  1. Implement changes and verify with automated tests (`pytest`) and endpoint/UI checks.
  2. Clean up any temporary or debug artifacts.
  3. Present the diff summary, test results, and impact analysis to the user.
  4. Wait for explicit user confirmation before proceeding with merges or remote pushes.

### 8.3 Version Bumping on Every Change to `main`
- **Every change merged into `main` MUST bump the version** (e.g. `1.1.7` $\rightarrow$ `1.1.8` for fixes/refactors, `1.2.0` for new features).
- The version must be kept strictly synchronized across all three authoritative files:
  1. `server/version.py`:
     ```python
     SERVER_VERSION = "X.Y.Z"
     ```
  2. `client/package.json`:
     ```json
     "version": "X.Y.Z",
     ```
  3. `client/package-lock.json`:
     ```json
     "version": "X.Y.Z",
     ```
- The version bump must be committed with the message:
  ```bash
  git commit -m "chore: bump version to X.Y.Z"
  ```

### 8.4 Commit Message Standards
- Follow Conventional Commits:
  - `feat: <short description>` — New features (e.g., new game mode, new relation)
  - `fix: <short description>` — Bug fixes (e.g., query planner corrections, UI layout fixes)
  - `test: <short description>` — Test additions or updates
  - `chore: bump version to X.Y.Z` — Version increments
  - `docs: <short description>` — Documentation updates
