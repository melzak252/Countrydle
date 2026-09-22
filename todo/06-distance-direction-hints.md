# Implementation Plan: Progressive Distance & Direction Hints for Guesses

**Target File:** `todo/06-distance-direction-hints.md`  
**Feature:** Progressive Distance (km) & Direction Hints on Incorrect Guesses  
**Status:** Ready for Implementation  
**Affected Subsystems:** Backend (`server/utils/`, `server/schemas/`, `server/{mode}/__init__.py`), Database (`data/*.sqlite`, Alembic), Frontend (`client/src/types/`, `client/src/stores/`, `client/src/components/`, `client/src/pages/`, `client/src/i18n.ts`).

---

## 1. Executive Summary & Game Design Specifications

### 1.1 The Player Request & Mechanics
In Countrydle and its regional variations (US States, Województwa, Powiaty), players currently have a limited number of guesses (3 for countries, states, and powiaty; 2 for województwa). When an incorrect guess is made, players currently receive only a binary red `❌` icon without spatial or geographic feedback.

This feature introduces **Progressive Spatial Feedback**:
1. **Guess 1 (if incorrect):** The server calculates and returns the great-circle **Distance** in kilometers (e.g. `2,150 km`) between the guessed entity's geographical centroid and the daily secret target's centroid. The client renders an elegant distance badge pill.
2. **Guess 2 (if incorrect):** The server calculates and returns both the **Distance** AND the **Direction / Initial Bearing** (compass direction code e.g. `"NE"`, exact bearing in degrees e.g. `45°`, and direction arrow e.g. `"↗"`). The client renders an interactive distance & bearing pill with rotated compass arrows.
3. **Guess 3:** The final attempt. If correct, the player wins (`is_game_over=True`, `won=True`). If incorrect, the game is over and the answer is revealed.

### 1.2 Mode-Specific Guess Limits (3 Guesses vs 2 Guesses)
The game modes have differing guess allowances:
- **3-Guess Modes (`countrydle`, `us_statedle`, `powiatdle`):**
  - Guess 1: Distance only (`distance_km`)
  - Guess 2: Distance + Bearing (`distance_km`, `bearing_degrees`, `bearing_direction`)
  - Guess 3: Final attempt (Win or Reveal)
- **2-Guess Mode (`wojewodztwodle`):**
  - In `wojewodztwodle`, the maximum number of guesses is 2 (`max_guesses = 2`).
  - To provide meaningful gameplay in a 2-guess mode, **Guess 1 returns BOTH Distance and Direction** immediately, because Guess 2 is already the final attempt!

### 1.3 Anti-Cheat & Information Security Invariants
- **Zero Coordinate Leakage:** The geographical coordinates $(\text{latitude}, \text{longitude})$ of the target entity MUST NEVER be transmitted to the client before the game is over. 
- **Server-Side Computation:** The Haversine distance and bearing azimuth calculations MUST take place strictly on the server in the `POST /{mode}/guess` handler.
- The client only receives the final computed scalar values (`distance_km`, `bearing_degrees`, `bearing_direction`) for the specific entity guessed.

---

## 2. Mathematical Formulas & Precision Specifications

### 2.1 Great-Circle Distance (Haversine Formula)
Let:
- $\varphi_1, \lambda_1$: Latitude and longitude of Guessed Entity Centroid (in radians)
- $\varphi_2, \lambda_2$: Latitude and longitude of Target Entity Centroid (in radians)
- $R = 6371.0\text{ km}$: Volumetric mean radius of the Earth

$$\Delta \varphi = \varphi_2 - \varphi_1$$
$$\Delta \lambda = \lambda_2 - \lambda_1$$
$$a = \sin^2\left(\frac{\Delta \varphi}{2}\right) + \cos(\varphi_1) \cdot \cos(\varphi_2) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1 - a}\right)$$
$$d = R \cdot c$$

#### Precision & Rounding Rules:
- Distances $\ge 100\text{ km}$: Rounded to the nearest integer $\text{km}$ (e.g. $1448.5 \to 1449\text{ km}$ or $2150\text{ km}$).
- Distances $< 100\text{ km}$: Exact integer $\text{km}$, with a minimum threshold of $1\text{ km}$ when non-identical (e.g. neighboring counties at $18.4\text{ km} \to 18\text{ km}$).
- Correct Guess: Distance is $0\text{ km}$, bearings are `None`.

