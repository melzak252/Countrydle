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

---

## Answer Reports

Players can report a saved question result from its history card in any game mode. A report requires a comment of 1–2,000 characters after trimming whitespace; reporting does not change the answer, score, or remaining turns.

- `POST /answer-reports` accepts `mode`, `question_id`, `comment`, and an optional `report_token`. Modes are `countrydle`, `us_statedle`, `powiatdle`, and `wojewodztwodle`. Success returns only `{ "id": ... }`, never the hidden target or diagnostic context.
- Question responses include a signed `report_token` for guests. The token is bound to the mode and saved question ID and remains usable after guest progress is synced to an account. An authenticated question owner can also report without a token. Older guest histories without a token cannot be reported; synthetic unsaved error responses are not reportable.
- The server snapshots the original and interpreted question, validity, answer, explanation, retrieval context, game date, target, and recorded server version from the database. Clients cannot supply or override this context.
- Each saved question can have one report. Repeat or concurrent submissions return `409`; inaccessible or missing questions return `404`.
- Admin's **Reports** tab lists reports with status/mode filters and pagination. `GET /admin/answer-reports` supports `status=open|reviewed|all`, optional `mode`, `page`, and `limit` (maximum 100). `PATCH /admin/answer-reports/{id}` accepts `{ "reviewed": true }` to mark reviewed or `false` to reopen. Both endpoints require admin authentication.

The `answer_reports` table is created by Alembic revision `4c9f2a1b8d60`, applied through the existing startup migration process. Report tokens use `SECRET_KEY`; keep it stable across replicas. Rotating it invalidates previously issued guest report tokens.

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
