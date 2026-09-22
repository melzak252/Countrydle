# Continental Game Modes (Europedle, Asiadle, Africadle, Americadle) — Architecture & Implementation Plan

**Target File:** `todo/02-continental-modes.md`  
**Status:** Ready for Implementation  
**Affected Modules:**
- Backend Regional Engine: `server/continental/` (`__init__.py`, `crud.py`, `utils.py`, `scheduler.py`)
- Database Models & Migrations: `server/db/models/continental.py`, `server/alembic/versions/xxxx_add_continental_modes.py`
- Repositories: `server/db/repositories/continental.py`
- Pydantic Schemas: `server/schemas/continental.py`
- Question Answering & Knowledge Base: `server/countrydle/local_answering.py`, `server/countrydle/local_planner.py`, `data/country_facts.sqlite`
- Client Services: `client/src/services/api.ts`
- Client Stores & State Sync: `client/src/stores/gameStore.ts`, `client/src/lib/guestHistory.ts`, `client/src/types/index.ts`
- Client Map Components: `client/src/components/ContinentalMap.tsx`
- Client Pages & Routes: `client/src/pages/ContinentalGamePage.tsx`, `client/src/App.tsx`, `client/src/pages/HomePage.tsx`
- Navigation & Header: `client/src/components/Header.tsx`
- Internationalization: `client/src/i18n.ts`

---

## 1. Executive Summary & Vision

### 1.1 Expanding the Geography Deduction Universe
Countrydle's global game challenges players to deduce a single nation among 195 candidates using 10 questions and 3 guesses. While globally appealing, players consistently request focused regional challenges that test deeper geographic, political, and cultural knowledge of specific continents.

This feature introduces **4 new daily continental game modes**:
1. **Europedle (`/europe`)**: 47 European nations.
2. **Asiadle (`/asia`)**: 47 Asian nations.
3. **Africadle (`/africa`)**: 54 African nations.
4. **Americadle (`/americas`)**: 35 nations across North America (23) and South America (12).

### 1.2 Core Design Principles
1. **Calibrated Difficulty (8 Questions / 3 Guesses):** With search spaces compressed from 195 to between 35 and 54 nations, the question allowance is dialed down from 10 to 8. This preserves intellectual tension and demands sharp deductive inquiry without making the game trivially simple.
2. **Unified Regional Engine (Zero Duplicate Code Drift):** Rather than creating four redundant router silos (`server/europedle`, `server/asiadle`, etc.), the backend introduces a unified, parameterized continental engine (`server/continental/`) that shares schemas, state machines, guest sync, and answering pipelines across all four continents.
3. **Geographic Grounding & Transcontinental Integrity:** Transcontinental entities (Russia, Turkey, Kazakhstan, Egypt, Azerbaijan) follow strict, deterministic rules for daily puzzle selection, candidate guessing scope, border relationships, and question answering.
4. **Focused Continental Cartography:** Interactive Leaflet maps automatically frame each continent with optimized initial bounding boxes, custom camera viewports, and visual dampening of non-continental landmasses.
5. **Seamless Omnichannel Progression:** Guest progress is stored in `localStorage`, unified across tabs and sessions, and seamlessly synchronized to authenticated user accounts via `POST /continental/{continent}/sync`.

---

## 2. Mathematical Modeling & Game Mechanics

### 2.1 Information Theory & Question Allocation Analysis
In a guessing game with $N$ uniformly distributed candidates, the Shannon entropy $H$ representing the minimum number of binary (yes/no) questions required under optimal bisection is:
$$H = \log_2(N)$$

| Game Mode | Candidate Count ($N$) | Theoretical Minimum $\lceil \log_2(N) \rceil$ | Allowed Questions | Allowed Guesses | Information Capacity ($2^Q$) | Safety Margin Ratio ($2^Q / N$) |
|---|---|---|---|---|---|---|
| **Countrydle (Global)** | 195 | 8 | 10 | 3 | 1024 | $5.25\times$ |
| **Europedle** | 47 | 6 | **8** | **3** | 256 | $5.45\times$ |
| **Asiadle** | 47 | 6 | **8** | **3** | 256 | $5.45\times$ |
| **Africadle** | 54 | 6 | **8** | **3** | 256 | $4.74\times$ |
| **Americadle** | 35 | 6 | **8** | **3** | 256 | $7.31\times$ |

#### Why 8 Questions is the Optimal Number:
- In real play, geography questions rarely achieve a perfect 50/50 partition (e.g. asking "Does it have access to the sea?" eliminates ~15% to 30% of countries, not 50%).
- An allowance of 6 questions would demand flawless bisection with zero margin for exploratory questions (e.g., asking about religion, language family, or flag colors).
- 10 questions (the global standard) makes 35–54 country spaces trivial, as players easily guess by brute-force narrowing.
- **8 questions provides exactly 2 exploration/margin-of-error turns beyond the theoretical 6**, producing an engaging experience where deductive skill is rewarded and sloppy play is penalized.

### 2.2 Continental Scoring Engine
Scoring follows the non-linear Countrydle competitive standard, parameterized for `max_questions = 8` and `max_guesses = 3`:

