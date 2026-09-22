# Architectural & Implementation Plan: Flagdle (`/flagdle`)
## The Daily Flag Deduction & Progressive Visual Revelation Game

---

## 1. Executive Summary & Game Mode Vision

### 1.1 Core Value Proposition
**Flagdle** is a dedicated daily game mode (`/flagdle`) within the Countrydle platform that merges visual vexillology with Countrydle's signature deductive reasoning. While the flagship Countrydle mode relies heavily on textual 20-Questions AI interrogation, flags are inherently high-contrast visual artifacts. Flagdle gives geography enthusiasts, casual players, and students a fast-paced, visually gratifying, and highly replayable daily challenge.

### 1.2 Target Audience & Retention Impact
* **Vexillology Enthusiasts & Casual Gamers:** Quick daily play session (2–4 minutes) complementary to the deep Countrydle session (5–10 minutes).
* **Viral Social Growth:** Generates iconic, color-rich emoji share cards (reminiscent of Wordle and Flagle) that drive organic referral loops on Twitter/X, Reddit, and Discord.
* **Educational Value:** Reinforces national flag recognition, color symbolism, heraldic emblems, continental geography, and spatial bearings.

---

## 2. Comparative Analysis of Game Mechanics & Final Recommendation

We evaluated three architectural mechanics for Flagdle against key product and engineering criteria:
* **Option A:** 20 Questions for Flags (Pure NLP / SQLite Attribute Interrogation)
* **Option B:** Progressive Visual Reveal / Unblur Only (Pure Flagle clone)
* **Option C:** Hybrid Vexillological Deduction Engine (Progressive Visual Reveal + Attribute Clue Matrix + Spatial Direction)

### 2.1 Deep Comparison Matrix

| Evaluation Dimension | Option A: 20 Questions for Flags | Option B: Visual Unblur Only | Option C: Hybrid Deduction Engine (RECOMMENDED) |
| :--- | :--- | :--- | :--- |
| **Core Mechanic** | Player types NLP questions (*"Does the flag have green?"*, *"Is there a crescent?"*). AI/SQLite evaluates against `country_flag_colors` and `country_flag_symbols`. 10 questions, 3 guesses. | Flag starts heavily pixelated or masked in 6 tiles. 6 guesses. Each wrong guess unmasks 1 tile (16.6%) or reduces blur radius. | 6 guesses. Each wrong guess uncovers 1/6th of the flag **AND** evaluates the guessed country against the secret target across 3 attribute axes (Color Overlap, Emblem Match, Distance/Bearing). |
| **Server Cost & Inference Latency** | High (~$0.0008/turn if routed through Gemini LLM planner, 800ms–1500ms latency). | Zero ($0.00 token cost, 0ms AI inference, purely deterministic). | Zero ($0.00 token cost; all attribute checks run via instant local SQLite lookups and Haversine math, <5ms response). |
| **Visual Gratification** | Low (Text input and textual tables; flag remains unseen until game over). | High (Direct visual engagement with vector flag graphics). | Maximum (Combines visual tile unmasking with satisfying tactile clue badges and distance arrows). |
| **Disambiguation / Anti-Frustration** | Medium (Text disambiguation works, but lacks immediate visual context). | Poor (Tricolor deadlocks: e.g., guessing Chad vs Romania, Monaco vs Poland vs Indonesia, or Ireland vs Côte d'Ivoire with partial tiles leads to pure random guessing). | Excellent (If player guesses Chad and it's Romania, the visual slice confirms colors, while distance/bearing clue *"5,200 km North ↗"* immediately breaks the deadlock). |
| **Accessibility (a11y & Screen Readers)** | High for text, but no visual assist. | Inaccessible to visually impaired / color-blind players. | Full compliance: Screen readers receive explicit structured text clues (*"Guessed: Germany. Shared colors: Red, Yellow. Absent: Black. Bearing: 1,400km South"*). |
| **Social Virality (Share Grid)** | Moderate (Numeric question score). | High (Basic tile reveal emoji grid). | Outstanding (Multi-dimensional emoji grid showing tile progress, color hits, and spatial arrows). |
| **Implementation Complexity** | Medium (Reuses `countrydle` question pipeline). | Low (Frontend CSS canvas/mask). | Medium-High (Requires secure image masking proxy, clue comparison engine, and timeline UI). |

### 2.2 Concrete Recommendation: Option C (Hybrid Vexillological Deduction Engine)

**Option C is selected as the production architecture.** 
Flags represent both spatial geometry (colors, stripes, symbols) and sovereign identity. A purely visual game (Option B) degrades into frustrating coin flips on the 40+ world flags sharing identical tricolor bands or canton layouts. Conversely, a purely textual 20-questions game (Option A) ignores the beauty of vexillological artwork and strains LLM tokens. 

