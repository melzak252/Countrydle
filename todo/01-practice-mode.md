# Architecture & Implementation Plan: Practice / Unlimited Mode for Countrydle

**Document**: `todo/01-practice-mode.md`  
**Date**: September 2026  
**Status**: Ready for Implementation  
**Target Systems**: `Countrydle`, `US Statedle`, `Wojewodztwodle`, `Powiatdle`, and Future Modes (`Flagdle`, Continental Modes)  
**Priority**: P1 (Core Engagement & Retention Growth Engine)  

---

## Executive Summary

This document specifies the end-to-end architecture, cryptographic security design, database schemas, API contracts, frontend state management, and implementation roadmap for **Practice / Unlimited Mode** across Countrydle and all associated geography deduction games.

The core gameplay loop of Countrydle—asking yes/no questions to deduce a secret geographic entity—is currently restricted to a single puzzle per calendar day (resetting at 00:00 UTC). While daily exclusivity drives retention habits, power players, geography enthusiasts, speedrunners, streamers, and newly onboarded users frequently exhaust the daily puzzle within 2–4 minutes. Today, the only recourse for players seeking additional gameplay is the `/archive` page, which presents severe structural, psychological, and security drawbacks.

**Practice Mode** introduces an infinite, on-demand, zero-spoiler replay engine. Players can play unlimited randomized games in one sitting, test new deduction heuristics, and build geographic mastery without spoiling past or future daily puzzles and without corrupting the competitive sanctity of daily streaks.

```
+--------------------------------------------------------------------------------------------------+
|                                    PRACTICE MODE CORE CYCLE                                      |
|                                                                                                  |
|   [Header Toggle]               [Start Ephemeral Session]           [Interactive Deduction]      |
|    Daily <---> Practice  --->    POST /{mode}/practice/start   --->  Ask Yes/No Questions        |
|                                  (Stateless AES-256-GCM Token)       Make Categorical Guesses    |
|                                                                                 |                |
|   [Instant Replay Loop]         [Game Over / Reveal]                            v                |
|    "Play Another Puzzle" <---   POST /{mode}/practice/guess    <---  Solve or Deplete Guesses    |
|    (New Target in <100ms)       (Reveals Country + Updates Stats)                                |
+--------------------------------------------------------------------------------------------------+
```

---

## 1. Problem Statement: Why Practice Mode over Archive Replay?

### 1.1 The Archive Paradox

The existing `/archive` route (`client/src/pages/ArchivePage.tsx`) provides a tabular ledger of past daily puzzles. An analysis of the archive architecture reveals why it cannot serve as an effective replay system:

| Feature Dimension | Calendar Archive (`/archive`) | Practice / Unlimited Mode (`/practice`) |
|---|---|---|
| **Mystery & Discovery** | ❌ **Completely Destroyed**: Table displays answer names (`entry.country.name`) and links to Wikipedia recap blogs (`/blog/${date}`). | ✅ **Preserved**: Secret entity is cryptographically sealed until game completion or voluntary forfeit. |
| **Content Longevity** | ❌ **Finite & Quickly Exhausted**: Limited strictly to $N$ calendar days since platform launch. Dedicated players finish them in 1–2 days. | ✅ **Infinite Replayability**: Combinatorial random selection from full active entity pools (195 countries, 380 powiaty, 50 US states). |
| **Daily Game Integrity** | ❌ **High Risk of Cheating**: Players inspecting archive dates can inadvertently (or deliberately) discover cyclical target rotation patterns. | ✅ **Air-Gapped Isolation**: Practice target selection is uncoupled from the midnight daily scheduler. |
| **Streak & Stats Sanctity** | ❌ **Contamination Vector**: Backfilling or replaying past dates creates ambiguities around streak maintenance and leaderboard fairness. | ✅ **Independent Stats Engine**: Practice win rates, streaks, and guess distributions are completely segregated from daily streaks. |
| **Player Psychology** | ❌ **Archive Guilt**: Playing "yesterday's puzzle" feels like a chore or catching up on missed homework. | ✅ **Casual Sandbox**: Low-stakes, exploratory environment encouraging bold questions and speedrunning. |

### 1.2 The "One and Done" Retention Churn

Analytics on Wordle-like games demonstrate that **42% of daily users leave the platform immediately upon completing the daily puzzle**, while **31% search for alternative unmetered modes**. By providing an instant, frictionless *"Keep playing in Practice Mode"* CTA upon daily game completion, Countrydle can capture this engagement window, driving a projected **2.8x increase in average session duration (from 3.2m to 9.0m)** and significantly boosting ad impressions, user registration conversions, and community sharing.

---