$$S_{\text{total}} = S_{\text{base}} + S_{\text{question}} + S_{\text{guess}} + S_{\text{speed}} + S_{\text{streak}}$$

1. **Base Win Floor ($S_{\text{base}}$):** `+500` points for any successful victory.
2. **Question Efficiency Bonus ($S_{\text{question}}$):** Rewards solving with fewer questions using an exponential curve ($q = \text{questions asked}$):
   $$S_{\text{question}} = \text{round}\left(1500 \times \left(\frac{8 - q}{8}\right)^{1.5}\right)$$
   - 0 questions used: $+1,500$ pts
   - 1 question used: $+1,235$ pts
   - 2 questions used: $+974$ pts
   - 4 questions used: $+530$ pts
   - 7 questions used: $+66$ pts
   - 8 questions used: $+0$ pts
3. **Guess Accuracy Bonus ($S_{\text{guess}}$):** Rewards high confidence on the first guess ($g = \text{guesses made}$):
   $$S_{\text{guess}} = \text{round}\left(500 \times \frac{3 - g + 1}{3}\right)$$
   - Guess 1 (1st try): $+500$ pts
   - Guess 2 (2nd try): $+333$ pts
   - Guess 3 (3rd try): $+167$ pts
4. **Speed Bonus ($S_{\text{speed}}$):** 0 to 300 points, decaying linearly over 5 minutes (300 seconds):
   $$S_{\text{speed}} = \max(0, \min(300, 300 - \text{elapsed\_seconds}))$$
5. **Daily Streak Bonus ($S_{\text{streak}}$):** $+50$ points per consecutive daily victory, capped at $+500$ points (at 10-day streak).

**Theoretical Maximum Score:** $500 + 1500 + 500 + 300 + 500 = \mathbf{3,300\text{ points}}$.

---

## 3. Candidate Datasets & Continental Scope