### 2.2 Forward Azimuth / Initial Bearing
The initial bearing (great-circle forward azimuth) along the orthodrome from Point 1 (Guess) to Point 2 (Target):

$$y = \sin(\Delta \lambda) \cdot \cos(\varphi_2)$$
$$x = \cos(\varphi_1) \cdot \sin(\varphi_2) - \sin(\varphi_1) \cdot \cos(\varphi_2) \cdot \cos(\Delta \lambda)$$
$$\theta_0 = \text{atan2}(y, x)$$
$$\text{Bearing}_{\text{degrees}} = \left(\text{degrees}(\theta_0) + 360.0\right) \pmod{360.0}$$

Rounded to nearest integer degree: `bearing_degrees = round(Bearing_degrees) % 360`.

### 2.3 16-Point & 8-Point Compass Mapping Table

Sector width for 16-point compass: $\Delta\theta = \frac{360^\circ}{16} = 22.5^\circ$, centered on each heading ($\pm 11.25^\circ$).

$$\text{Index} = \left\lfloor \frac{(\theta + 11.25) \pmod{360}}{22.5} \right\rfloor$$

| Index | Code (EN) | Direction Name (EN) | Code (PL) | Direction Name (PL) | Range (Degrees) | Unicode Arrow |
|:---:|:---:|:---|:---:|:---|:---:|:---:|
| 0 | **N** | North | **Pn** | Północ | $348.75^\circ - 11.25^\circ$ | ↑ |
| 1 | **NNE** | North-Northeast | **PnPn-Wsch** | Północny-północny wschód | $11.25^\circ - 33.75^\circ$ | ↗ |
| 2 | **NE** | Northeast | **Pn-Wsch** | Północny wschód | $33.75^\circ - 56.25^\circ$ | ↗ |
| 3 | **ENE** | East-Northeast | **Wsch-Pn-Wsch** | Wschodni-północny wschód | $56.25^\circ - 78.75^\circ$ | ↗ |
| 4 | **E** | East | **Wsch** | Wschód | $78.75^\circ - 101.25^\circ$ | → |
| 5 | **ESE** | East-Southeast | **Wsch-Pd-Wsch** | Wschodni-południowy wschód | $101.25^\circ - 123.75^\circ$ | ↘ |
| 6 | **SE** | Southeast | **Pd-Wsch** | Południowy wschód | $123.75^\circ - 146.25^\circ$ | ↘ |
| 7 | **SSE** | South-Southeast | **PdPd-Wsch** | Południowy-południowy wschód | $146.25^\circ - 168.75^\circ$ | ↘ |
| 8 | **S** | South | **Pd** | Południe | $168.75^\circ - 191.25^\circ$ | ↓ |
| 9 | **SSW** | South-Southwest | **PdPd-Zach** | Południowy-południowy zachód | $191.25^\circ - 213.75^\circ$ | ↙ |
| 10 | **SW** | Southwest | **Pd-Zach** | Południowy zachód | $213.75^\circ - 236.25^\circ$ | ↙ |
| 11 | **WSW** | West-Southwest | **Zach-Pd-Zach** | Zachodni-południowy zachód | $236.25^\circ - 258.75^\circ$ | ↙ |
| 12 | **W** | West | **Zach** | Zachód | $258.75^\circ - 281.25^\circ$ | ← |
| 13 | **WNW** | West-Northwest | **Zach-Pn-Zach** | Zachodni-północny zachód | $281.25^\circ - 303.75^\circ$ | ↖ |
| 14 | **NW** | Northwest | **Pn-Zach** | Północny zachód | $303.75^\circ - 326.25^\circ$ | ↖ |
| 15 | **NNW** | North-Northwest | **PnPn-Zach** | Północny-północny zachód | $326.25^\circ - 348.75^\circ$ | ↖ |

### 2.4 Test Verification Vectors (Known Reference Points)
Unit tests will assert exact values against these geodetic benchmark pairs:
1. **Warsaw $\to$ London:**
   - Warsaw: $(52.2297^\circ\text{ N}, 21.0122^\circ\text{ E})$, London: $(51.5074^\circ\text{ N}, -0.1278^\circ\text{ W})$
   - Expected Distance: $1448.5\text{ km} \to 1449\text{ km}$
   - Expected Bearing: $275.2^\circ \to 275^\circ$ (Sector: `W`, Arrow: `←`)