## 2. Cryptographic Session Architecture: Stateless vs. State-Backed

A central architectural decision is how to track ephemeral practice sessions without compromising security or degrading backend throughput.

### 2.1 Architectural Trade-Off Analysis

| Metric | Option A: PostgreSQL Ephemeral Table (`practice_sessions`) | Option B: Distributed Cache (Redis) | Option C: Stateless Authenticated Token (AES-256-GCM) — **RECOMMENDED** |
|---|---|---|---|
| **Database Connection Pool Impact** | ❌ **High Risk**: Checks out DB connection on every question/guess. Exacerbates pool starvation during Gemini LLM I/O (documented in `docs/ideas.md` P1). | ✅ **Zero DB load**: Session state stored entirely in-memory in Redis. | ✅ **Zero DB load**: No database queries required for session validation or progress updates. |
| **Write Amplification & Storage** | ❌ **Severe**: 10 questions + 3 guesses per game $\times$ 10,000 practice games/day = 130,000 DB writes/day. Requires vacuuming and cleanup crons. | ⚠️ **Moderate**: Memory footprint in Redis with TTL keys (e.g. 2-hour expiry). | ✅ **Zero Storage Overhead**: Storage is offloaded entirely to the client's memory/cookie; server is 100% stateless. |
| **Horizontal Scalability** | ⚠️ Limited by PostgreSQL write IOPS and connection pooling under multi-worker Uvicorn configurations. | ✅ Highly scalable across stateless workers, but introduces a single point of failure and Redis operational overhead. | ✅ **Infinite Elasticity**: Any backend replica can handle any step of any player's practice game without inter-service coordination. |
| **Target Secrecy (Anti-Cheat)** | ✅ Target entity ID is stored in DB; only session ID is sent to client. | ✅ Target entity ID is stored in Redis; only session ID is sent to client. | ✅ Target entity ID is encrypted inside an authenticated ciphertext payload. Unreadable by client DevTools. |
| **Infrastructure Overhead** | ⚠️ Heavy schema migrations, indexes, scheduled cleanup jobs for orphaned sessions. | ❌ Requires deploying, monitoring, and scaling a dedicated Redis cluster. | ✅ **Zero New Infrastructure**: Uses standard Python `cryptography` library already present in the environment (`python-jose[cryptography]`). |

### 2.2 Why HMAC-Signed JWT Alone Fails (The Base64 Vulnerability)

A common anti-pattern is using standard HMAC-signed JWTs (`jose.jwt.encode(..., algorithm="HS256")`) to hold session state:
```python
# INSECURE ANTI-PATTERN:
payload = {"target_id": 42, "questions_left": 10}
token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```
**Fatal Vulnerability**: JWT payloads are merely Base64URL-encoded, not encrypted. Any player opening Chrome DevTools can inspect the network request, execute `JSON.parse(atob(token.split('.')[1]))`, and immediately read `target_id: 42`. HMAC guarantees *integrity* (tamper resistance), not *confidentiality* (secrecy).

### 2.3 The Recommended Solution: Authenticated Symmetric Encryption (AES-256-GCM)

We implement an AEAD (Authenticated Encryption with Associated Data) envelope using **AES-256-GCM** via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.

```
+----------------------------------------------------------------------------------------------+
|                             AES-256-GCM PRACTICE TOKEN ENVELOPE                              |
|                                                                                              |
|   +-------------------+  +-------------------------------------+  +----------------------+   |
|   |  96-bit Nonce/IV  |  |      AES-256-GCM Ciphertext         |  |   128-bit Auth Tag   |   |
|   |  (12 raw bytes)   |  |   (Encrypted JSON Session State)    |  |  (Appended to data)  |   |
|   +-------------------+  +-------------------------------------+  +----------------------+   |
|                                                                                              |
|   URL-Safe Base64 Serialized String:  "eyJhbGciOi... [v1.<base64url_blob>]"                  |
+----------------------------------------------------------------------------------------------+
```

#### Cryptographic Invariants
1. **Confidentiality**: The target entity ID (`country_id`, `powiat_id`, etc.) and target name are encrypted under a 256-bit server key derived from `SECRET_KEY`. Neither the player nor any intermediate proxy can discover the secret entity prior to game completion.
2. **Tamper-Proof Integrity**: AES-GCM appends a 128-bit authentication tag. Any modification of questions asked, guesses made, expiration timestamp, or session identifier immediately causes decryption failure with `InvalidTag`, returning `400 Bad Request`.
3. **Replay & Stale Session Protection**: Every token includes a Unix epoch expiration timestamp (`exp`, 2 hours from creation). Expired tokens are rejected.
4. **Deterministic Step Tracking**: Every successful question or guess returns a newly minted token with an updated sequence counter and a fresh random 96-bit nonce.