All candidate definitions strictly originate from `data/country_facts.sqlite` (tables: `countries` and `country_continents`).

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        DATA/COUNTRY_FACTS.SQLITE                              │
├───────────────────┬───────────────────┬───────────────────┬───────────────────┤
│ Europe (47)       │ Asia (47)         │ Africa (54)       │ Americas (35)     │
├───────────────────┼───────────────────┼───────────────────┼───────────────────┤
│ Albania           │ Afghanistan       │ Algeria           │ North America (23)│
│ Andorra           │ Armenia           │ Angola            │ Antigua & Barbuda │
│ Austria           │ Azerbaijan*       │ Benin             │ Bahamas           │
│ Azerbaijan*       │ Bahrain           │ Botswana          │ Barbados          │
│ Belarus           │ Bangladesh        │ Burkina Faso      │ Belize            │
│ Belgium           │ Bhutan            │ Burundi           │ Canada            │
│ Bosnia & Herz.    │ Brunei            │ Cameroon          │ Costa Rica        │
│ Bulgaria          │ Cambodia          │ Cape Verde        │ Cuba              │
│ Croatia           │ China             │ Central African R.│ Dominica          │
│ Cyprus            │ Georgia           │ Chad              │ Dominican Republic│
│ Czech Republic    │ India             │ Comoros           │ El Salvador       │
│ Denmark           │ Indonesia         │ Dem. Rep. Congo   │ Grenada           │
│ Estonia           │ Iran              │ Djibouti          │ Guatemala         │
│ Finland           │ Iraq              │ Egypt*            │ Haiti             │
│ France            │ Israel            │ Equatorial Guinea │ Honduras          │
│ Germany           │ Japan             │ Eritrea           │ Jamaica           │
│ Greece            │ Jordan            │ Eswatini          │ Mexico            │
│ Hungary           │ Kazakhstan*       │ Ethiopia          │ Nicaragua         │
│ Iceland           │ Kuwait            │ Gabon             │ Panama            │
│ Ireland           │ Kyrgyzstan        │ Gambia            │ St Kitts & Nevis  │
│ Italy             │ Laos              │ Ghana             │ Saint Lucia       │
│ Latvia            │ Lebanon           │ Guinea            │ St Vincent & Gren.│
│ Liechtenstein     │ Malaysia          │ Guinea-Bissau     │ Trinidad & Tobago │
│ Lithuania         │ Maldives          │ Ivory Coast       │ United States     │
│ Luxembourg        │ Mongolia          │ Kenya             │                   │
│ Malta             │ Myanmar           │ Lesotho           │ South America (12)│
│ Moldova           │ Nepal             │ Liberia           │ Argentina         │
│ Monaco            │ North Korea       │ Libya             │ Bolivia           │
│ Montenegro        │ Oman              │ Madagascar        │ Brazil            │
│ Netherlands       │ Pakistan          │ Malawi            │ Chile             │
│ North Macedonia   │ Palestine         │ Mali              │ Colombia          │
│ Norway            │ Philippines       │ Mauritania        │ Ecuador           │
│ Poland            │ Qatar             │ Mauritius         │ Guyana            │
│ Portugal          │ Russia*           │ Morocco           │ Paraguay          │
│ Romania           │ Saudi Arabia      │ Mozambique        │ Peru              │
│ Russia*           │ Singapore         │ Namibia           │ Suriname          │
│ San Marino        │ South Korea       │ Niger             │ Uruguay           │
│ Serbia            │ Sri Lanka         │ Nigeria           │ Venezuela         │
│ Slovakia          │ Syria             │ Rep. of the Congo │                   │
│ Slovenia          │ Tajikistan        │ Rwanda            │                   │
│ Spain             │ Thailand          │ Senegal           │                   │
│ Sweden            │ Turkey*           │ Seychelles        │                   │
│ Switzerland       │ Turkmenistan      │ Sierra Leone      │                   │
│ Turkey*           │ UAE               │ Somalia           │                   │
│ Ukraine           │ Uzbekistan        │ South Africa      │                   │
│ United Kingdom    │ Vietnam           │ South Sudan       │                   │
│ Vatican City      │ Yemen             │ Sudan             │                   │
│                   │                   │ São Tomé & Prínc. │                   │
│                   │                   │ Tanzania          │                   │
│                   │                   │ Togo              │                   │
│                   │                   │ Tunisia           │                   │
│                   │                   │ Uganda            │                   │
│                   │                   │ Zambia            │                   │
│                   │                   │ Zimbabwe          │                   │
└───────────────────┴───────────────────┴───────────────────┴───────────────────┘
* Denotes transcontinental or regionally dual entities.
```

---

## 4. Transcontinental Countries & Disputed Regions

### 4.1 The Transcontinental Reality Matrix
Geography features several nations spanning continental divides:

| Country | Primary / Political Affiliation | Geographic Span | `country_continents` DB Entry | Eligible Modes |
|---|---|---|---|---|
| **Russia** | Europe (Capital, culture, 77% population) | Europe (west of Urals) & Asia (Siberia) | `'Europe'`, `'Asia'` | Europedle, Asiadle |
| **Turkey** | Europe / Asia | East Thrace (Europe) & Anatolia (Asia) | `'Europe'`, `'Asia'` | Europedle, Asiadle |
| **Azerbaijan** | Europe / Asia (Caucasus) | Europe (north of watershed) & Asia | `'Europe'`, `'Asia'` | Europedle, Asiadle |
| **Kazakhstan** | Central Asia | Asia & Europe (west of Ural River: Atyrau/W. Kaz.) | `'Asia'` (in DB) | Asiadle (Target); Europedle (see below) |
| **Egypt** | Africa | Africa & Asia (Sinai Peninsula east of Suez) | `'Africa'` (in DB) | Africadle (Target); Asiadle (see below) |
| **Georgia** | Europe / Asia (Caucasus) | South Caucasus (Asia / European Council) | `'Asia'` (in DB) | Asiadle |
| **Armenia** | Europe / Asia (Caucasus) | Transcaucasia (Geographically Asia, culturally Europe)| `'Asia'` (in DB) | Asiadle |
| **Cyprus** | Europe (EU Member) | Mediterranean (Geographically Asia, politically Europe)| `'Europe'` (in DB) | Europedle |

### 4.2 Rules for Continental Modes

#### Rule 1: Secret Target Eligibility
- A country can be chosen as the daily secret target in a continental mode if and only if it is registered in that continent's candidate list.
- **Russia**, **Turkey**, and **Azerbaijan** can be targets in either **Europedle** or **Asiadle**.
- **Egypt** can be the target in **Africadle**.
- **Kazakhstan** can be the target in **Asiadle**.
- **Anti-Collision Constraint (Same-Day Exclusion):** If Russia is selected as today's target in Europedle, it is strictly disqualified from being today's target in Asiadle. A transcontinental country cannot be the active puzzle in two modes on the same UTC date.

#### Rule 2: Guess Input Whitelist Enforcement
- Autocomplete dropdowns and guess submission endpoints strictly enforce the continent's country pool:
  - Submitting a guess outside the mode's candidate list returns `400 Bad Request`:
    `{"detail": "Candidate '{guess}' is not an eligible country in {mode}."}`
  - Example: A player in Europedle can guess **Russia** or **Turkey**, but cannot guess **Egypt** or **Brazil**.
  - A player in Asiadle can guess **Russia**, **Turkey**, or **Japan**, but cannot guess **Germany**.

#### Rule 3: Target-Centric Absolute Question Answering
Questions in continental modes are answered based on the **absolute factual reality of the secret country**, NOT relative to the mode boundary.
- **Scenario A (Target is Russia in Europedle):**
  - Player asks: *"Is the country in Europe?"* $\to$ **YES** (`Russia is located in Europe and Asia`).
  - Player asks: *"Is the country in Asia?"* $\to$ **YES** (`Russia is located in Europe and Asia`).
  - Player asks: *"Is the country transcontinental?"* $\to$ **YES**.
  - Player asks: *"Does it border an Asian country?"* $\to$ **YES** (Borders China, Mongolia, Kazakhstan, North Korea, etc.).
  - Player asks: *"Does it border Poland?"* $\to$ **YES** (Via Kaliningrad Oblast).
- **Scenario B (Target is Germany in Europedle):**
  - Player asks: *"Is the country in Asia?"* $\to$ **NO** (`Germany is located in Europe`).
- **Scenario C (Target is Egypt in Africadle):**
  - Player asks: *"Does the country have territory in Asia?"* $\to$ **YES** (`Egypt includes the Sinai Peninsula in Asia`).
  - Player asks: *"Does it border an Asian country?"* $\to$ **YES** (`Egypt borders Israel and Palestine`).

#### Rule 4: Border & Continental Edge Queries
Border verification queries resolve against `country_borders` in `data/country_facts.sqlite`.
- When checking if Country $A$ borders Country $B$, the physical border is verified regardless of whether Country $B$ is part of the current continental mode.
  - In Europedle, asking *"Does it border China?"* correctly yields **YES** if the secret target is Russia, even though China is not in Europedle.

---

## 5. Backend Architecture: Unified Regional Engine

### 5.1 Monolithic Routers vs. Unified Regional Engine
Before coding, we evaluate two architectural paths:

| Factor | Option A: Individual Siloed Routers (`/europedle`, `/asiadle`, etc.) | Option B: Unified Parameterized Engine (`/continental/{continent}/`) | Verdict |
|---|---|---|---|
| **Code Duplication** | 4 copies of state machines, guest sync, schemas, and endpoints (~2,000 duplicated LOC). | 1 centralized generic engine (~500 LOC) parameterized by `ContinentEnum`. | **Option B wins** |
| **Database Schema** | 16 new tables (4 tables $\times$ 4 modes) or messy table sprawl. | 4 clean normalized tables with `continent` discriminator column. | **Option B wins** |
| **Scheduler Maintenance** | 4 separate cron jobs needing individual error handling. | 1 atomic daily rotation job running over `ContinentEnum.all()`. | **Option B wins** |
| **Client Service Integration**| 4 distinct API service objects in frontend. | 1 generic `createContinentalService(continent)` factory. | **Option B wins** |
| **Migration Risk** | Massive Alembic script with high chance of typo drift across tables. | Single concise migration with indexing on `(continent, date)`. | **Option B wins** |

**Decision:** We implement **Option B: Unified Parameterized Engine** under `server/continental/`.

### 5.2 Database Models (`server/db/models/continental.py`)

Using PostgreSQL 17 with Async SQLAlchemy:

```python
from datetime import date
from enum import StrEnum
from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from db.base import Base