2. **New York $\to$ Tokyo:**
   - NYC: $(40.7128^\circ\text{ N}, -74.0060^\circ\text{ W})$, Tokyo: $(35.6762^\circ\text{ N}, 139.6503^\circ\text{ E})$
   - Expected Distance: $10851.7\text{ km} \to 10852\text{ km}$
   - Expected Bearing: $333.0^\circ \to 333^\circ$ (Sector: `NNW`, Arrow: `↖`)
3. **Paris $\to$ Berlin:**
   - Paris: $(48.8566^\circ\text{ N}, 2.3522^\circ\text{ E})$, Berlin: $(52.5200^\circ\text{ N}, 13.4050^\circ\text{ E})$
   - Expected Distance: $878.0\text{ km} \to 878\text{ km}$
   - Expected Bearing: $54.2^\circ \to 54^\circ$ (Sector: `NE`, Arrow: `↗`)
4. **Sydney $\to$ Los Angeles:**
   - Sydney: $(-33.8688^\circ\text{ S}, 151.2093^\circ\text{ E})$, LA: $(34.0522^\circ\text{ N}, -118.2437^\circ\text{ W})$
   - Expected Distance: $12073.0\text{ km} \to 12073\text{ km}$
   - Expected Bearing: $56.0^\circ \to 56^\circ$ (Sector: `ENE`, Arrow: `↗`)

---

## 3. Database Audit & Data Enrichment Specifications

### 3.1 SQLite Database Audit Results
An inspection of the SQLite database tables in `data/` reveals:
| Database | Table | Total Rows | Latitude Present? | Longitude Present? | Notes |
|:---|:---|:---:|:---:|:---:|:---|
| `data/country_facts.sqlite` | `countries` | 195 | Yes (195/195) | Yes (195/195) | Complete REST Countries centroid coords |
| `data/us_state_facts.sqlite` | `us_states` | 50 | Yes (50/50) | Yes (50/50) | Complete geographic midpoints |
| `data/voivodeship_facts.sqlite` | `voivodeships` | 16 | Yes (16/16) | Yes (16/16) | Complete Voivodeship centroids |
| `data/powiat_facts.sqlite` | `powiats` | 380 | **NO (Missing)** | **NO (Missing)** | Columns do not exist currently |

### 3.2 Powiat Coordinates Enrichment Plan
- `client/public/powiaty-min.geojson` contains GeoJSON features for all 380 Polish powiats, with a 100% 380/380 name match to `data/powiaty.csv`.
- **Database Update Migration:**
  Create a migration script `server/scripts/enrich_powiat_coordinates.py`:
  1. Parse `client/public/powiaty-min.geojson`.
  2. For each feature, compute polygon centroid:
     $$\bar{\varphi} = \frac{1}{N}\sum_{i=1}^N \varphi_i, \quad \bar{\lambda} = \frac{1}{N}\sum_{i=1}^N \lambda_i$$
  3. Execute on `data/powiat_facts.sqlite`:
     ```sql
     ALTER TABLE powiats ADD COLUMN latitude REAL;
     ALTER TABLE powiats ADD COLUMN longitude REAL;
     ```
  4. Update each of the 380 records with its computed centroid.
  5. Update `server/scripts/build_powiat_facts_sqlite.py` to include `latitude` and `longitude` in future rebuilds.
- **Fail-Safe In-Memory Fallback:**
  In `server/utils/geo.py`, maintain an automatic fallback reader that computes and caches centroids directly from `powiaty-min.geojson` if the SQLite table columns are unpopulated.

---

## 4. Backend Architecture & API Specifications

### 4.1 Geo Utility Service (`server/utils/geo.py`)
Create a central geographic service with in-memory centroid caching to ensure $O(1)$ lookups with zero database overhead:

```python
# server/utils/geo.py
from __future__ import annotations
import math
import sqlite3
from pathlib import Path
from typing import NamedTuple

class GeoCentroid(NamedTuple):
    lat: float
    lon: float

class ProximityHint(NamedTuple):
    distance_km: int | None
    bearing_degrees: int | None
    bearing_direction: str | None

# In-memory centroid caches keyed by (mode, id) and (mode, normalized_name)
_CENTROIDS_BY_ID: dict[tuple[str, int], GeoCentroid] = {}
_CENTROIDS_BY_NAME: dict[tuple[str, str], GeoCentroid] = {}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360.0) % 360.0

def bearing_to_direction(degrees: float) -> str:
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    idx = int((degrees + 11.25) % 360 / 22.5)
    return directions[idx]

def load_all_centroids():
    """Preload all 641 centroids across the 4 modes on startup."""
    ...

def calculate_proximity_hint(
    mode: str,
    guessed_id: int | None,
    guessed_name: str | None,
    target_id: int,
    guess_count: int,
    is_correct: bool,
    max_guesses: int = 3,
) -> ProximityHint:
    if is_correct:
        return ProximityHint(distance_km=0, bearing_degrees=None, bearing_direction=None)

    target_centroid = get_centroid(mode, entity_id=target_id)
    guessed_centroid = get_centroid(mode, entity_id=guessed_id, name=guessed_name)

    if not target_centroid or not guessed_centroid:
        return ProximityHint(distance_km=None, bearing_degrees=None, bearing_direction=None)

    dist = round(haversine_distance(
        guessed_centroid.lat, guessed_centroid.lon,
        target_centroid.lat, target_centroid.lon
    ))
    dist = max(1, dist) if dist < 10 else dist

    bearing = round(calculate_bearing(
        guessed_centroid.lat, guessed_centroid.lon,
        target_centroid.lat, target_centroid.lon
    )) % 360
    direction = bearing_to_direction(bearing)

    # Progressive Hint Rules:
    if max_guesses == 2:
        # Wojewodztwodle: Guess 1 provides both distance + direction
        if guess_count == 1:
            return ProximityHint(distance_km=dist, bearing_degrees=bearing, bearing_direction=direction)
    else:
        # 3-Guess modes:
        if guess_count == 1:
            # Guess 1: Distance only
            return ProximityHint(distance_km=dist, bearing_degrees=None, bearing_direction=None)
        elif guess_count == 2:
            # Guess 2: Distance + Direction
            return ProximityHint(distance_km=dist, bearing_degrees=bearing, bearing_direction=direction)

    return ProximityHint(distance_km=None, bearing_degrees=None, bearing_direction=None)
```

### 4.2 Schema Enhancements (`server/schemas/*.py`)
Update the Guess response models across all four modes:
1. `server/schemas/countrydle.py`: `GuessDisplay`
2. `server/schemas/us_statedle.py`: `USStateGuessDisplay`
3. `server/schemas/wojewodztwodle.py`: `WojewodztwoGuessDisplay`
4. `server/schemas/powiatdle.py`: `PowiatGuessDisplay`

```python
class GuessDisplay(GuessBase):
    id: int
    answer: bool | None
    guessed_at: datetime
    distance_km: int | None = None
    bearing_degrees: int | None = None
    bearing_direction: str | None = None
```

### 4.3 Endpoint Implementation in `POST /{mode}/guess`
In `server/countrydle/__init__.py`, `server/us_statedle/__init__.py`, `server/wojewodztwodle/__init__.py`, `server/powiatdle/__init__.py`:

```python
# 1. Determine guess attempt index (1, 2, or 3)
current_guess_count = (guest_state["guesses_count"] + 1) if user is None else (state.guesses_made + 1)

# 2. Compute hints
hint = calculate_proximity_hint(
    mode="countrydle",
    guessed_id=guess.country_id,
    guessed_name=guess.guess,
    target_id=daily_country.country_id,
    guess_count=current_guess_count,
    is_correct=is_correct,
    max_guesses=COUNTRYDLE_CONFIG.max_guesses,
)

# 3. Attach hint to response model
# Both Guest user and Authenticated user receive identical hint data
```

### 4.4 Guess State Hydration in `GET /{mode}/state`
When a user refreshes or returns to the game, `get_state()` retrieves previous guesses.
- If stored in DB columns (`distance_km`, `bearing_degrees`, `bearing_direction`), serialize directly.
- If previously stored rows have `NULL` (legacy guesses), dynamically recalculate the hints for past guesses in the array so guess #1 displays its distance and guess #2 displays distance + direction.

### 4.5 Database Model & Migration (Alembic)
Create migration `add_distance_and_bearing_to_guesses.py`:
Add columns to `countrydle_guesses`, `us_statedle_guesses`, `wojewodztwodle_guesses`, `powiatdle_guesses`:
- `distance_km`: `Integer`, `nullable=True`
- `bearing_degrees`: `Integer`, `nullable=True`
- `bearing_direction`: `String(8)`, `nullable=True`