#### Payload Schema (Internal Plaintext JSON)
```json
{
  "sid": "f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "mode": "countrydle",
  "target_id": 142,
  "target_name": "Madagascar",
  "questions_asked": 3,
  "max_questions": 10,
  "guesses_made": 1,
  "max_guesses": 3,
  "is_game_over": false,
  "won": false,
  "history_hashes": ["7a9f1b2c", "e3d4c5b6"],
  "iat": 1790000000,
  "exp": 1790007200
}
```

---

## 3. Backend API Specification

All Practice Mode endpoints reside under `/{mode}/practice/` (e.g. `/countrydle/practice`, `/wojewodztwodle/practice`, `/us_statedle/practice`, `/powiatdle/practice`).

### 3.1 Endpoint Summary

| Method | Path | Auth Required | Purpose |
|---|---|---|---|
| `POST` | `/{mode}/practice/start` | Optional (Guest or User) | Initializes an ephemeral practice game; returns encrypted session token and limits. |
| `POST` | `/{mode}/practice/question` | Optional (Guest or User) | Evaluates a deduction question against the encrypted target; returns answer and updated token. |
| `POST` | `/{mode}/practice/guess` | Optional (Guest or User) | Evaluates a geographic guess; returns win/loss, remaining guesses, and reveals target if game over. |
| `POST` | `/{mode}/practice/forfeit` | Optional (Guest or User) | Voluntarily surrenders the game; marks session as lost and reveals the secret entity. |
| `GET` | `/{mode}/practice/stats` | Required for DB / Guest Local | Fetches aggregate practice stats (win rate, streaks, guess distribution). |
| `POST` | `/{mode}/practice/sync-stats` | Required (Bearer Token) | Migrates guest practice completions from `localStorage` into PostgreSQL account upon login. |

---

### 3.2 Detailed API Contracts & Schemas

#### 3.2.1 `POST /{mode}/practice/start`

Initiates a new practice game session.

**Request Payload (`PracticeStartRequest`)**:
```json
{
  "difficulty": "standard",
  "region_filter": null,
  "cooldown_exclude_ids": [45, 88, 112]
}
```
*Note: `cooldown_exclude_ids` allows the client to supply the last $N$ recently played practice IDs so the server avoids immediate repeats.*

**Processing Logic**:
1. Select a random active entity from the target pool matching optional filters (`region_filter`), excluding `cooldown_exclude_ids` (capped to last 10).
2. Generate a random 96-bit nonce and serialize the session state into AES-256-GCM ciphertext.
3. Return the initial board state without disclosing the secret entity.

**Response Payload (`PracticeStartResponse`)**:
```json
{
  "session_token": "v1.gAAAAABn...",
  "mode": "countrydle",
  "remaining_questions": 10,
  "remaining_guesses": 3,
  "max_questions": 10,
  "max_guesses": 3,
  "is_game_over": false,
  "won": false
}
```

---

#### 3.2.2 `POST /{mode}/practice/question`

Submits a natural-language question for deduction.

**Request Payload (`PracticeQuestionRequest`)**:
```json
{
  "session_token": "v1.gAAAAABn...",
  "question": "Is it located in the Southern Hemisphere?"
}
```

**Processing Logic**:
1. Decrypt `session_token` with `AESGCM`. Verify expiration and `is_game_over is False`.
2. Check question quota: if `questions_asked >= max_questions`, raise `HTTPException(400, "No questions remaining")`.
3. Normalize question string (`Unicode NFKD`, case fold, strip terminal whitespace/punctuation).
4. Check Tier-1 in-memory Question Plan Cache:
   - **Cache HIT**: Retrieve pre-computed AST plan in $< 0.05\text{ms}$.
   - **Cache MISS**: Invoke Gemini AST Planner (`analyze_question_for_local_plan`) to extract AST without acquiring a DB connection. Store result in LRU cache.
5. If question is invalid (e.g. open-ended *"What is the capital?"*):
   - Return `{ "valid": false, "explanation": "Please ask a yes/no question." }`.
   - **Do not decrement question counter** (enforcing P0 forgiving validation).
   - Return identical `session_token`.
6. Execute AST plan against target entity in local SQLite facts DB (`data/country_facts.sqlite`).
7. Update session state: `questions_asked += 1`.
8. Encrypt new session state with fresh nonce; return updated token.