class ContinentCode(StrEnum):
    EUROPE = "europe"
    ASIA = "asia"
    AFRICA = "africa"
    AMERICAS = "americas"

class ContinentalDay(Base):
    __tablename__ = "continental_days"

    id = Column(Integer, primary_key=True, index=True)
    continent = Column(Enum(ContinentCode, name="continent_code_enum", values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    date = Column(Date, nullable=False, default=func.now(), index=True)

    country = relationship("Country")

    __table_args__ = (
        UniqueConstraint("continent", "date", name="uq_continental_days_continent_date"),
    )

class ContinentalState(Base):
    __tablename__ = "continental_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id"), nullable=False, index=True)
    remaining_questions = Column(Integer, nullable=False, default=8)
    remaining_guesses = Column(Integer, nullable=False, default=3)
    questions_asked = Column(Integer, nullable=False, default=0)
    guesses_made = Column(Integer, nullable=False, default=0)
    is_game_over = Column(Boolean, nullable=False, default=False)
    won = Column(Boolean, nullable=False, default=False)
    points = Column(Integer, nullable=False, default=0)

    user = relationship("User")
    day = relationship("ContinentalDay")

    __table_args__ = (
        UniqueConstraint("user_id", "day_id", name="uq_continental_states_user_day"),
    )