---

## 5. Client Architecture & State Persistence

### 5.1 Type Definitions (`client/src/types/index.ts`)
Update `Guess` interface:
```typescript
export interface Guess {
  id: number;
  guess: string;
  country_id?: number;
  us_state_id?: number;
  wojewodztwo_id?: number;
  powiat_id?: number;
  answer?: boolean;
  guessed_at: string;
  distance_km?: number | null;
  bearing_degrees?: number | null;
  bearing_direction?: string | null;
}
```

### 5.2 Store Persistence (`client/src/stores/gameStore.ts`)
- The client `gameStore.ts` stores guest progress in localStorage under `guess_game_{gameType}_{date}` as a `GuestSnapshot`.
- In `makeGuess`:
  `const guess = await service.makeGuess(...)`
  `const newGuesses = [...guesses, guessWithElapsed];`
- Because `guess` now includes `distance_km`, `bearing_degrees`, and `bearing_direction`, the snapshot automatically stores these fields in localStorage without breaking the existing validation schema in `readGuestSnapshot`.
- When the guest user later logs in and triggers `syncGuestData`, the server updates DB records while preserving the hint metadata.

---

## 6. Client UI / UX Design & Styling Specifications

### 6.1 Reusable `GuessBadge` Component (`client/src/components/GuessBadge.tsx`)
Create a dedicated component to render guess rows across all four game pages:

```tsx
// client/src/components/GuessBadge.tsx
import { ArrowUp, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { Guess } from '../types';

interface GuessBadgeProps {
  guess: Guess;
  gameType?: 'country' | 'us_states' | 'wojewodztwa' | 'powiaty';
}

export default function GuessBadge({ guess, gameType = 'country' }: GuessBadgeProps) {
  const { t, i18n } = useTranslation();

  if (guess.answer) {
    return (
      <li className="flex items-center justify-between border-l-2 border-emerald-500 bg-obsidian-950 px-3 py-2.5">
        <div className="flex items-center gap-3">
          <Check size={16} className="shrink-0 text-emerald-400" aria-hidden="true" />
          <span className="break-words text-sm font-medium text-sand-100">{guess.guess}</span>
        </div>
        <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
          {t('gamePage.solved', 'Solved')}
        </span>
      </li>
    );
  }

  const distanceFormatted = guess.distance_km != null
    ? `${guess.distance_km.toLocaleString(i18n.language === 'pl' ? 'pl-PL' : 'en-US')} km`
    : null;

  const colorClass = getProximityColor(guess.distance_km, gameType);

  return (
    <li className="flex items-center justify-between border-l-2 border-rose-500/60 bg-obsidian-950 px-3 py-2.5">
      <div className="flex items-center gap-3 min-w-0 pr-2">
        <X size={16} className="shrink-0 text-rose-400" aria-hidden="true" />
        <span className="truncate text-sm text-zinc-300">{guess.guess}</span>
      </div>

      {distanceFormatted && (
        <div 
          className={`flex shrink-0 items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium border ${colorClass}`}
          aria-label={`Distance: ${distanceFormatted}${guess.bearing_direction ? `, Direction: ${guess.bearing_direction}` : ''}`}
        >
          {guess.bearing_degrees != null && (
            <span
              className="inline-flex items-center justify-center transition-transform duration-500"
              style={{ transform: `rotate(${guess.bearing_degrees}deg)` }}
              title={`${guess.bearing_degrees}°`}
            >
              <ArrowUp size={13} strokeWidth={2.5} className="shrink-0" />
            </span>
          )}
          <span>{distanceFormatted}</span>
          {guess.bearing_direction && (
            <>
              <span className="opacity-40">·</span>
              <span className="font-semibold uppercase tracking-wider">{t(`directions.${guess.bearing_direction}`, guess.bearing_direction)}</span>
            </>
          )}
        </div>
      )}
    </li>
  );
}
```

### 6.2 Adaptive Proximity Color Scales
Because the geographical extents vary dramatically between world countries ($20,000\text{ km}$ max) and Polish counties ($650\text{ km}$ max across Poland, often $30-50\text{ km}$ between neighbors), the color thresholds adapt by mode:

| Game Mode | Max Extent | Ice / Cool Gray | Cold Amber | Warm Orange | Hot Emerald/Gold |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Countrydle** | $20,000\text{ km}$ | $> 5,000\text{ km}$ | $2,000 - 5,000\text{ km}$ | $500 - 2,000\text{ km}$ | $< 500\text{ km}$ |
| **US States** | $5,000\text{ km}$ | $> 2,000\text{ km}$ | $1,000 - 2,000\text{ km}$ | $300 - 1,000\text{ km}$ | $< 300\text{ km}$ |
| **Województwa** | $650\text{ km}$ | $> 350\text{ km}$ | $200 - 350\text{ km}$ | $100 - 200\text{ km}$ | $< 100\text{ km}$ |
| **Powiaty** | $650\text{ km}$ | $> 250\text{ km}$ | $120 - 250\text{ km}$ | $50 - 120\text{ km}$ | $< 50\text{ km}$ |

#### Tailwind CSS Proximity Color Palette:
- **Ice / Cool Gray:** `border-zinc-700/50 bg-zinc-800/40 text-zinc-400`
- **Cold Amber:** `border-amber-500/25 bg-amber-500/10 text-amber-300`
- **Warm Orange:** `border-orange-500/30 bg-orange-500/10 text-orange-300`
- **Hot Emerald/Gold:** `border-emerald-500/30 bg-emerald-500/15 text-emerald-300 font-semibold`

---

## 7. Localization Specifications (English & Polish)

Update `client/src/i18n.ts`:

```typescript
// English
directions: {
  N: 'N',
  NNE: 'NNE',
  NE: 'NE',
  ENE: 'ENE',
  E: 'E',
  ESE: 'ESE',
  SE: 'SE',
  SSE: 'SSE',
  S: 'S',
  SSW: 'SSW',
  SW: 'SW',
  WSW: 'WSW',
  W: 'W',
  WNW: 'WNW',
  NW: 'NW',
  NNW: 'NNW',
},
hints: {
  distanceOnly: '{{distance}} km',
  distanceAndDirection: '{{distance}} km · {{arrow}} {{direction}}',
}

// Polish
directions: {
  N: 'Pn',
  NNE: 'PnPn-Wsch',
  NE: 'Pn-Wsch',
  ENE: 'Wsch-Pn-Wsch',
  E: 'Wsch',
  ESE: 'Wsch-Pd-Wsch',
  SE: 'Pd-Wsch',
  SSE: 'PdPd-Wsch',
  S: 'Pd',
  SSW: 'PdPd-Zach',
  SW: 'Pd-Zach',
  WSW: 'Zach-Pd-Zach',
  W: 'Zach',
  WNW: 'Zach-Pn-Zach',
  NW: 'Pn-Zach',
  NNW: 'PnPn-Zach',
},
hints: {
  distanceOnly: '{{distance}} km',
  distanceAndDirection: '{{distance}} km · {{arrow}} {{direction}}',
}
```

---

## 8. Share Card & Social Integration

In `client/src/components/ShareResultCard.tsx`, provide optional proximity progression in the shareable clipboard text while strictly maintaining the **spoiler-free invariant** (names of guessed and target entities are never leaked):

```text
Countrydle 2026-09-22 🌍
🏆 Score: 2,150 pts
❓ Questions: 4/10
🎯 Guesses: 3/3 (Solved!)
1️⃣ 🟧 2,150 km
2️⃣ 🟨 680 km ↗
3️⃣ 🟩 Solved!
🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜

Can you beat my deduction score?
https://countrydle.online
```

Where:
- ⬛ / ⬜: Cool Gray ($> 5,000\text{ km}$)
- 🟨: Amber ($2,000 - 5,000\text{ km}$)
- 🟧: Orange ($500 - 2,000\text{ km}$)
- 🟫 / 🟨 / 🟩: Hot / Solved

---

## 9. Testing & Verification Strategy