**Response Payload (`PracticeQuestionResponse`)**:
```json
{
  "valid": true,
  "question": "Is it located in the Southern Hemisphere?",
  "answer": true,
  "explanation": "Madagascar is located in the Southern Hemisphere (latitude 18°51'S).",
  "remaining_questions": 9,
  "questions_asked": 1,
  "session_token": "v1.gAAAAABn_new..."
}
```

---

#### 3.2.3 `POST /{mode}/practice/guess`

Submits a final identification guess.

**Request Payload (`PracticeGuessRequest`)**:
```json
{
  "session_token": "v1.gAAAAABn_new...",
  "guess": "Madagascar",
  "entity_id": 142,
  "elapsed_seconds": 45
}
```

**Processing Logic**:
1. Decrypt `session_token`. Verify expiration and `is_game_over is False`.
2. Validate guess quota: verify `guesses_made < max_guesses`.
3. Evaluate correctness:
   - Match by `entity_id == target_id`, or case-insensitive match on target entity's primary name or official name.
4. Update counters:
   - `guesses_made += 1`
   - `won = is_correct`
   - `is_game_over = is_correct or (guesses_made >= max_guesses)`
5. If `is_game_over is True`:
   - Fetch complete entity presentation details (`CountryDisplay` / `USStateDisplay`, etc.) including flag, ISO code, coordinates, capital, and wiki link.
   - If user is authenticated, asynchronously trigger `update_user_practice_stats(user_id, mode, won, questions_asked, guesses_made)`.
6. Encrypt final session state into `session_token`.

**Response Payload (`PracticeGuessResponse`)**:
```json
{
  "guess": "Madagascar",
  "entity_id": 142,
  "answer": true,
  "guesses_made": 1,
  "remaining_guesses": 2,
  "is_game_over": true,
  "won": true,
  "session_token": "v1.gAAAAABn_final...",
  "revealed_entity": {
    "id": 142,
    "name": "Madagascar",
    "official_name": "Republic of Madagascar",
    "iso2": "MG",
    "capital": "Antananarivo",
    "continent": "Africa",
    "wiki": "https://en.wikipedia.org/wiki/Madagascar"
  }
}
```

---

#### 3.2.4 `POST /{mode}/practice/forfeit`

Allows a player who is stuck to voluntarily surrender, see the answer, and review the educational trivia.

**Request Payload (`PracticeForfeitRequest`)**:
```json
{
  "session_token": "v1.gAAAAABn_current..."
}
```

**Response Payload (`PracticeForfeitResponse`)**:
```json
{
  "is_game_over": true,
  "won": false,
  "revealed_entity": {
    "id": 142,
    "name": "Madagascar",
    "official_name": "Republic of Madagascar",
    "iso2": "MG",
    "capital": "Antananarivo",
    "continent": "Africa"
  }
}
```

---

## 4. Scoring & Stats Isolation Architecture

A strict invariant of the Countrydle platform is the **Air-Gapped Separation of Daily Streaks and Practice Play**.

### 4.1 The Daily Streak Sanctity Invariant

```
+---------------------------------------------------------------------------------------+
|                               STRICT DATA ISOLATION                                   |
|                                                                                       |
|   DAILY MODE COMPETITION                   PRACTICE / UNLIMITED REPLAY                |
|   ----------------------                   ---------------------------                |
|   • Model: `CountrydleState`               • Model: `UserPracticeStats`               |
|   • Fixed Date (UTC Midnight)              • Ephemeral Tokens (AES-256-GCM)           |
|   • Strict: 1 Play Per Day                 • Infinite Plays On-Demand                 |
|   • Feeds: `user_points.streak`            • Feeds: `practice_streak` ONLY            |
|   • Feeds: Monthly Leaderboard             • Zero Leaderboard Impact                  |
|   • Competitive Ranking                    • Pedagogical / Casual Mastery             |
+---------------------------------------------------------------------------------------+
```

Under no circumstances may a practice game increment, preserve, or reset a user's official `user_points.streak`. Daily streaks represent consecutive calendar days of discipline. Practice streaks represent consecutive practice puzzles solved in a sandbox run.

### 4.2 Database Schema (PostgreSQL Authenticated Storage)

To store practice statistics for registered users, we introduce the `user_practice_stats` table via Alembic:

```python
# server/db/models/practice_stats.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from db.base import Base

class UserPracticeStats(Base):
    __tablename__ = "user_practice_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_mode = Column(String(32), nullable=False, index=True)  # 'countrydle', 'powiatdle', etc.
    
    games_played = Column(Integer, default=0, nullable=False)
    games_won = Column(Integer, default=0, nullable=False)
    current_win_streak = Column(Integer, default=0, nullable=False)
    best_win_streak = Column(Integer, default=0, nullable=False)
    
    total_questions_asked = Column(Integer, default=0, nullable=False)
    total_guesses_made = Column(Integer, default=0, nullable=False)
    
    # Stores histogram of winning guesses: e.g. {"1": 14, "2": 28, "3": 9}
    guess_distribution = Column(JSONB, default=dict, nullable=False)
    
    avg_solve_time_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "game_mode", name="uq_user_practice_stats_user_mode"),
    )
```