Option C delivers:
1. **The 6-Stage Progressive Unmasking:** A 3×2 dynamic grid mask (or progressive radial unblur) uncovers 1/6th of the flag image with every incorrect guess.
2. **Deterministic Vexillological Feedback:** Every incorrect guess returns:
   * **Color Overlap Chips:** Colors present in both target and guess (`matched_colors`), colors in guess absent in target (`missed_colors`), and count of remaining undiscovered colors.
   * **Emblem / Symbol Match:** Direct verification against `country_flag_symbols` (`star`, `crescent`, `cross`, `coat_of_arms`, `sun`, `stripes`, `circle`, `eagle`).
   * **Spatial Compass Bearing:** Distance (km) and compass direction (e.g. `2,150 km ↘ Southeast`) calculated via spherical Haversine formula from centroid coordinates.
3. **Zero AI Operating Cost:** 100% deterministic local computation using SQLite and PostgreSQL.

---

## 3. Data & Asset Pipeline

### 3.1 SQLite Knowledge Base Audit (`data/country_facts.sqlite`)
The database contains verified flag metadata across world nations:
* `countries`: 195 sovereign nations (`id`, `app_country_name`, `official_name`, `cca2`, `cca3`, `latitude`, `longitude`, `capital`, `region`, `subregion`).
* `country_flag_colors`: 613 rows covering 194 countries.
  * Unique color taxonomy: `red` (151), `white` (140), `blue` (98), `yellow` (87), `green` (83), `black` (44), `orange` (10).
  * *Data Anomaly Identified:* Country ID 133 (`Palestine`, `PS`) currently lacks rows in `country_flag_colors`. A one-off backfill migration will insert `black`, `white`, `green`, `red` for country ID 133.
* `country_flag_symbols`: 335 rows across 188 countries.
  * Standard symbol taxonomy: `stripes` (144), `star` (65), `coat_of_arms` (29), `stars` (28), `cross` (21), `crescent` (16), `sun` (14), `circle` (10), `eagle` (8).
  * 7 countries possess unique or non-standard emblems (`Bhutan` [dragon], `Cyprus` [island map/copper], `Eritrea` [olive branch], `Guyana` [arrowhead], `Saint Lucia` [cerulean triangle], `Saudi Arabia` [shahada/sword]). When queried, these evaluate to `other_emblem` or custom badges.

### 3.2 High-Resolution Flag Asset Pipeline (`flagcdn.com`)
* **Vector Source (SVG):** `https://flagcdn.com/{cca2.lower()}.svg` (lossless scaling for the main unmasking canvas).
* **Raster Fallbacks:** 
  * Large: `https://flagcdn.com/w640/{cca2.lower()}.png` (retina mobile/desktop display).
  * Medium: `https://flagcdn.com/w320/{cca2.lower()}.png` (summary card).
  * Micro: `https://flagcdn.com/20x15/{cca2.lower()}.png` (dropdown autocomplete suggestions).
* **Aspect Ratio Normalization:**
  World flags have varying proportions:
  * 2:3 ratio (majority of countries: France, Spain, Japan, Italy).
  * 1:2 ratio (UK, Australia, Canada, New Zealand, former British territories).
  * 1:1 square (Switzerland, Vatican City).
  * Non-standard: Nepal (5:4 double-pennant), Qatar (11:28), Belgium (13:15).
  * *Layout Strategy:* The Flagdle viewport utilizes a fixed `aspect-[3/2]` container with `object-contain`, centered against a neutral canvas with subtle drop-shadow and border (`border border-sand-700/50 bg-sand-900/40`), ensuring flags like Switzerland or Nepal render cleanly without stretching or distortion.

---

## 4. Security & Anti-Cheat Architecture (CRITICAL)

### 4.1 The Threat Model
In web-based deduction games, client-side inspection is the primary vulnerability:
1. **Network Tab Inspection:** If the frontend requests `https://flagcdn.com/w640/fr.png` directly, a player inspecting DevTools instantly discovers France.
2. **DOM / CSS Class Leaks:** If the image tag contains `data-country="France"` or `alt="Flag of France"` prior to game completion, cheat scripts can scrape it.
3. **State Payload Leaks:** If `GET /flagdle/state` contains `country_id: 42` or `iso2: "FR"`, the game is compromised.

### 4.2 Multi-Layered Anti-Cheat Safeguards
```
+-----------------------------------------------------------------------------------+
| CLIENT BROWSER                                                                    |
|                                                                                   |
|  1. Requests Game State: GET /flagdle/state                                       |
|     <-- Receives: day_id, remaining_guesses: 6, guesses: [], mask_stage: 1         |
|     (ZERO country_id, ZERO iso2, ZERO flag URL)                                   |
|                                                                                   |
|  2. Fetches Obfuscated Image: GET /flagdle/flag-asset?stage=1&token=...           |
|     <-- Receives: Server-rendered WebP with 5/6th of image scrambled/masked       |
|                                                                                   |
|  3. Submits Guess: POST /flagdle/guess {"country_id": 85}                         |
|     <-- Receives: {is_correct: false, matched_colors: [...], distance_km: 1800}   |
|                                                                                   |
|  4. Game Over (Win/Loss): GET /flagdle/end/state                                  |
|     <-- Receives: Full target {id: 42, name: "France", iso2: "fr"}                |
|     Client unlocks full unmasked SVG: https://flagcdn.com/fr.svg                  |
+-----------------------------------------------------------------------------------+
```