class ContinentalGuess(Base):
    __tablename__ = "continental_guesses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id"), nullable=False, index=True)
    guess = Column(String, nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    guessed_at = Column(DateTime, server_default=func.now(), nullable=False)
    answer = Column(Boolean, nullable=False)
    elapsed_seconds = Column(Integer, nullable=True)

    user = relationship("User")
    day = relationship("ContinentalDay")
    country = relationship("Country")

class ContinentalQuestion(Base):
    __tablename__ = "continental_questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    day_id = Column(Integer, ForeignKey("continental_days.id"), nullable=False, index=True)
    original_question = Column(String, nullable=False)
    question = Column(String, nullable=True)
    valid = Column(Boolean, nullable=False)
    answer = Column(Boolean, nullable=True)
    explanation = Column(String, nullable=True)
    context = Column(String, nullable=True)
    asked_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    day = relationship("ContinentalDay")
```

### 5.3 Daily Rotation Scheduler (`server/continental/scheduler.py`)
Integrated into `server/utils/__init__.py` using APScheduler:

```python
import random
from datetime import date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.continental import ContinentCode, ContinentalDay
from db.repositories.country import CountryRepository
from server.continental.utils import get_continent_country_ids

COOLDOWN_DAYS = {
    ContinentCode.EUROPE: 35,
    ContinentCode.ASIA: 35,
    ContinentCode.AFRICA: 40,
    ContinentCode.AMERICAS: 25,
}

async def generate_continental_days(session: AsyncSession):
    """Generate daily puzzles for Europe, Asia, Africa, and Americas for the next 5 days."""
    today = date.today()
    for offset in range(5):
        day_date = today + timedelta(days=offset)
        
        # Track countries chosen on this specific day across continents to prevent same-day collisions
        chosen_today_country_ids = set()

        # Check existing entries for day_date
        existing_res = await session.execute(
            select(ContinentalDay).where(ContinentalDay.date == day_date)
        )
        existing_days = {d.continent: d for d in existing_res.scalars().all()}
        for d in existing_days.values():
            chosen_today_country_ids.add(d.country_id)

        for continent in ContinentCode:
            if continent in existing_days:
                continue

            cooldown = COOLDOWN_DAYS[continent]
            recent_res = await session.execute(
                select(ContinentalDay.country_id)
                .where(and_(
                    ContinentalDay.continent == continent,
                    ContinentalDay.date >= day_date - timedelta(days=cooldown),
                    ContinentalDay.date < day_date
                ))
            )
            recent_ids = set(recent_res.scalars().all())

            # Fetch candidate countries for this continent
            candidate_ids = await get_continent_country_ids(continent)
            
            # Eligible = candidate - recent cooldown - countries already picked today in other continental modes
            eligible_ids = [
                cid for cid in candidate_ids 
                if cid not in recent_ids and cid not in chosen_today_country_ids
            ]
            
            # Fallback if over-constrained
            if not eligible_ids:
                eligible_ids = [cid for cid in candidate_ids if cid not in chosen_today_country_ids]
            if not eligible_ids:
                eligible_ids = candidate_ids

            selected_id = random.choice(eligible_ids)
            chosen_today_country_ids.add(selected_id)

            new_day = ContinentalDay(
                continent=continent,
                country_id=selected_id,
                date=day_date
            )
            session.add(new_day)

    await session.commit()
```

---

## 6. Maps, Viewports & Leaflet Cartography

### 6.1 Viewports & Max Bounds Table
The interactive map uses `client/public/countries_50m.geojson`. To ensure fast loading, no heavy tilesets or separate GeoJSON downloads are needed. Instead, the map component focuses on the targeted continent via camera bounds:

| Continent | Center `[lat, lng]` | Desktop Zoom | Mobile Zoom | FitBounds Box `[[S, W], [N, E]]` | Visual Extent |
|---|---|---|---|---|---|
| **Europe** | `[54.5260, 15.2551]` | `4` | `3` | `[[34.0, -25.0], [71.5, 45.0]]` | Iceland, Azores, Portugal to Urals & Caucasus |
| **Asia** | `[34.0479, 100.6197]` | `3` | `2` | `[[-11.0, 26.0], [77.0, 150.0]]` | Levant & Arabian Peninsula to Japan & Indonesia |
| **Africa** | `[1.6508, 17.6791]` | `3` | `2.2`| `[[-35.5, -18.0], [37.5, 52.0]]` | Mediterranean coast to Cape Town, Cape Verde to Madagascar |
| **Americas** | `[15.0000, -85.0000]` | `2.5` | `1.8`| `[[-56.0, -170.0], [72.0, -30.0]]` | Alaska & Canada through Central America to Tierra del Fuego |

### 6.2 Visual Layering Architecture
```
┌────────────────────────────────────────────────────────┐
│ Leaflet MapContainer (World Dark Base)                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1. Out-of-Scope Countries (Background Context)   │  │
│  │    Fill: #18181b (zinc-900), Opacity: 0.25       │  │
│  │    Stroke: 1px solid #27272a, Non-interactive   │  │
│  │    pointerEvents: 'none', No hover/tooltip       │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 2. In-Scope Continental Candidates               │  │
│  │    - Neutral: Fill #27272a, Stroke: 1px #52525b  │  │
│  │    - Candidate: Fill #10b981 (Emerald), Glow     │  │
│  │    - Eliminated: Ghosted + diagonal hatch        │  │
│  │    - Correct: Fill #22c55e (Green), Pulse badge  │  │
│  │    Interactive: Hover brings to front, Tooltips  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 3. Continental Controls & Camera FlyTo           │  │
│  │    [Reset View] [Clear Selection] [Zoom Answer]  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 7. Client Integration & UX Specifications

### 7.1 URLs & Route Structure
- `/europe` $\to$ Europedle
- `/asia` $\to$ Asiadle
- `/africa` $\to$ Africadle
- `/americas` $\to$ Americadle

All routes render `<ContinentalGamePage continent={ContinentCode.EUROPE} />`, keeping view logic 100% DRY.

### 7.2 Home Page Cards (`client/src/pages/HomePage.tsx`)
The home page grid is enhanced with distinct badges, entity counts, and deduction limits:

```tsx
const continentalGames = [
  {
    id: 'europe',
    title: 'Europedle',
    region: 'Europe',
    badge: '47 European Nations · 8 Questions · 3 Guesses',
    description: 'From Nordic fjords to Mediterranean archipelagos. Find the mystery European country.',
    path: '/europe',
    icon: Compass,
    questions: 8,
    guesses: 3,
    count: 47,
  },
  {
    id: 'asia',
    title: 'Asiadle',
    region: 'Asia',
    badge: '47 Asian Nations · 8 Questions · 3 Guesses',
    description: 'Steppes, islands, and ancient civilizations. Pinpoint the hidden Asian nation.',
    path: '/asia',
    icon: Globe2,
    questions: 8,
    guesses: 3,
    count: 47,
  },
  {
    id: 'africa',
    title: 'Africadle',
    region: 'Africa',
    badge: '54 African Nations · 8 Questions · 3 Guesses',
    description: 'Deserts, savannas, and vibrant cultures. Discover today’s mystery African country.',
    path: '/africa',
    icon: Sun,
    questions: 8,
    guesses: 3,
    count: 54,
  },
  {
    id: 'americas',
    title: 'Americadle',
    region: 'The Americas',
    badge: '35 Nations (23 North + 12 South) · 8 Questions · 3 Guesses',
    description: 'Spanning from the Arctic tundra to Patagonia. Uncover the mystery American state.',
    path: '/americas',
    icon: Map,
    questions: 8,
    guesses: 3,
    count: 35,
  },
];
```

### 7.3 Navigation Dropdown (`client/src/components/Header.tsx`)
The dropdown menu is restructured into two elegant sub-sections:

```
Games ▾
├── GLOBAL & CONTINENTS
│   ├── 🌍 World Map (Countrydle)   [/game]
│   ├── 🏰 Europedle                [/europe]
│   ├── 🏯 Asiadle                  [/asia]
│   ├── 🏜️ Africadle                [/africa]
│   └── 🌎 Americadle               [/americas]
└── REGIONAL & SPECIALIZED
    ├── 🗽 US States                [/us-states]
    ├── 🦅 Polish Counties (Powiaty)[/powiaty]
    └── 🇵🇱 Polish Voivodeships      [/wojewodztwa]
```

### 7.4 Internationalization (i18n) Support
Add full translation keys in `client/src/i18n.ts` for English (`en`) and Polish (`pl`):

```typescript
// English
europeTitle: 'Europedle',
asiaTitle: 'Asiadle',
africaTitle: 'Africadle',
americasTitle: 'Americadle',
europeSubtitle: '47 European Nations · 8 Questions · 3 Guesses',
asiaSubtitle: '47 Asian Nations · 8 Questions · 3 Guesses',
africaSubtitle: '54 African Nations · 8 Questions · 3 Guesses',
americasSubtitle: '35 American Nations · 8 Questions · 3 Guesses',
askPlaceholder: 'Ask a yes/no question about the country... ({{count}} left)',
guessPlaceholder: 'Guess the country... ({{count}} left)',

// Polish
europeTitle: 'Europedle',
asiaTitle: 'Asiadle',
africaTitle: 'Africadle',
americasTitle: 'Americadle',
europeSubtitle: '47 państw europejskich · 8 pytań · 3 próby',
asiaSubtitle: '47 państw azjatyckich · 8 pytań · 3 próby',
africaSubtitle: '54 państwa afrykańskie · 8 pytań · 3 próby',
americasSubtitle: '35 państw obu Ameryk · 8 pytań · 3 próby',
askPlaceholder: 'Zadaj pytanie tak/nie o ukryte państwo... (zostało {{count}})',
guessPlaceholder: 'Odgadnij państwo... (zostało {{count}})',
```

---

## 8. Zustand Store Factory Extensions

### 8.1 Extending `GuestGameType` (`client/src/lib/guestHistory.ts`)
```typescript
export type GuestGameType = 
  | 'country' 
  | 'powiaty' 
  | 'us_states' 
  | 'wojewodztwa'
  | 'europe'
  | 'asia'
  | 'africa'
  | 'americas';

const limits: Record<GuestGameType, { questions: number; guesses: number }> = {
  country: { questions: 10, guesses: 3 },
  powiaty: { questions: 15, guesses: 3 },
  us_states: { questions: 8, guesses: 3 },
  wojewodztwa: { questions: 5, guesses: 2 },
  europe: { questions: 8, guesses: 3 },
  asia: { questions: 8, guesses: 3 },
  africa: { questions: 8, guesses: 3 },
  americas: { questions: 8, guesses: 3 },
};
```

### 8.2 Store Instantiation (`client/src/stores/gameStore.ts`)
```typescript
export const useEuropeGameStore = createGameStore('europe');
export const useAsiaGameStore = createGameStore('asia');
export const useAfricaGameStore = createGameStore('africa');
export const useAmericasGameStore = createGameStore('americas');

// Map helper to fetch store dynamically by continent
export const getContinentalStore = (continent: 'europe' | 'asia' | 'africa' | 'americas') => {
  switch (continent) {
    case 'europe': return useEuropeGameStore;
    case 'asia': return useAsiaGameStore;
    case 'africa': return useAfricaGameStore;
    case 'americas': return useAmericasGameStore;
  }
};
```

### 8.3 Client API Service (`client/src/services/api.ts`)
```typescript
export const createContinentalService = (continent: string) => ({
  getState: async (): Promise<GameResponse> => {
    const response = await api.get(`/continental/${continent}/state`);
    return response.data;
  },
  getCountries: async (): Promise<CountryDisplay[]> => {
    const response = await api.get(`/continental/${continent}/countries`);
    return response.data;
  },
  askQuestion: async (question: string): Promise<Question> => {
    const response = await api.post(`/continental/${continent}/question`, { question });
    return response.data;
  },
  makeGuess: async (guess: string, country_id?: number, elapsed_seconds?: number): Promise<Guess> => {
    const response = await api.post(`/continental/${continent}/guess`, { guess, country_id, elapsed_seconds });
    return response.data;
  },
  getLeaderboard: async (type: 'monthly' | 'average' = 'monthly'): Promise<any[]> => {
    const response = await api.get(`/continental/${continent}/leaderboard?type=${type}`);
    return response.data;
  },
  getHistory: async (): Promise<any[]> => {
    const response = await api.get(`/continental/${continent}/history`);
    return response.data;
  },
  syncGuestData: async (data: any): Promise<GameResponse> => {
    const response = await api.post(`/continental/${continent}/sync`, data);
    return response.data;
  },
  reveal: async (): Promise<CountryDisplay> => {
    const response = await api.get(`/continental/${continent}/reveal`);
    return response.data;
  },
});

export const europeService = createContinentalService('europe');
export const asiaService = createContinentalService('asia');
export const africaService = createContinentalService('africa');
export const americasService = createContinentalService('americas');
```

---

## 9. API Specifications

All endpoints are mounted under `/continental/{continent}` where `continent` is one of `europe`, `asia`, `africa`, `americas`.

### 9.1 `GET /continental/{continent}/state`
Returns the active daily game state for the requesting user or guest.
- **Headers:** `Cookie: access_token=...` (optional for authenticated users).
- **Response `200 OK` (Active Game):**
```json
{
  "user": { "id": 42, "username": "explorer" },
  "date": "2026-09-22",
  "state": {
    "id": 108,
    "user_id": 42,
    "day_id": 34,
    "remaining_questions": 6,
    "remaining_guesses": 3,
    "questions_asked": 2,
    "guesses_made": 0,
    "is_game_over": false,
    "won": false,
    "points": 0
  },
  "guesses": [],
  "questions": [
    {
      "id": 1012,
      "original_question": "Does it border Germany?",
      "question": "Does the country border Germany?",
      "valid": true,
      "answer": true,
      "explanation": "Poland shares a border with Germany.",
      "asked_at": "2026-09-22T08:14:00Z"
    }
  ],
  "country": null
}
```
- **Response `200 OK` (Game Over):**
Includes the revealed country:
```json
{
  ...
  "state": {
    ...
    "is_game_over": true,
    "won": true,
    "points": 2450
  },
  "country": {
    "id": 34,
    "name": "Poland",
    "official_name": "Republic of Poland",
    "capital": "Warsaw"
  }
}
```

### 9.2 `POST /continental/{continent}/question`
Submits a yes/no question evaluated via local KB and Gemini fallback.
- **Request Body:**
```json
{
  "question": "Is the country landlocked?"
}
```
- **Response `200 OK`:**
```json
{
  "id": 1013,
  "original_question": "Is the country landlocked?",
  "question": "Is the country landlocked?",
  "valid": true,
  "answer": false,
  "explanation": "Poland has a coastline along the Baltic Sea.",
  "asked_at": "2026-09-22T08:15:30Z"
}
```

### 9.3 `POST /continental/{continent}/guess`
Submits a country guess.
- **Request Body:**
```json
{
  "guess": "Poland",
  "country_id": 34,
  "elapsed_seconds": 45
}
```
- **Response `200 OK` (Correct Guess):**
```json
{
  "id": 512,
  "guess": "Poland",
  "country_id": 34,
  "answer": true,
  "guessed_at": "2026-09-22T08:16:00Z",
  "is_game_over": true,
  "won": true,
  "points": 2450
}
```
- **Error `400 Bad Request` (Invalid Continental Candidate):**
```json
{
  "detail": "Candidate 'Brazil' is not an eligible country in Europedle."
}
```

### 9.4 `POST /continental/{continent}/sync`
Synchronizes guest actions played in localStorage to the user's persistent DB account.
- **Request Body:**
```json
{
  "date": "2026-09-22",
  "state": {
    "remaining_questions": 6,
    "remaining_guesses": 2,
    "questions_asked": 2,
    "guesses_made": 1,
    "is_game_over": false,
    "won": false
  },
  "questions": [1012, 1013],
  "guesses": [
    { "guess": "Czech Republic", "country_id": 22 }
  ]
}
```

### 9.5 `GET /continental/{continent}/countries`
Returns the exact whitelist of eligible countries for the mode's autocomplete dropdown.
- **Response `200 OK`:**
```json
[
  { "id": 2, "name": "Albania", "cca2": "AL", "cca3": "ALB" },
  { "id": 4, "name": "Andorra", "cca2": "AD", "cca3": "AND" }
]
```

---

## 10. Step-by-Step Implementation & TDD Checklist

### Phase 1: Database & Migration
- [ ] Create Alembic migration `server/alembic/versions/xxxx_add_continental_modes.py`.
- [ ] Define tables: `continental_days`, `continental_states`, `continental_guesses`, `continental_questions`.
- [ ] Add unique constraint `(continent, date)` on `continental_days`.
- [ ] Add unique constraint `(user_id, day_id)` on `continental_states`.
- [ ] Execute `alembic upgrade head` and verify SQLite / Postgres tables.

### Phase 2: Backend Regional Engine & Repositories
- [ ] Implement `server/continental/utils.py` with `get_continent_country_ids(continent: ContinentCode)`.
- [ ] Implement repository `server/db/repositories/continental.py`:
  - `get_today_continental_day(continent)`
  - `get_day_by_date(continent, date)`
  - `get_or_create_state(user, day)`
  - `record_guess(user, day, guess, is_correct, elapsed_seconds)`
  - `record_question(user, day, question_data)`
  - `get_leaderboard(continent, type)`
- [ ] Configure `CONTINENTAL_CONFIG = GameConfig(max_questions=8, max_guesses=3)` in `server/game_logic.py`.
- [ ] Implement FastAPI router in `server/continental/__init__.py`.
- [ ] Mount `/continental` router in `server/app.py`.

### Phase 3: Daily Rotation Scheduler & Transcontinental Rules
- [ ] Implement `generate_continental_days` in `server/continental/scheduler.py`.
- [ ] Add `AsyncIOScheduler` cron trigger at `00:00 UTC` in `server/utils/__init__.py`.
- [ ] Implement anti-collision check to prevent the same country from appearing in two continental modes on the same day.
- [ ] Implement per-continent cooldown checks (35 days for Europe/Asia, 40 for Africa, 25 for Americas).
- [ ] Verify transcontinental answering rules against `server/countrydle/local_answering.py`.

### Phase 4: Client Stores, Services & Guest Sync
- [ ] Add continental types to `client/src/types/index.ts`.
- [ ] Extend `GuestGameType` in `client/src/lib/guestHistory.ts`.
- [ ] Update `gameLimits` and `guessMapping` in `client/src/stores/gameStore.ts`.
- [ ] Export `useEuropeGameStore`, `useAsiaGameStore`, `useAfricaGameStore`, and `useAmericasGameStore`.
- [ ] Implement `createContinentalService` in `client/src/services/api.ts`.
- [ ] Add guest history listeners and sync triggers in `client/src/App.tsx`.

### Phase 5: Continental Map Component & Responsive Viewports
- [ ] Create `client/src/components/ContinentalMap.tsx`:
  - Parameterized by `continent: ContinentCode`.
  - Configures initial center, zoom, and `maxBounds`.
  - Filters `countries_50m.geojson` into active continental features vs. dark background context.
  - Supports candidate selection, elimination hatch, and green victory reveal.
  - Implements `ZoomToCorrect` flyTo animation on game over.

### Phase 6: Game Page, Home Cards, Header & i18n
- [ ] Create `client/src/pages/ContinentalGamePage.tsx` parameterized by route param or prop.
- [ ] Register routes `/europe`, `/asia`, `/africa`, `/americas` in `client/src/App.tsx`.
- [ ] Update `client/src/pages/HomePage.tsx` with 4 new game cards showing entity counts and 8Q/3G badges.
- [ ] Restructure games dropdown in `client/src/components/Header.tsx` (Global vs. Regional grouping).
- [ ] Add full English and Polish dictionaries in `client/src/i18n.ts`.

### Phase 7: Verification & Automated Test Matrix
- [ ] **Unit Tests (`server/tests/test_continental_rules.py`):**
  - Verify question limit (8) and guess limit (3) enforcement.
  - Verify scoring calculations match calibrated formula.
  - Verify candidate validation rejects out-of-scope guesses with HTTP 400.
- [ ] **Transcontinental Tests (`server/tests/test_transcontinental.py`):**
  - Verify Russia and Turkey can be generated in both Europe and Asia.
  - Verify anti-collision prevents Russia in Europe and Asia on the same date.
  - Verify "Is it in Asia?" returns True for Russia in Europedle.
- [ ] **Integration Tests (`server/tests/test_continental_api.py`):**
  - Test `/continental/europe/state` for guest and authenticated user.
  - Test `/continental/europe/question` deducting turns properly.
  - Test `/continental/europe/sync` reconciling guest local progress.
- [ ] **Frontend Smoke Tests (`client/src/tests/ContinentalGame.test.tsx`):**
  - Verify map renders correct bounds per continent.
  - Verify autocomplete dropdown displays only 47/47/54/35 countries.

---

## 11. Rollout & Monitoring

1. **Pre-Launch Database Seed:** Run `generate_continental_days` manually via CLI script to populate the first 14 days of puzzles before deploying.
2. **Sitemap Update:** Add `/europe`, `/asia`, `/africa`, and `/americas` to dynamic sitemap in `server/app.py` for search crawler indexing.
3. **Analytics & Performance Guardrails:**
   - Monitor question latency on `/continental/{continent}/question` to ensure P95 stays under 250ms for local KB answers.
   - Track win rates per continent (expected: 60–75% for experienced geography players under the 8Q/3G rules).
4. **AdSense & SEO:** Ensure meta tags, descriptions, and sitemap entries reflect the new pages to drive organic discovery for regional geography enthusiasts.