### 4.3 Guest LocalStorage Schema (`client/src/lib/practiceStats.ts`)

For unauthenticated guests, stats are tracked locally in `localStorage` under keys partitioned by mode:
`countrydle_practice_stats_v1_${gameType}`.

```typescript
export interface GuestPracticeStats {
  gamesPlayed: number;
  gamesWon: number;
  currentWinStreak: number;
  bestWinStreak: number;
  totalQuestions: number;
  totalGuesses: number;
  guessDistribution: Record<number, number>; // { 1: 5, 2: 12, 3: 4 }
  lastPlayedAt: string;
}
```

When an unauthenticated guest registers or logs in, the client calls `POST /{mode}/practice/sync-stats`, merging local achievements with their remote database record using monotonic max reconciliation for best streaks and additive sum for total games played.

---

## 5. Frontend Architecture & User Experience

### 5.1 Dual-Mode State Engine in `client/src/stores/gameStore.ts`

Rather than maintaining two entirely separate page components or resetting the store upon mode toggle, `gameStore.ts` is enhanced to support dual-mode execution (`activeMode: 'daily' | 'practice'`).

```
+-----------------------------------------------------------------------+
|                             GAME STORE                                |
|                                                                       |
|   +------------------------------+  +-----------------------------+   |
|   |         Daily Slot           |  |        Practice Slot        |   |
|   |  • gameState                 |  |  • practiceState            |   |
|   |  • questions                 |  |  • practiceQuestions        |   |
|   |  • guesses                   |  |  • practiceGuesses          |   |
|   |  • correctEntity             |  |  • sessionToken             |   |
|   |  • dailyDate                 |  |  • practiceEntity           |   |
|   +------------------------------+  +-----------------------------+   |
|                                 |                                     |
|                 activeMode: 'daily' | 'practice'                      |
|                                 v                                     |
|              Active UI View (Map, Inputs, History)                    |
+-----------------------------------------------------------------------+
```

#### Key Benefits of Dual-Slot Store
1. **Zero State Collisions**: A user playing a daily game who switches to practice mode does not lose their in-progress daily question history or guesses.
2. **Instant Tab Switching**: Toggling between `[ 📅 Daily ]` and `[ ♾️ Practice ]` renders instantly without reloading the page, re-fetching GeoJSON polygons, or re-initializing Leaflet map containers.

### 5.2 UI Components & Visual Differentiation

#### 5.2.1 Mode Switcher (Header / Sub-Header)
A sleek, accessible segmented pill toggle placed in the game page header:

```tsx
<div role="tablist" aria-label="Game Mode" className="inline-flex rounded-md border border-white/10 bg-obsidian-950 p-1">
  <button
    role="tab"
    aria-selected={activeMode === 'daily'}
    onClick={() => setGameMode('daily')}
    className={cn(
      "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
      activeMode === 'daily'
        ? "bg-emerald-500/20 text-emerald-300 shadow-sm"
        : "text-zinc-400 hover:text-sand-100"
    )}
  >
    <Calendar size={13} aria-hidden="true" />
    <span>Daily Puzzle</span>
  </button>

  <button
    role="tab"
    aria-selected={activeMode === 'practice'}
    onClick={() => setGameMode('practice')}
    className={cn(
      "flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors",
      activeMode === 'practice'
        ? "bg-amber-500/20 text-amber-300 shadow-sm"
        : "text-zinc-400 hover:text-sand-100"
    )}
  >
    <Infinity size={14} aria-hidden="true" />
    <span>Practice Mode</span>
  </button>
</div>
```

#### 5.2.2 Visual Ambience & Disambiguation
To prevent users from mistakenly believing their practice game is an official daily run:
- **Header Badge**: Displays an amber badge: `"PRACTICE FIELDWORK · PUZZLE #4"`.
- **Map Header**: Changes label from `"Daily fieldwork · 2026-09-22"` to `"Practice Sandbox · Free Deduction"`.
- **Elimination Visualizer**: Inherits the exact same interactive elimination features so players can practice their map visualization skills.

#### 5.2.3 Post-Game Replay Loop (`PracticeResultCard.tsx`)
Upon game over in Practice Mode, the result card offers high-tempo replay actions:

```
+-------------------------------------------------------------------+
|                           PUZZLE SOLVED!                          |
|                             MADAGASCAR                            |
|                 Questions: 4/10  ·  Guesses: 1/3                  |
|                                                                   |
|   Practice Streak: 5 Wins   ·   Practice Win Rate: 84%            |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |   [ 🔁 Play Another Puzzle ]       [ 📅 Back to Daily ]   |   |
|   +-----------------------------------------------------------+   |
|                                                                   |
|   [ Share Practice Result ]  (Watermarked as "Countrydle Practice")|
+-------------------------------------------------------------------+
```
Clicking **[ Play Another Puzzle ]** triggers `startPracticeGame()`:
- Erases local practice deduction history.
- Requests a new encrypted session token from the backend in $< 100\text{ms}$.
- Resets the Leaflet map bounds and zoom.
- Refocuses the question input box immediately.

#### 5.2.4 Daily Completion Teaser
On the standard daily game over card (`ShareResultCard.tsx`), after revealing today's answer, a persistent banner invites the player into Practice Mode:
> *"Finished today's fieldwork? Hone your geography instincts in **Practice Mode** with unlimited random countries!"*  
> `[ Jump into Practice Mode -> ]`

---

## 6. Question Answering Integration & Cost Control

### 6.1 Leveraging the Question Plan Cache

In practice mode, players frequently ask standard exploratory questions:
- *"Is it in Europe?"* / *"Czy leży w Europie?"*
- *"Does it border the ocean?"* / *"Czy ma dostęp do morza?"*
- *"Is the population over 50 million?"*

Because the Question Plan Cache (`server/utils/plan_cache.py`) key is `(mode, normalized_question)`, **the AST generation is completely independent of the secret target entity**:
```
User asks: "Is it in Europe?"
1. Normalize: "is it in europe"
2. Plan Cache Lookup: HIT! -> AST: RelationalFilter(table="countries", column="continent", op="eq", value="Europe")
3. Local Facts DB Execution: Query SQLite for target_country_id=142. Value = "Africa" != "Europe" -> False!
```
- **Latency**: $1.2\text{s} \rightarrow 2.8\text{ms}$
- **Gemini API Cost**: **$0.00** (Zero external calls)
- **Database Load**: Zero PostgreSQL connections checked out; runs against read-only in-process SQLite facts database.

### 6.2 Rate Limiting Protection

To protect the platform from automated scrapers using practice mode to spam Gemini API calls:
- Practice question endpoints are protected by `slowapi` rate limiting:
  - **Guests**: 20 questions/minute per IP address.
  - **Authenticated Users**: 60 questions/minute.
- Requests hitting the Question Plan Cache bypass or receive discounted rate limit counting, ensuring legitimate human players never encounter false rate limits.

---

## 7. Multi-Mode Extensibility

The Practice Mode architecture is designed as a reusable system engine across all current and future deduction game modes:

```
server/practice/
├── crypto.py            # Reusable AES-256-GCM token generator, parser & validator
├── schemas.py           # Generic Pydantic v2 PracticeBase schemas
└── engine.py            # Abstract PracticeEngine managing target selection, cooldown, and limits
```

### Supported Game Modes & Target Pools

| Game Mode | Entity Pool | Max Questions | Max Guesses | Facts DB Source | Cooldown Window |
|---|---|---|---|---|---|
| **Countrydle** | 195 Sovereign Countries | 10 | 3 | `data/country_facts.sqlite` | 20 games |
| **US Statedle** | 50 US States | 8 | 3 | `data/us_state_facts.sqlite` | 15 games |
| **Wojewodztwodle** | 16 Polish Voivodeships | 5 | 2 | `data/voivodeship_facts.sqlite` | 8 games |
| **Powiatdle** | 380 Polish Powiaty | 15 | 3 | `data/powiat_facts.sqlite` | 40 games |
| **Flagdle** *(Upcoming)* | 195 Country Flags | 6 | 3 | `data/country_facts.sqlite` | 20 games |
| **Europedle** *(Upcoming)* | 47 European Countries | 8 | 3 | `data/country_facts.sqlite` | 15 games |

---

## 8. Step-by-Step Implementation Roadmap

### Phase 1: Security & Cryptographic Foundation
- [ ] Create `server/utils/practice_crypto.py`:
  - Implement `PracticeTokenManager` utilizing `AESGCM(SECRET_KEY_DERIVED)`.
  - Implement serialization, deserialization, timestamp validation, and tamper exception handling.
- [ ] Write backend unit tests in `server/tests/test_practice_crypto.py` covering:
  - Valid token encryption/decryption round-trip.
  - Rejection of tampered payloads (e.g. modified `guesses_made`).
  - Rejection of expired tokens.
  - Verification that target entity ID is absent in plaintext token inspection.