1. **Server-Side Masking / Image Proxy Endpoint (`/flagdle/flag-asset`):**
   * During active gameplay (`is_game_over == False`), the client never requests `flagcdn.com` directly.
   * Instead, the client requests `/flagdle/flag-asset?stage={revealed_stages}&token={hmac_token}`.
   * The backend loads the SVG/PNG in memory, applies a 6-tile curtain mask (blacking out unrevealed tiles or applying a heavy progressive Gaussian blur via `Pillow`/`cairosvg`), and streams the resulting WebP/PNG directly to the browser.
   * Unrevealed pixels literally do not exist in the client image payload.
2. **HMAC Request Signing:**
   * The image URL includes a short-lived HMAC token: `hmac.new(SECRET, f"{day_id}:{user_id_or_guest}:{stage}".encode(), sha256).hexdigest()[:16]`.
   * Prevents players from manipulating the `stage` parameter to preview stage 6 ahead of time.
3. **Strict State Serialization Isolation:**
   * `FlagdleStateResponse` deliberately omits `country_id`, `country`, `cca2`, and `target_name`.
   * Only `FlagdleEndStateResponse` (served when `state.is_game_over == True`) includes the `CountryDisplay` entity.

---

## 5. Backend System Architecture & Database Design

### 5.1 Database Models (`server/db/models/flagdle.py`)
```python
from datetime import date, datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from db.base import Base


class FlagdleDay(Base):
    __tablename__ = "flagdle_days"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    country = relationship("Country")
    states = relationship("FlagdleState", back_populates="day", cascade="all, delete-orphan")
    guesses = relationship("FlagdleGuess", back_populates="day", cascade="all, delete-orphan")


class FlagdleState(Base):
    __tablename__ = "flagdle_states"
    __table_args__ = (
        UniqueConstraint("user_id", "day_id", name="uq_flagdle_user_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False, index=True)
    
    remaining_guesses = Column(Integer, default=6, nullable=False)
    guesses_made = Column(Integer, default=0, nullable=False)
    revealed_stage = Column(Integer, default=1, nullable=False)  # 1 to 6
    is_game_over = Column(Boolean, default=False, nullable=False)
    won = Column(Boolean, default=False, nullable=False)
    points = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    day = relationship("FlagdleDay", back_populates="states")
    user = relationship("User")


class FlagdleGuess(Base):
    __tablename__ = "flagdle_guesses"

    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("flagdle_days.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    guessed_country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    guess_text = Column(String, nullable=False)
    
    answer = Column(Boolean, nullable=False)  # True if correct match
    distance_km = Column(Integer, nullable=False)
    bearing_degrees = Column(Integer, nullable=False)
    bearing_compass = Column(String(4), nullable=False)  # N, NE, E, SE, S, SW, W, NW
    
    matched_colors = Column(JSON, nullable=False)  # List[str], e.g. ["red", "white"]
    missed_colors = Column(JSON, nullable=False)   # List[str], colors in guess not in target
    matched_symbols = Column(JSON, nullable=False) # List[str], e.g. ["stripes"]
    
    elapsed_seconds = Column(Integer, nullable=True)
    guessed_at = Column(DateTime, default=func.now())

    day = relationship("FlagdleDay", back_populates="guesses")
    user = relationship("User")
    guessed_country = relationship("Country")
```

### 5.2 Alembic Migration Script (`alembic/versions/7a8f9e0d1c2b_add_flagdle_tables.py`)
* Creates `flagdle_days`, `flagdle_states`, `flagdle_guesses` with foreign keys to `countries` and `users`.
* Creates index `idx_flagdle_days_date` on `flagdle_days(date)`.
* Creates unique constraint `uq_flagdle_user_day` on `flagdle_states(user_id, day_id)`.
* Seeds Palestine flag colors in `country_flag_colors` to guarantee 100% data integrity.

### 5.3 Daily Rotation & Flag Selection Engine (`server/flagdle/crud.py`)
```python
import random
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.flagdle import FlagdleDay
from db.models.country import Country

class FlagdleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_day_flag_by_date(self, target_date: date) -> FlagdleDay | None:
        stmt = select(FlagdleDay).where(FlagdleDay.date == target_date)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def generate_new_day_flag(self, target_date: date | None = None) -> FlagdleDay:
        if target_date is None:
            target_date = date.today()

        # Check existing
        existing = await self.get_day_flag_by_date(target_date)
        if existing:
            return existing

        # Rotation policy: Fetch all countries not used in the last 90 days
        subquery = (
            select(FlagdleDay.country_id)
            .where(FlagdleDay.date >= target_date - timedelta(days=90))
        )
        stmt = select(Country.id).where(~Country.id.in_(subquery))
        res = await self.session.execute(stmt)
        candidate_ids = res.scalars().all()

        if not candidate_ids:
            # Fallback if pool exhausted
            all_stmt = select(Country.id)
            all_res = await self.session.execute(all_stmt)
            candidate_ids = all_res.scalars().all()

        chosen_country_id = random.choice(candidate_ids)
        new_day = FlagdleDay(country_id=chosen_country_id, date=target_date)
        self.session.add(new_day)
        await self.session.commit()
        await self.session.refresh(new_day)
        return new_day
```