### 9.1 Unit Tests (`server/tests/test_geo_hints.py`)
- **Haversine Accuracy:** Test against Warsaw-London, NYC-Tokyo, Paris-Berlin, Sydney-LA reference coordinates ($\pm 1\text{ km}$ tolerance).
- **Bearing Azimuth & Sector Boundaries:** Test cardinal crossings: $0^\circ$ (N), $45^\circ$ (NE), $90^\circ$ (E), $180^\circ$ (S), $270^\circ$ (W), $359.5^\circ$ (N). Test edge bounds at $11.24^\circ$ vs $11.26^\circ$.
- **Hint Engine Progression:**
  - Call `calculate_proximity_hint` with `guess_count=1` $\implies$ returns `distance_km` only (`bearing_degrees=None`, `bearing_direction=None`).
  - Call with `guess_count=2` $\implies$ returns `distance_km` AND `bearing_degrees` AND `bearing_direction`.
  - Call with `is_correct=True` $\implies$ returns `distance_km=0`.
  - Call with unknown entity $\implies$ returns `None` gracefully without crashing.
  - Call for `wojewodztwodle` (`max_guesses=2`) with `guess_count=1` $\implies$ returns both distance and direction.

### 9.2 Route Integration Tests (`server/tests/test_guess_proximity.py`)
- Test `POST /countrydle/guess`:
  - 1st incorrect guess: verifies JSON response contains integer `distance_km` and `null` for `bearing_degrees` and `bearing_direction`.
  - 2nd incorrect guess: verifies JSON response contains both integer `distance_km` and valid integer `bearing_degrees` (0-359) and string `bearing_direction`.
  - Check guest session cookie flow and authenticated user flow behave identically.
- Test `POST /wojewodztwodle/guess`:
  - 1st incorrect guess: verifies JSON returns both distance and direction.

### 9.3 Client Component Tests (`client/tests/GuessBadge.test.tsx`)
- Verify rendering of distance only when `bearing_degrees` is undefined/null.
- Verify rendering of rotated arrow and direction badge when `bearing_degrees` and `bearing_direction` are provided.
- Verify correct CSS color class applied based on distance and game mode.

---

## 10. Step-by-Step Execution Plan & Verification Checklist

### Phase 1: Data Preparation & Centroid Enrichment
- [ ] Create `server/scripts/enrich_powiat_coordinates.py` to calculate polygon centroids from `client/public/powiaty-min.geojson`.
- [ ] Run script to add `latitude` and `longitude` to `data/powiat_facts.sqlite` `powiats` table.
- [ ] Verify non-null coordinate count: `SELECT count(latitude), count(longitude) FROM powiats` returns 380/380.

### Phase 2: Core Geo Utility Service
- [ ] Create `server/utils/geo.py` with Haversine formula, initial bearing azimuth, 16-point compass mapping, and in-memory centroid caching.
- [ ] Add `load_all_centroids()` hook in `server/app.py` startup event.
- [ ] Write unit tests in `server/tests/test_geo_hints.py` and verify passing.

### Phase 3: Schemas & Database Migration
- [ ] Update `GuessDisplay` schemas in `server/schemas/countrydle.py`, `us_statedle.py`, `wojewodztwodle.py`, `powiatdle.py`.
- [ ] Create Alembic migration `add_distance_and_bearing_to_guesses` for the four guess tables.
- [ ] Update repository models in `server/db/models/guess.py`, `us_statedle.py`, `wojewodztwodle.py`, `powiatdle.py`.

### Phase 4: API Handlers Update
- [ ] Update `make_guess` in `server/countrydle/__init__.py`.
- [ ] Update `make_guess` in `server/us_statedle/__init__.py`.
- [ ] Update `make_guess` in `server/wojewodztwodle/__init__.py`.
- [ ] Update `make_guess` in `server/powiatdle/__init__.py`.
- [ ] Update `get_state` in all four routers to hydrate past guess hints on refresh.

### Phase 5: Client Types, Store & UI
- [ ] Update `Guess` interface in `client/src/types/index.ts`.
- [ ] Create `client/src/components/GuessBadge.tsx`.
- [ ] Replace inline guess item rendering in `GamePage.tsx`, `USStatesGamePage.tsx`, `WojewodztwaGamePage.tsx`, `PowiatyGamePage.tsx` with `<GuessBadge>`.
- [ ] Add direction translations and number formatting to `client/src/i18n.ts`.
- [ ] Update `ShareResultCard.tsx` to include optional guess proximity progress.

### Phase 6: Final Verification & Smoke Testing
- [ ] Run backend test suite: `pytest server/tests/test_geo_hints.py server/tests/test_guess_proximity.py`.
- [ ] Run frontend test suite: `npm test` in `client/`.
- [ ] Verify zero regressions in game logic, guest state synchronization, and score calculation.