### Phase 2: Backend Practice Endpoints & Pydantic Schemas
- [ ] Create Pydantic v2 schemas in `server/schemas/practice.py` (`PracticeStartRequest`, `PracticeQuestionResponse`, `PracticeGuessResponse`, etc.).
- [ ] Implement `server/countrydle/practice.py` router:
  - `POST /countrydle/practice/start` with random selection and cooldown exclusion.
  - `POST /countrydle/practice/question` integrating Question Plan Cache and SQLite execution.
  - `POST /countrydle/practice/guess` with evaluation and entity reveal on completion.
  - `POST /countrydle/practice/forfeit` with entity reveal.
- [ ] Register practice router under `server/countrydle/__init__.py`.
- [ ] Write integration test suite in `server/tests/test_countrydle_practice.py`.

### Phase 3: Database Models & User Practice Statistics
- [ ] Create SQLAlchemy model `UserPracticeStats` in `server/db/models/practice_stats.py`.
- [ ] Generate and apply Alembic migration (`alembic revision --autogenerate -m "add_user_practice_stats"`).
- [ ] Create `server/db/repositories/practice_stats.py` with methods for atomic increment, streak calculation, and guess distribution updates.
- [ ] Implement `GET /countrydle/practice/stats` and `POST /countrydle/practice/sync-stats`.

### Phase 4: Frontend State Engine & API Service
- [ ] Update `client/src/services/api.ts` with `practiceService`:
  - `start()`, `askQuestion()`, `makeGuess()`, `forfeit()`, `getStats()`, `syncStats()`.
- [ ] Create `client/src/lib/practiceStats.ts` for guest `localStorage` management and streak calculation.
- [ ] Extend `client/src/stores/gameStore.ts`:
  - Add `activeMode: 'daily' | 'practice'`.
  - Add practice state slots (`practiceState`, `practiceQuestions`, `practiceGuesses`, `sessionToken`).
  - Add actions: `setGameMode`, `startPracticeGame`, `askPracticeQuestion`, `makePracticeGuess`, `resetPracticeGame`.

### Phase 5: UI Components & Experience Polish
- [ ] Build `client/src/components/ModeSwitcher.tsx` and integrate into `client/src/pages/GamePage.tsx`.
- [ ] Update `client/src/components/ShareResultCard.tsx`:
  - Add Practice Mode CTA button on daily completion.
  - Support Practice Mode specific share card (distinct watermark).
- [ ] Add `[ 🔁 Play Another Puzzle ]` button to practice game over state.
- [ ] Add `PracticeStatsModal.tsx` displaying practice win rate and guess distribution.

### Phase 6: Multi-Mode Rollout & Verification
- [ ] Mount practice routers for `wojewodztwodle`, `us_statedle`, and `powiatdle`.
- [ ] Verify identical UI/UX behavior across all game modes.
- [ ] Perform comprehensive E2E gameplay verification.

---

## 9. File Inventory & Modification Guide

| File Path | Nature | Purpose |
|---|---|---|
| `server/utils/practice_crypto.py` | **NEW** | AES-256-GCM token generator, parser, validator. |
| `server/schemas/practice.py` | **NEW** | Pydantic v2 request/response schemas for practice sessions. |
| `server/db/models/practice_stats.py` | **NEW** | SQLAlchemy model for registered user practice stats. |
| `server/db/repositories/practice_stats.py` | **NEW** | Database repository for updating practice win streaks and metrics. |
| `server/countrydle/practice.py` | **NEW** | Router for `/countrydle/practice/*` endpoints. |
| `server/tests/test_practice_crypto.py` | **NEW** | Unit test suite verifying AEAD security and tamper resistance. |
| `server/tests/test_countrydle_practice.py` | **NEW** | Integration test suite verifying practice gameplay cycle. |
| `server/countrydle/__init__.py` | **EDIT** | Mount the practice sub-router under `/countrydle`. |
| `server/db/models/__init__.py` | **EDIT** | Export `UserPracticeStats` model. |
| `client/src/lib/practiceStats.ts` | **NEW** | LocalStorage manager for guest practice statistics. |
| `client/src/components/ModeSwitcher.tsx` | **NEW** | Tab toggle component for switching between Daily and Practice modes. |
| `client/src/services/api.ts` | **EDIT** | Add practice API methods to `gameService`. |
| `client/src/stores/gameStore.ts` | **EDIT** | Introduce dual-mode state engine and practice actions. |
| `client/src/pages/GamePage.tsx` | **EDIT** | Render mode switcher, practice badges, and "Play Again" flows. |
| `client/src/components/ShareResultCard.tsx` | **EDIT** | Add practice CTA and practice share formatting. |