### 5.4 APScheduler Integration (`server/utils/__init__.py`)
Add the scheduled daily job alongside `generate_day_countries`:
```python
async def generate_day_flags():
    async with AsyncSessionLocal() as session:
        f_repo = FlagdleRepository(session)
        for day_date in (date.today() + timedelta(days=n) for n in range(5)):
            existing = await f_repo.get_day_flag_by_date(day_date)
            if existing is None:
                logging.info(f"Generating Flagdle target for {day_date}")
                await f_repo.generate_new_day_flag(day_date)

# In scheduler initialization:
scheduler.add_job(generate_day_flags, CronTrigger(hour=0, minute=0))
```

### 5.5 Geographic & Vexillological Clue Evaluator (`server/flagdle/evaluator.py`)
```python
import math
import sqlite3
from typing import Dict, List, Tuple

COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

def calculate_haversine_distance_and_bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Tuple[int, int, str]:
    """Calculates great-circle distance (km) and compass bearing from (lat1, lon1) to (lat2, lon2)."""
    R = 6371.0  # Earth radius in kilometers

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Distance
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = int(round(R * c))

    # Initial Bearing
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2) -
         math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))
    bearing_rad = math.atan2(y, x)
    bearing_deg = int((math.degrees(bearing_rad) + 360) % 360)

    # Compass index (each segment is 45 deg)
    idx = int(round(bearing_deg / 45)) % 8
    compass = COMPASS_POINTS[idx]

    return distance_km, bearing_deg, compass

def evaluate_flag_attributes(
    sqlite_conn: sqlite3.Connection,
    target_country_id: int,
    guessed_country_id: int
) -> Dict[str, List[str]]:
    """Compares colors and symbols between target and guessed country using country_facts.sqlite."""
    cur = sqlite_conn.cursor()

    # Target attributes
    target_colors = {r[0] for r in cur.execute("SELECT color FROM country_flag_colors WHERE country_id=?", (target_country_id,))}
    target_symbols = {r[0] for r in cur.execute("SELECT symbol FROM country_flag_symbols WHERE country_id=?", (target_country_id,))}

    # Guessed attributes
    guessed_colors = {r[0] for r in cur.execute("SELECT color FROM country_flag_colors WHERE country_id=?", (guessed_country_id,))}
    guessed_symbols = {r[0] for r in cur.execute("SELECT symbol FROM country_flag_symbols WHERE country_id=?", (guessed_country_id,))}

    matched_colors = sorted(list(target_colors.intersection(guessed_colors)))
    missed_colors = sorted(list(guessed_colors.difference(target_colors)))
    matched_symbols = sorted(list(target_symbols.intersection(guessed_symbols)))

    return {
        "matched_colors": matched_colors,
        "missed_colors": missed_colors,
        "matched_symbols": matched_symbols,
    }
```

### 5.6 Dynamic Points & Scoring Algorithm (`server/game_logic.py`)
```python
FLAGDLE_CONFIG = GameConfig(max_questions=0, max_guesses=6)

def calculate_flagdle_points(
    won: bool,
    guesses_used: int,
    elapsed_seconds: int | None = None,
    streak: int = 0,
) -> int:
    """
    Scoring curve for Flagdle:
    - Base Win Floor: +500 pts
    - Guess Bonus: Rewards rapid identification
        Guess 1: +1,500 pts | Guess 2: +1,100 pts | Guess 3: +800 pts
        Guess 4: +500 pts   | Guess 5: +250 pts   | Guess 6: +100 pts
    - Speed Bonus: Up to +300 pts decaying over 180 seconds (3 min)
    - Daily Streak Bonus: +50 pts per consecutive day (capped at +500 pts)
    Total possible score: 2,800 pts.
    """
    if not won:
        return 0

    base_points = 500
    guess_bonus_map = {1: 1500, 2: 1100, 3: 800, 4: 500, 5: 250, 6: 100}
    guess_bonus = guess_bonus_map.get(guesses_used, 50)

    speed_bonus = 0
    if elapsed_seconds is not None and elapsed_seconds > 0:
        decay_factor = max(0.0, (180 - elapsed_seconds) / 180)
        speed_bonus = int(300 * (decay_factor ** 1.5))

    streak_bonus = min(500, max(0, streak) * 50)

    return base_points + guess_bonus + speed_bonus + streak_bonus
```

---

## 6. Pydantic v2 API Schemas (`server/schemas/flagdle.py`)

```python
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from schemas.user import UserDisplay
from schemas.country import CountryDisplay

class FlagdleGuessBase(BaseModel):
    guess: str
    country_id: Optional[int] = None
    elapsed_seconds: Optional[int] = None

class FlagdleGuessDisplay(BaseModel):
    id: int
    guess: str
    country_id: int
    answer: bool
    distance_km: int
    bearing_degrees: int
    bearing_compass: str
    matched_colors: List[str]
    missed_colors: List[str]
    matched_symbols: List[str]
    guessed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FlagdleStateSchema(BaseModel):
    remaining_guesses: int
    guesses_made: int
    revealed_stage: int
    is_game_over: bool
    won: bool
    points: int

    model_config = ConfigDict(from_attributes=True)

class FlagdleStateResponse(BaseModel):
    user: Optional[UserDisplay] = None
    date: str
    state: FlagdleStateSchema
    guesses: List[FlagdleGuessDisplay]
    flag_asset_url: str  # e.g. "/flagdle/flag-asset?stage=2&token=abc123xyz"
    country: Optional[CountryDisplay] = None  # None until is_game_over=True

class FlagdleEndStateResponse(FlagdleStateResponse):
    country: CountryDisplay = Field(...)

class FlagdleSyncSchema(BaseModel):
    state: FlagdleStateSchema
    guesses: List[FlagdleGuessBase]
    date: str
```

---

## 7. Client UI/UX Specification

### 7.1 Page Layout & Component Tree (`/flagdle`)
```
[Header Navigation: Countrydle | Flagdle (ACTIVE) | US States | Powiaty]
+-------------------------------------------------------------------------+
|                                                                         |
|                          FLAGDLE #42 - 2026-09-22                       |
|           Deduce the secret national flag in 6 guesses or fewer         |
|                                                                         |
|   +-----------------------------------------------------------------+   |
|   |                       FLAG DISPLAY VIEWPORT                     |   |
|   |  [ 3x2 Tile Grid / Progressive Radial Reveal Mask Container ]   |   |
|   |                                                                 |   |
|   |   +-------------------+-------------------+-----------------+   |   |
|   |   | Tile 1 (Revealed) | Tile 2 (MASKED)   | Tile 3 (MASKED) |   |   |
|   |   +-------------------+-------------------+-----------------+   |   |
|   |   | Tile 4 (MASKED)   | Tile 5 (MASKED)   | Tile 6 (MASKED) |   |   |
|   |   +-------------------+-------------------+-----------------+   |   |
|   |                                                                 |   |
|   |   Stage: 1/6 Revealed                  Remaining Guesses: 5     |   |
|   +-----------------------------------------------------------------+   |
|                                                                         |
|   +-----------------------------------------------------------------+   |
|   | [🔍 Search country name...                            ] [GUESS] |   |
|   | Suggestions: [ 🇳🇴 Norway ] [ 🇫🇷 France ] [ 🇳🇱 Netherlands ]      |   |
|   +-----------------------------------------------------------------+   |
|                                                                         |
|   DEDUCTION TIMELINE & CLUES                                            |
|   +-----------------------------------------------------------------+   |
|   | #1. 🇳🇱 Netherlands | ❌ Incorrect                              |   |
|   |     🧭 2,450 km ↘ SE  |  Matched: [🔴 Red] [⚪ White]           |   |
|   |     Missed: [🔵 Blue] |  Symbols: [None]                        |   |
|   +-----------------------------------------------------------------+   |
|                                                                         |
+-------------------------------------------------------------------------+
| (On Game Over) Modal / Inline Card:                                     |
|  - High-Res Unmasked SVG Flag Display                                   |
|  - Full Country Stats (Capital, Population, Region)                     |
|  - Copyable Emoji Share Grid (Wordle/Flagle style)                      |
|  - Countdown Timer to Next Daily Flag (00:00 UTC)                       |
+-------------------------------------------------------------------------+
```

### 7.2 The Visual Unmasking Mechanism (`FlagDisplay.tsx`)
We provide a dual-mode render strategy:
1. **Desktop & High Performance:** 6-tile curtain mask with smooth CSS transitions (`transition-all duration-700 ease-in-out`).
2. **Mobile & Low Bandwidth:** Server-side pre-rendered masked WebP streamed from `/flagdle/flag-asset`, preventing client GPU lag and memory bloat on mobile browsers.