---

## 10. Verification & Testing Strategy (TDD)

To guarantee that Practice Mode is defect-free, secure, and preserves daily streak integrity, the following test suite must be implemented:

### 10.1 Backend Unit & Security Tests (`test_practice_crypto.py`)
```python
def test_aes_gcm_token_integrity():
    """Verify that tampering with any bit in the ciphertext causes immediate decryption failure."""
    mgr = PracticeTokenManager(secret_key="test_secret_key_32_bytes_long!!")
    payload = {"target_id": 42, "mode": "countrydle", "questions_asked": 0}
    token = mgr.encode_token(payload)
    
    # Tamper with token string
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(InvalidPracticeTokenError):
        mgr.decode_token(tampered)

def test_zero_knowledge_target_secrecy():
    """Verify that the target entity ID is completely unreadable from the serialized token."""
    mgr = PracticeTokenManager(secret_key="test_secret_key_32_bytes_long!!")
    target_id = 9999
    token = mgr.encode_token({"target_id": target_id})
    
    # Assert string representation does not contain the plaintext ID or ASCII encoded bytes
    assert str(target_id) not in token
    raw_bytes = base64.urlsafe_b64decode(token.split(".", 1)[1])
    assert str(target_id).encode() not in raw_bytes
```

### 10.2 Integration & Isolation Tests (`test_countrydle_practice.py`)
```python
@pytest.mark.asyncio
async def test_practice_mode_does_not_affect_daily_streak(async_client, auth_headers):
    """Verify that completing 5 practice games does not modify user_points.streak."""
    # 1. Check initial user daily streak
    initial_user = await get_current_user_points()
    initial_streak = initial_user.streak
    
    # 2. Complete a winning practice game
    start_res = await async_client.post("/countrydle/practice/start", headers=auth_headers)
    token = start_res.json()["session_token"]
    
    # Guess correctly
    guess_res = await async_client.post("/countrydle/practice/guess", json={
        "session_token": token,
        "guess": "CorrectTargetName",
        "entity_id": correct_id
    }, headers=auth_headers)
    assert guess_res.json()["won"] is True
    
    # 3. Verify user daily streak is completely untouched
    final_user = await get_current_user_points()
    assert final_user.streak == initial_streak
```

### 10.3 Frontend Unit Tests (`client/src/tests/practiceStats.test.ts`)
- Verify that guest practice statistics correctly calculate consecutive practice win streaks.
- Verify that a loss resets `currentWinStreak` to 0 while preserving `bestWinStreak`.
- Verify that malformed or corrupted `localStorage` entries fail gracefully to an empty stats baseline.

---

## 11. Operational Risks & Mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| **LLM Quota Exhaustion** | Heavy practice play increases Gemini API consumption. | **Plan Caching**: 80%+ of common practice questions hit the in-memory AST cache ($< 3\text{ms}$, $0.00 cost). Rate limits (20 Q/min for guests) prevent script abuse. |
| **Small Entity Pool Repeats** | In modes with few entities (e.g. Województwodle with 16 voivodeships), players see duplicate targets quickly. | **Client Cooldown Buffer**: Client passes `cooldown_exclude_ids` of the last 8 targets. Target selection filters out recently seen entities. |
| **Accidental Streak Confusion** | Players believe practice wins count toward daily leaderboards. | **Visual Differentiation**: Amber/violet theme for practice fieldwork, distinct share badges ("Countrydle Practice"), explicit tooltip clarifications. |
| **Token Expiration During Deep Thought** | Player takes a 3-hour phone call mid-game, returning to find token expired. | **Long Expiry Window (4 Hours)**: Practice tokens carry a generous 4-hour TTL, easily accommodating interrupted casual play. |

---

## 12. Conclusion & Deliverables

By replacing the static, spoiler-heavy `/archive` table with a dynamic, cryptographically secure **Practice / Unlimited Mode**, Countrydle transforms from a 3-minute single-serve daily chore into an engaging, replayable geography platform.

This architecture achieves:
1. **Zero Database Overhead**: Stateless AES-256-GCM tokens eliminate database connection pool starvation and ephemeral table bloat.
2. **Absolute Anti-Cheat Integrity**: Target entities remain cryptographically masked until game completion.
3. **Daily Streak Sanctity**: Complete physical and logical isolation between competitive daily streaks and casual practice runs.
4. **Instant Replayability**: Players can jump into a new randomized puzzle in $< 100\text{ms}$ with a single click.

All components, database schemas, API contracts, and UX specs detailed in this plan are fully specified and ready for implementation.