```tsx
// client/src/components/flagdle/FlagDisplay.tsx
import React from 'react';

interface FlagDisplayProps {
  stage: number; // 1 to 6
  isGameOver: boolean;
  flagUrl: string;
  countryName?: string;
}

export const FlagDisplay: React.FC<FlagDisplayProps> = ({
  stage,
  isGameOver,
  flagUrl,
  countryName,
}) => {
  // 6 grid tiles (row 1: 0, 1, 2; row 2: 3, 4, 5)
  // Pre-determined pseudo-random unmask order: [0, 4, 2, 5, 1, 3]
  const UNMASK_ORDER = [0, 4, 2, 5, 1, 3];
  const revealedSet = new Set(UNMASK_ORDER.slice(0, stage));

  return (
    <div className="relative mx-auto max-w-xl overflow-hidden rounded-xl border border-sand-700/60 bg-sand-950 p-2 shadow-2xl shadow-sand-950/80">
      <div className="relative aspect-[3/2] w-full overflow-hidden rounded-lg bg-sand-900">
        {/* The Flag Image */}
        <img
          src={flagUrl}
          alt={isGameOver && countryName ? `Flag of ${countryName}` : 'Mystery National Flag'}
          className="h-full w-full object-contain transition-all duration-500"
          draggable={false}
        />

        {/* 6-Tile Curtain Mask Overlay (active only before game over) */}
        {!isGameOver && (
          <div className="absolute inset-0 grid grid-cols-3 grid-rows-2">
            {[0, 1, 2, 3, 4, 5].map((tileIdx) => {
              const isRevealed = revealedSet.has(tileIdx);
              return (
                <div
                  key={tileIdx}
                  className={`border border-sand-800/30 backdrop-blur-md transition-all duration-700 ease-out ${
                    isRevealed
                      ? 'pointer-events-none opacity-0 scale-95'
                      : 'bg-sand-900/95 opacity-100'
                  }`}
                >
                  {!isRevealed && (
                    <div className="flex h-full items-center justify-center text-xs font-mono text-sand-500/50">
                      ?
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between px-2 text-xs font-medium text-sand-400">
        <span>Reveal Progress: {Math.min(100, Math.round((stage / 6) * 100))}%</span>
        <span>Tile {stage} of 6</span>
      </div>
    </div>
  );
};
```

### 7.3 Autocomplete Input with Micro-Flags (`FlagdleGuessInput.tsx`)
Extends `GuessInput.tsx` to include `https://flagcdn.com/20x15/{iso2.lower()}.png` in the suggestion list, allowing visual recognition as players search:
```tsx
// Suggestion row preview:
<div className="flex items-center gap-3 py-2 px-3 hover:bg-sand-800 cursor-pointer">
  <img
    src={`https://flagcdn.com/20x15/${country.iso2.toLowerCase()}.png`}
    alt=""
    className="h-3.5 w-5 rounded-sm object-cover shadow-sm"
    loading="lazy"
  />
  <span className="text-sand-100 font-medium">{country.name}</span>
  <span className="text-xs text-sand-400 ml-auto">{country.region}</span>
</div>
```

### 7.4 Shareable Emoji Result Card (`FlagdleShareResultCard.tsx`)
Generates viral social proof formatted for messaging apps and social media:
```
Countrydle Flagdle #42 3/6 🚩
🟩⬜⬜⬛⬛⬛ 🧭 3,200km ↘
🟩🟩⬜⬛⬛⬛ 🧭 850km ↗
🟩🟩🟩🟩🟩🟩 🎯 FOUND!
Score: 1,850 pts ⚡ Streak: 5 days
https://countrydle.com/flagdle
```

---

## 8. Client State Management & Store Design (`useFlagdleGameStore`)

### 8.1 Zustand Store Architecture (`client/src/stores/gameStore.ts`)
```typescript
import { create } from 'zustand';
import type { GameState, Guess } from '../types';
import { flagdleService } from '../services/api';
import { recordGuestCompletion } from '../lib/guestHistory';

interface FlagdleStateData {
  gameState: GameState | null;
  guesses: any[];
  stage: number;
  flagAssetUrl: string | null;
  correctCountry: any | null;
  dailyDate: string | null;
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  startTime: number | null;

  fetchGameState: () => Promise<void>;
  makeGuess: (countryId: number, countryName: string) => Promise<void>;
  syncGuestData: () => Promise<void>;
  resetGame: () => void;
}

export const useFlagdleGameStore = create<FlagdleStateData>((set, get) => ({
  gameState: null,
  guesses: [],
  stage: 1,
  flagAssetUrl: null,
  correctCountry: null,
  dailyDate: null,
  isLoading: false,
  isGuest: false,
  error: null,
  startTime: null,

  fetchGameState: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await flagdleService.getState();
      const localKey = `guess_game_flagdle_${data.date}`;
      const localData = localStorage.getItem(localKey);
      
      if (localData) {
        const parsed = JSON.parse(localData);
        recordGuestCompletion('flagdle', data.date, parsed.state, data.date);
      }

      set({
        gameState: data.state,
        guesses: data.guesses,
        stage: data.state.revealed_stage,
        flagAssetUrl: data.flag_asset_url,
        correctCountry: data.country || null,
        dailyDate: data.date,
        isGuest: !data.user,
        isLoading: false,
        startTime: Date.now(),
      });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  makeGuess: async (countryId: number, countryName: string) => {
    const { gameState, startTime, dailyDate } = get();
    if (!gameState || gameState.is_game_over || gameState.remaining_guesses <= 0) return;

    set({ isLoading: true });
    try {
      const elapsed = startTime ? Math.round((Date.now() - startTime) / 1000) : 0;
      const guessRes = await flagdleService.makeGuess({
        country_id: countryId,
        guess: countryName,
        elapsed_seconds: elapsed,
      });

      const nextGuesses = [...get().guesses, guessRes];
      const isWon = guessRes.answer;
      const isGameOver = isWon || nextGuesses.length >= 6;
      const nextStage = isGameOver ? 6 : Math.min(6, nextGuesses.length + 1);

      const nextState: GameState = {
        ...gameState,
        guesses_made: nextGuesses.length,
        remaining_guesses: Math.max(0, 6 - nextGuesses.length),
        is_game_over: isGameOver,
        won: isWon,
      };

      // Local storage snapshot for guest continuity
      if (dailyDate) {
        localStorage.setItem(
          `guess_game_flagdle_${dailyDate}`,
          JSON.stringify({ state: nextState, guesses: nextGuesses })
        );
      }

      let revealedCountry = get().correctCountry;
      if (isGameOver) {
        const endState = await flagdleService.getEndState();
        revealedCountry = endState.country;
      }

      set({
        gameState: nextState,
        guesses: nextGuesses,
        stage: nextStage,
        correctCountry: revealedCountry,
        isLoading: false,
      });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  syncGuestData: async () => {
    const { dailyDate } = get();
    if (!dailyDate) return;
    const localKey = `guess_game_flagdle_${dailyDate}`;
    const localRaw = localStorage.getItem(localKey);
    if (!localRaw) return;

    try {
      const snapshot = JSON.parse(localRaw);
      await flagdleService.syncGuestData({
        date: dailyDate,
        state: snapshot.state,
        guesses: snapshot.guesses,
      });
      localStorage.removeItem(localKey);
      await get().fetchGameState();
    } catch (err) {
      console.error('Failed to sync Flagdle guest data', err);
    }
  },

  resetGame: () => {
    set({
      gameState: null,
      guesses: [],
      stage: 1,
      flagAssetUrl: null,
      correctCountry: null,
      isLoading: false,
      error: null,
    });
  },
}));
```

### 8.2 Guest History Extension (`client/src/lib/guestHistory.ts`)
Update `GuestGameType` union and `limits` dictionary:
```typescript
export type GuestGameType = 'country' | 'powiaty' | 'us_states' | 'wojewodztwa' | 'flagdle';

const limits: Record<GuestGameType, { questions: number; guesses: number }> = {
  country: { questions: 10, guesses: 3 },
  powiaty: { questions: 15, guesses: 3 },
  us_states: { questions: 8, guesses: 3 },
  wojewodztwa: { questions: 5, guesses: 2 },
  flagdle: { questions: 0, guesses: 6 },
};
```

---

## 9. Comprehensive Testing Strategy & Edge Cases

### 9.1 Edge Cases to Defend Against

1. **Non-Standard Aspect Ratios:**
   * *Nepal:* Double-pennant triangular flag. If rendered with `object-cover`, the outer boundary is truncated. *Test assertion:* Must use `object-contain` within an aspect-[3/2] bounding frame with transparent/neutral pillarbox padding.
   * *Switzerland & Vatican City:* 1:1 square flags. Must center cleanly without stretching.
2. **Missing Flag Colors in SQLite:**
   * Country 133 (Palestine) missing colors in `country_flag_colors`. *Test assertion:* Data migration script must execute idempotent insert; verify `SELECT COUNT(*) FROM country_flag_colors WHERE country_id=133` equals 4.
3. **Identical Colors / Disambiguation:**
   * Guessing Chad (`TD`) when target is Romania (`RO`). Both flags have vertical stripes: blue, yellow, red (Chad's blue is slightly darker, but in color taxonomy both are `blue`, `yellow`, `red`).
   * *Test assertion:* `matched_colors` returns `["blue", "red", "yellow"]`, `distance_km` returns ~4,200 km, `bearing_compass` returns `"N"`. Ensures player is guided geographically rather than being deadlocked.
4. **UTC Turnover Race Condition:**
   * Player starts Flagdle at 23:59 UTC and submits guess 2 at 00:01 UTC.
   * *Test assertion:* The guess endpoint must validate against the `day_id` associated with the active session token rather than naive `date.today()`, preventing mid-game target country swaps.
5. **Guest Login Sync Merging:**
   * Player plays 3 guesses as guest, then logs into existing account that already played 1 guess on another device.
   * *Test assertion:* Server state takes strict precedence to avoid illegal state counts (`guesses_made > 6`).

### 9.2 Backend Automated Test Suite (`server/tests/test_flagdle.py`)
```python
import pytest
from datetime import date
from httpx import AsyncClient
from db.models.country import Country
from db.models.flagdle import FlagdleDay, FlagdleState

@pytest.mark.asyncio
async def test_flagdle_daily_generation(db_session):
    from flagdle.crud import FlagdleRepository
    repo = FlagdleRepository(db_session)
    day = await repo.generate_new_day_flag(date(2026, 9, 22))
    assert day is not None
    assert day.country_id > 0
    assert day.date == date(2026, 9, 22)

@pytest.mark.asyncio
async def test_flagdle_state_isolation_anti_cheat(client: AsyncClient):
    """Verify target country ID and ISO2 are NEVER returned during active game."""
    res = await client.get("/flagdle/state")
    assert res.status_code == 200
    data = res.json()
    assert "country" in data
    assert data["country"] is None
    assert "country_id" not in data["state"]
    assert "fr.svg" not in data["flag_asset_url"]

@pytest.mark.asyncio
async def test_flagdle_clue_evaluation(db_session):
    from flagdle.evaluator import evaluate_flag_attributes, calculate_haversine_distance_and_bearing
    # Test Paris (48.85, 2.35) to Berlin (52.52, 13.40)
    dist, bearing, compass = calculate_haversine_distance_and_bearing(48.85, 2.35, 52.52, 13.40)
    assert 850 <= dist <= 900
    assert compass in ["NE", "ENE", "E"]

@pytest.mark.asyncio
async def test_flagdle_win_flow(client: AsyncClient, db_session):
    """Verify guessing correct country awards points and unlocks full end state."""
    # Fetch current day flag
    from flagdle.crud import FlagdleRepository
    repo = FlagdleRepository(db_session)
    day = await repo.get_day_flag_by_date(date.today())
    
    # Submit correct guess
    res = await client.post("/flagdle/guess", json={"country_id": day.country_id, "guess": "Target"})
    assert res.status_code == 200
    guess_data = res.json()
    assert guess_data["answer"] is True

    # Check end state
    end_res = await client.get("/flagdle/end/state")
    assert end_res.status_code == 200
    end_data = end_res.json()
    assert end_data["state"]["won"] is True
    assert end_data["state"]["is_game_over"] is True
    assert end_data["country"]["id"] == day.country_id
```

---

## 10. Step-by-Step Implementation Checklist

### Phase 1: Database & Data Pipeline
* [ ] **Fix SQLite Data Ingestion:** Run backfill script to insert missing Palestine (`country_id: 133`) colors (`red`, `white`, `green`, `black`) into `country_flag_colors`.
* [ ] **SQLAlchemy Models:** Create `server/db/models/flagdle.py` defining `FlagdleDay`, `FlagdleState`, `FlagdleGuess`.
* [ ] **Alembic Migration:** Generate and apply migration `alembic/versions/xxxx_add_flagdle_tables.py`.
* [ ] **Repositories:** Implement `server/db/repositories/flagdle.py` for atomic state transitions and guess persistence.

### Phase 2: Game Logic & Obfuscated Image Proxy
* [ ] **Clue Evaluator:** Implement `server/flagdle/evaluator.py` (Haversine distance, bearing, SQLite color/symbol comparison).
* [ ] **Scoring Engine:** Add `calculate_flagdle_points()` in `server/game_logic.py`.
* [ ] **Secure Image Proxy:** Create `server/flagdle/image_proxy.py` using `Pillow` to stream server-masked flag WebP tiles.
* [ ] **Daily Rotation Job:** Add `generate_day_flags` to `server/utils/__init__.py` on APScheduler (`hour=0, minute=0`).

### Phase 3: REST API Endpoints (`server/flagdle/`)
* [ ] Implement `GET /flagdle/state`: Initializes or fetches daily state (anti-cheat protected).
* [ ] Implement `POST /flagdle/guess`: Evaluates guess, calculates clues, updates remaining guesses.
* [ ] Implement `GET /flagdle/end/state`: Returns full country details and solution upon game over.
* [ ] Implement `POST /flagdle/sync`: Reconciles guest localStorage progress into user profile upon authentication.
* [ ] Implement `GET /flagdle/flag-asset`: Authenticated HMAC image proxy streaming masked flag.
* [ ] Register router in `server/app.py` under prefix `/flagdle`.

### Phase 4: Frontend State & Client Services
* [ ] **Types:** Add `FlagdleState`, `FlagdleGuess`, `FlagdleResponse` to `client/src/types/index.ts`.
* [ ] **API Service:** Add `flagdleService` in `client/src/services/api.ts`.
* [ ] **Zustand Store:** Add `useFlagdleGameStore` to `client/src/stores/gameStore.ts`.
* [ ] **Guest History:** Update `client/src/lib/guestHistory.ts` to support `'flagdle'` game mode and limits.

### Phase 5: Client Components & Routing
* [ ] **Flag Display:** Build `client/src/components/flagdle/FlagDisplay.tsx` with smooth CSS tile curtain unmasking.
* [ ] **Guess Input:** Build `client/src/components/flagdle/FlagdleGuessInput.tsx` with micro-flag preview icons.
* [ ] **Clue Timeline:** Build `client/src/components/flagdle/DeductionTimeline.tsx` showing distance, compass, colors, and emblems.
* [ ] **Result Card:** Build `client/src/components/flagdle/FlagdleResultCard.tsx` with one-click copyable emoji share grid.
* [ ] **Page Route:** Create `client/src/pages/FlagdlePage.tsx` and register route `/flagdle` in `client/src/App.tsx`.
* [ ] **Navigation Header:** Add Flagdle button with flag icon 🚩 to `Header.tsx` and homepage mode cards.

### Phase 6: Quality Gate & Launch Verification
* [ ] Execute backend test suite: `pytest server/tests/test_flagdle.py`.
* [ ] Verify DevTools network inspection: Ensure target country name and unmasked image URL are completely absent before game over.
* [ ] Test guest-to-account synchronization across browser tabs.
* [ ] Test mobile viewport layout on iOS Safari and Android Chrome across 1:1, 2:3, and non-standard flag aspect ratios.
