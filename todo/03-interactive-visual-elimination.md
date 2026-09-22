# Interactive Visual Elimination & Dual-State Map Marking — Architecture & Implementation Plan

**Target File:** `todo/03-interactive-visual-elimination.md`  
**Status:** Ready for Implementation  
**Affected Modules:**
- Client Store: `client/src/stores/gameStore.ts`
- Client Map Components: `client/src/components/MapBox.tsx`, `client/src/components/USStatesMap.tsx`, `client/src/components/WojewodztwaMap.tsx`, `client/src/components/PowiatyMap.tsx`
- Clue History Component: `client/src/components/History.tsx`
- Types & Models: `client/src/types/index.ts`, `server/schemas/countrydle.py`
- Server Answering Engine (Optional metadata): `server/countrydle/local_answering.py`, `server/countrydle/local_planner.py`

---

## 1. Executive Summary & Problem Analysis

### 1.1 The User Cognitive Conflict
In Countrydle and its sister modes (Powiatdle, Wojewodztwodle, USStatedle), the interactive map is the primary deduction workspace. Players consult the map to evaluate hypotheses, count geographic neighbors, track latitudinal/longitudinal bounds, and narrow down possibilities.

Currently, clicking an entity on the map executes:
```typescript
toggleEntitySelection(countryName.toUpperCase());
```
Which pushes/removes the name from a single flat array `selectedEntityNames: string[]` and renders the entity with a red fill `#cc2222` (or emerald outline depending on component variant).

This single-state boolean toggle triggers a fundamental clash between two equal cohorts of players:
- **Cohort A (Inclusionary Deduction):** Uses map highlights to bookmark **"Strong Candidates / Suspects"** (e.g. "It's in the Balkans with a population < 10M, so I mark Serbia, Croatia, Bosnia, Montenegro"). For them, highlighted = **Alive / Potential Answer**.
- **Cohort B (Exclusionary Deduction):** Uses map markings to **"Eliminate / Rule Out"** countries based on answered clues (e.g. "Question: 'Is it landlocked? -> NO' — I want to cross off Hungary, Austria, Switzerland, Czechia"). For them, marked = **Dead / Impossible**.

Because only one color/state exists, neither cohort can play naturally. When Cohort A and Cohort B play together or stream the game, the UI is completely ambiguous: a colored country might mean "definitely possible" or "definitely impossible". Furthermore, neither cohort can combine both techniques (e.g. eliminating 80% of a continent while starring 3 prime suspects).

### 1.2 Performance & Technical Bottlenecks in Current Maps
1. **Full Layer Traversal on Click:** When `selectedEntityNames` updates, `useEffect` iterates over every layer in `geoJsonLayerRef.current.eachLayer(...)`. For Countrydle (195 features) and US States (51 features), this takes 2–4ms. But for **Powiaty (380 detailed polygon boundaries)**, re-styling all 380 SVG path layers on every tap causes noticeable frame-drops (40–80ms) and jank on mobile web browsers.
2. **Missing Touch Interaction Nuance:** On touch devices, panning the map frequently triggers accidental feature clicks because `click` fires after a touch release even if a minor drag occurred.
3. **No Right-Click Shortcut:** On desktop, players expect right-click to perform an alternative action (e.g., secondary mark or quick erase), but currently right-click simply triggers the native browser context menu.
4. **Colorblind Inaccessibility:** The current color scheme uses `#cc2222` (red) for selected and `#22cc22` (green) for correct answers. For players with Protanopia or Deuteranopia (red-green color vision deficiency affecting ~8% of males), these two states share near-identical perceived luminance and hue without texture or shape differentiation.

---

## 2. Core Interaction Model & UX Architecture

### 2.1 Four-State Entity Lifecycle
Every map entity (country, state, voivodeship, powiat) exists in one of four mutually exclusive visual states:

```
                  ┌───────────────┐
                  │ 0. NEUTRAL    │ (Default: dark base, semi-transparent)
                  └───┬───────▲───┘
      Click/Select    │       │ Clear/Cycle
      or Pen Mode     ▼       │
      ┌──────────────────┐   │
      │ 1. CANDIDATE     │───┘
      │ (Emerald glow)   │
      └───┬──────────────┘
          │
          │ Cycle or Right-Click / Eliminator Mode
          ▼
      ┌──────────────────┐
      │ 2. ELIMINATED    │───► (Can return to Neutral via click or eraser)
      │ (Dimmed / Hatch) │
      └──────────────────┘

      [Special State on Game Over]
      ┌──────────────────┐
      │ 3. REVEALED      │ (Correct entity: Gold/Vivid Emerald, locked against toggles)
      └──────────────────┘
```

| State | Fill Color | Fill Opacity | Border / Stroke | Accessibility Texture / Pattern | Semantic Meaning |
|---|---|---|---|---|---|
| **0. Neutral** | `#242424` (zinc-800) | `0.70` | `1px solid #52525b` (zinc-600) | None (plain base map) | Unevaluated territory |
| **1. Candidate** | `#10b981` (emerald-500) | `0.75` | `2px solid #34d399` (emerald-400) + glow | Subtle dot-matrix pattern or bright solid glow | Primary suspect / Hypothesis |
| **2. Eliminated** | `#18181b` (zinc-900) | `0.20` (ghosted) | `1px dashed #71717a` (zinc-500) | 45° diagonal hatch pattern (`url(#diagonal-hatch)`) | Ruled out / Impossible |
| **3. Revealed** | `#22c55e` (green-500) | `0.90` | `3px solid #ffffff` + pulse | Checkmark badge at centroid | Correct answer (Game Over) |

### 2.2 Dual-Interaction Paradigms: Cycle vs Active Tool

To accommodate both casual mobile users and hardcore desktop deduction players, the system offers **two switchable interaction workflows** via a floating toolbar setting:

#### Workflow A: The 3-State Cycle (Default for Mobile & Fast Tapping)
Tapping or clicking an entity cycles forward:
`Neutral ➔ Candidate ➔ Eliminated ➔ Neutral`
- Quick, zero-toolbar interaction.
- Single tap on a country makes it green (Candidate).
- Second tap turns it dimmed/cross-hatched (Eliminated).
- Third tap clears it back to Neutral.

#### Workflow B: The Dual-Tool Switcher (Default for Desktop & Power Users)
A floating toolbar above the map provides explicit active tool modes:
- 🟢 **Candidate Pen (Green Mode):** Direct click sets/unsets **Candidate** (`Neutral ⇄ Candidate`).
- 🔴 **Elimination Eraser (Red/Dim Mode):** Direct click sets/unsets **Eliminated** (`Neutral ⇄ Eliminated`).
- 🔄 **Cycle Mode:** Reverts to 3-state cycling.

#### Workflow C: Desktop Power Shortcuts
Regardless of the active tool mode, desktop keyboard/mouse shortcuts provide immediate 1-click access:
- **Left-Click:** Applies active tool (or cycles in cycle mode).
- **Right-Click (`contextmenu`):** Always toggles **Eliminated** state (`Neutral/Candidate ➔ Eliminated`, or `Eliminated ➔ Neutral`). Suppresses browser context menu via `e.preventDefault()`.
- **Shift + Left-Click:** Always toggles **Candidate** state.
- **Alt / Option + Left-Click:** Instantly resets the clicked entity to **Neutral**.

#### Workflow D: Mobile Touch Gestures
- **Short Tap (< 300ms, touch movement < 8px):** Executes primary action (cycle or active tool).
- **Long Press (Hold ≥ 350ms):** Toggles **Eliminated** state. Accompanied by subtle haptic vibration (`navigator.vibrate(25)` if supported) and visual scale pulse.
- **Two-Finger Pinch / Drag:** Leaflet native map pan and zoom. Long-press timer is immediately aborted if `touchmove` distance exceeds 8 pixels.

### 2.3 The Map Deduction Toolbar
Positioned at top-left or floating docked above the map canvas:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  [ 🟢 Mode: Candidate ] [ 🚫 Mode: Eliminate ] [ 🔄 Cycle ]                      │
│  ──────────────────────────────────────────────────────────────                  │
│  Candidates: 5  |  Eliminated: 124  |  Remaining: 66                             │
│  [ Clear Candidates ]  [ Clear Eliminated ]  [ Reset All ]  [ ⚙️ Colorblind Mode ]│
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Clue-Assisted Auto-Elimination (Smart Assistant)

### 3.1 Strict Principle of Deduction Agency
Countrydle is a game of intellectual skill and deductive reasoning. **Auto-elimination must NEVER be forced or applied automatically upon receiving an answer.** Automated background changes rob the player of the thrill of deduction.

Instead, the Clue Assistant acts as an **opt-in visual calculator**:
1. When a question is answered and verified, the question card in `History.tsx` detects if the clue has an unambiguous geographic or property-based scope.
2. An elegant, subtle action pill appears at the bottom of the clue card:
   - Example (Answer: NO): `[ 🚫 Apply to Map: Eliminate Europe (47) ]`
   - Example (Answer: YES): `[ 🟢 Apply to Map: Highlight South America (12) ]`
3. Clicking this action:
   - Updates `eliminatedEntities` or `candidateEntities` in the Zustand store.
   - Triggers an instant map re-style.
   - Shows a transient toast with an **Undo** button (`"Marked 47 European countries as eliminated. [Undo]"`).
4. The button transitions to a checked state: `[ ✓ Applied (47) · Click to Revert ]`.

### 3.2 Elimination Rule Derivation: Backend AST vs Client Mapping
There are two complementary layers to resolve which entities match a clue:

#### Layer 1: Client-Side Geometry & Metadata Engine (Instant & Offline)
For the most common question categories across all game modes, the client already holds or can load lightweight metadata lookup tables:
- **Countrydle:** Continent (`Europe`, `Asia`, `Africa`, `Americas`, `Oceania`), Hemisphere (`Northern`, `Southern`, `Eastern`, `Western`), Landlocked (`Yes`, `No`), Island Nation (`Yes`, `No`).
- **US States:** Region (`Northeast`, `Midwest`, `South`, `West`), Coastline (`Atlantic`, `Pacific`, `Gulf`, `Landlocked`), Original 13 Colonies.
- **Wojewodztwa:** Historical regions, access to sea, border countries.
- **Powiaty:** Parent Voivodeship (`wojewodztwo` code/name), City Counties (`miasto na prawach powiatu` vs `ziemski`).

#### Layer 2: Server AST Plan Hints (Local Knowledge Base)
The backend `local_planner.py` generates an execution AST for local KB questions (e.g. `{"operator": "==", "left": {"property": "continent"}, "right": {"value": "Europe"}}`).
When the question is processed, the server can optionally attach a precomputed `elimination_hint` object to the question response:

```json
{
  "id": 42,
  "original_question": "Is it in Europe?",
  "question": "Is the country located in Europe?",
  "valid": true,
  "answer": false,
  "explanation": "The target country is not located in Europe.",
  "elimination_hint": {
    "action": "eliminate",
    "target_count": 47,
    "label_en": "Eliminate Europe (47 countries)",
    "label_pl": "Wyklucz Europę (47 państw)",
    "entity_names": ["ALBANIA", "ANDORRA", "AUSTRIA", "BELARUS", "BELGIUM", ...]
  }
}
```

If `elimination_hint` is null (e.g. for complex semantic LLM answers not backed by a discrete local AST property), no auto-elimination button is displayed, leaving manual marking to the player.

---

## 4. Technical Architecture & Component Implementation

### 4.1 State Store Specification (`client/src/stores/gameStore.ts`)

We upgrade `GameData` and `GameActions` to replace the ambiguous `selectedEntityNames` with a robust dual-state model while retaining backward compatibility for any legacy callers.

```typescript
export type MapMarkingMode = 'cycle' | 'candidate' | 'eliminated';

export interface GameData {
  gameState: GameState | null;
  questions: Question[];
  guesses: Guess[];
  entities: any[];
  correctEntity: any | null;
  dailyDate: string | null;
  
  // Dual-State Map Markings
  candidateEntities: string[];    // Normalized uppercase names
  eliminatedEntities: string[];   // Normalized uppercase names
  markingMode: MapMarkingMode;    // Active tool
  isColorblindMode: boolean;      // High-contrast / hatch texture toggle
  
  // Backward compatibility alias (points to candidateEntities)
  selectedEntityNames: string[];
  
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  gameStartTime: number | null;
}

export interface GameActions {
  fetchGameState: () => Promise<void>;
  fetchEntities: () => Promise<void>;
  askQuestion: (questionText: string) => Promise<void>;
  makeGuess: (guessText: string, entityId?: number) => Promise<void>;
  syncGuestData: () => Promise<void>;
  resetGame: () => void;
  
  // New Map Marking Actions
  cycleEntityMark: (name: string) => void;
  setEntityMark: (name: string, state: 'neutral' | 'candidate' | 'eliminated') => void;
  toggleCandidate: (name: string) => void;
  toggleEliminated: (name: string) => void;
  batchMarkEntities: (names: string[], state: 'candidate' | 'eliminated', mode?: 'replace' | 'merge') => void;
  clearCandidates: () => void;
  clearEliminated: () => void;
  clearAllMarks: () => void;
  setMarkingMode: (mode: MapMarkingMode) => void;
  toggleColorblindMode: () => void;
  
  // Backward compatibility
  toggleEntitySelection: (name: string) => void;
  clearSelection: () => void;
}
```

#### State Transition Logic in Store Implementation:
```typescript
cycleEntityMark: (rawName: string) => {
  const name = rawName.toUpperCase();
  const { candidateEntities, eliminatedEntities } = get();
  
  if (candidateEntities.includes(name)) {
    // Candidate -> Eliminated
    set({
      candidateEntities: candidateEntities.filter(n => n !== name),
      eliminatedEntities: [...eliminatedEntities, name],
      selectedEntityNames: candidateEntities.filter(n => n !== name),
    });
  } else if (eliminatedEntities.includes(name)) {
    // Eliminated -> Neutral
    set({
      eliminatedEntities: eliminatedEntities.filter(n => n !== name),
    });
  } else {
    // Neutral -> Candidate
    const nextCandidates = [...candidateEntities, name];
    set({
      candidateEntities: nextCandidates,
      selectedEntityNames: nextCandidates,
    });
  }
  get().persistMarksToSnapshot();
},

setEntityMark: (rawName: string, targetState: 'neutral' | 'candidate' | 'eliminated') => {
  const name = rawName.toUpperCase();
  const { candidateEntities, eliminatedEntities } = get();
  
  const nextCandidates = candidateEntities.filter(n => n !== name);
  const nextEliminated = eliminatedEntities.filter(n => n !== name);
  
  if (targetState === 'candidate') {
    nextCandidates.push(name);
  } else if (targetState === 'eliminated') {
    nextEliminated.push(name);
  }
  
  set({
    candidateEntities: nextCandidates,
    eliminatedEntities: nextEliminated,
    selectedEntityNames: nextCandidates,
  });
  get().persistMarksToSnapshot();
},

batchMarkEntities: (rawNames: string[], targetState: 'candidate' | 'eliminated', mode = 'merge') => {
  const names = new Set(rawNames.map(n => n.toUpperCase()));
  const { candidateEntities, eliminatedEntities } = get();
  
  let nextCandidates = mode === 'replace' && targetState === 'candidate' ? [] : [...candidateEntities];
  let nextEliminated = mode === 'replace' && targetState === 'eliminated' ? [] : [...eliminatedEntities];
  
  if (targetState === 'candidate') {
    // Remove from eliminated, add to candidate
    nextEliminated = nextEliminated.filter(n => !names.has(n));
    names.forEach(n => {
      if (!nextCandidates.includes(n)) nextCandidates.push(n);
    });
  } else {
    // Remove from candidate, add to eliminated
    nextCandidates = nextCandidates.filter(n => !names.has(n));
    names.forEach(n => {
      if (!nextEliminated.includes(n)) nextEliminated.push(n);
    });
  }
  
  set({
    candidateEntities: nextCandidates,
    eliminatedEntities: nextEliminated,
    selectedEntityNames: nextCandidates,
  });
  get().persistMarksToSnapshot();
}
```

#### LocalStorage Snapshot Persistence:
The guest snapshot schema (`GuestSnapshot`) is updated to serialize `candidateEntities` and `eliminatedEntities` alongside `state`, `questions`, and `guesses`. When a player refreshes their browser mid-game, all their visual markings remain intact.

---

### 4.2 High-Performance Leaflet Rendering Engine

#### The Powiaty 380-Polygon Challenge:
In `PowiatyMap.tsx`, there are 380 features. In previous code:
```typescript
geoJsonLayerRef.current.eachLayer((layer: any) => { ... layer.setStyle(...) });
```
Executing this inside a `useEffect` triggered on every click means 380 style recalculations, DOM attribute writes, and repaint triggers.

#### The O(1) Imperative Layer Map Solution:
We introduce a feature registry ref in all map components (`layerIndexRef = useRef<Map<string, L.Path>>(new Map())`).

1. **On GeoJSON Initialization (`onEachFeature`):**
   ```typescript
   layerIndexRef.current.set(entityKey.toUpperCase(), layer as L.Path);
   ```
2. **On Single Click / Mark Change:**
   Instead of iterating 380 layers, update **only the clicked layer** directly:
   ```typescript
   const layer = layerIndexRef.current.get(name.toUpperCase());
   if (layer) {
     layer.setStyle(computeEntityStyle(name, state));
   }
   ```
3. **On Batch Elimination (e.g. 47 countries):**
   Iterate only the 47 affected keys via `layerIndexRef.current.get(name)`, bypassing the other 148 layers entirely.
4. **Canvas vs SVG Renderer:**
   Leaflet's default SVG renderer creates an individual SVG `<path>` node per feature. For Powiaty on low-end mobile devices, SVG DOM size is heavy. We configure `preferCanvas: true` or pass an explicit `L.canvas()` renderer to `<MapContainer>` or `<GeoJSON>`:
   ```typescript
   const canvasRenderer = useMemo(() => L.canvas({ padding: 0.5, tolerance: 10 }), []);
   ...
   <GeoJSON data={geoJsonData} renderer={canvasRenderer} ... />
   ```
   *Note on canvas rendering:* Canvas allows rendering thousands of vertices in a single HTML5 `<canvas>` element with zero DOM node overhead, dramatically accelerating zoom and pan framerates.

---

### 4.3 Color Palette & SVG Hatch Pattern (Colorblind Accessibility)

To ensure WCAG AAA compliance and support for color vision deficiency (Protanopia, Deuteranopia, Tritanopia, Monochromacy), we combine **color**, **luminance**, and **fill pattern**.

#### SVG Pattern Definition (Injected into Leaflet SVG Defs or Component CSS):
```html
<svg className="absolute w-0 h-0 pointer-events-none" aria-hidden="true">
  <defs>
    <!-- 45-degree diagonal stripes for Eliminated entities -->
    <pattern id="eliminated-hatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="0" y2="8" stroke="#ef4444" strokeWidth="2.5" strokeOpacity="0.4" />
      <rect width="8" height="8" fill="#18181b" fillOpacity="0.3" />
    </pattern>
    
    <!-- High-Contrast Colorblind Pattern -->
    <pattern id="cb-eliminated-cross" width="10" height="10" patternUnits="userSpaceOnUse">
      <path d="M 0 0 L 10 10 M 10 0 L 0 10" stroke="#71717a" strokeWidth="1.5" strokeOpacity="0.6" />
    </pattern>
  </defs>
</svg>
```

#### Style Resolution Function:
```typescript
interface StyleConfig {
  isCorrect: boolean;
  isCandidate: boolean;
  isEliminated: boolean;
  isColorblind: boolean;
}

export const getEntityPathStyle = (config: StyleConfig): L.PathOptions => {
  const { isCorrect, isCandidate, isEliminated, isColorblind } = config;

  // 1. Correct / Revealed (Game Over)
  if (isCorrect) {
    return {
      fillColor: isColorblind ? '#eab308' : '#22c55e', // Gold in CB mode, Emerald in standard
      fillOpacity: 0.85,
      weight: 2.5,
      color: '#ffffff',
      opacity: 1,
      dashArray: undefined,
    };
  }

  // 2. Candidate (Suspect)
  if (isCandidate) {
    return {
      fillColor: isColorblind ? '#06b6d4' : '#10b981', // Vivid Cyan in CB mode, Emerald in standard
      fillOpacity: 0.75,
      weight: 2,
      color: isColorblind ? '#22d3ee' : '#34d399',
      opacity: 1,
      dashArray: undefined,
    };
  }

  // 3. Eliminated (Ruled Out)
  if (isEliminated) {
    return {
      fillColor: isColorblind ? '#1c1917' : '#27272a',
      fillOpacity: 0.15, // Highly dimmed / ghosted
      weight: 1,
      color: isColorblind ? '#a1a1aa' : '#71717a',
      opacity: 0.6,
      dashArray: '4, 4', // Dashed border to visually signal exclusion
    };
  }

  // 4. Neutral (Default)
  return {
    fillColor: '#242424',
    fillOpacity: 0.65,
    weight: 1,
    color: '#3f3f46',
    opacity: 0.8,
    dashArray: undefined,
  };
};
```

---

### 4.4 Touch & Pointer Event Handling (Mobile vs Desktop)

To avoid drag-vs-click race conditions and support long-press on mobile:

```typescript
interface TouchHandlerState {
  touchTimer: NodeJS.Timeout | null;
  touchStartPos: { x: number; y: number } | null;
  didLongPress: boolean;
}

export function bindEntityPointerEvents(
  layer: L.Path,
  entityName: string,
  handlers: {
    onCycle: (name: string) => void;
    onToggleCandidate: (name: string) => void;
    onToggleEliminated: (name: string) => void;
    getActiveMode: () => MapMarkingMode;
  }
) {
  const touchState: TouchHandlerState = {
    touchTimer: null,
    touchStartPos: null,
    didLongPress: false,
  };

  // Prevent native browser right-click menu on map polygons
  layer.on('contextmenu', (e: L.LeafletMouseEvent) => {
    L.DomEvent.preventDefault(e.originalEvent);
    L.DomEvent.stopPropagation(e.originalEvent);
    handlers.onToggleEliminated(entityName);
  });

  // Desktop Left Click
  layer.on('click', (e: L.LeafletMouseEvent) => {
    L.DomEvent.stopPropagation(e.originalEvent);
    
    // Ignore synthetic click if long-press just fired
    if (touchState.didLongPress) {
      touchState.didLongPress = false;
      return;
    }

    const mouseEvent = e.originalEvent as MouseEvent;
    if (mouseEvent.shiftKey) {
      handlers.onToggleCandidate(entityName);
      return;
    }
    if (mouseEvent.altKey) {
      // Direct reset
      return;
    }

    const mode = handlers.getActiveMode();
    if (mode === 'candidate') {
      handlers.onToggleCandidate(entityName);
    } else if (mode === 'eliminated') {
      handlers.onToggleEliminated(entityName);
    } else {
      handlers.onCycle(entityName);
    }
  });

  // Mobile Touch Gestures
  const el = (layer as any)._path as SVGElement | undefined;
  if (el) {
    el.addEventListener('touchstart', (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      touchState.didLongPress = false;
      touchState.touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };

      touchState.touchTimer = setTimeout(() => {
        touchState.didLongPress = true;
        if (navigator.vibrate) navigator.vibrate(30); // Haptic feedback
        handlers.onToggleEliminated(entityName);
      }, 350); // 350ms long-press threshold
    }, { passive: true });

    el.addEventListener('touchmove', (e: TouchEvent) => {
      if (!touchState.touchStartPos) return;
      const dx = Math.abs(e.touches[0].clientX - touchState.touchStartPos.x);
      const dy = Math.abs(e.touches[0].clientY - touchState.touchStartPos.y);
      // Abort long press if finger moved > 8px (player is panning the map)
      if (dx > 8 || dy > 8) {
        if (touchState.touchTimer) clearTimeout(touchState.touchTimer);
        touchState.touchStartPos = null;
      }
    }, { passive: true });

    el.addEventListener('touchend', () => {
      if (touchState.touchTimer) clearTimeout(touchState.touchTimer);
      touchState.touchStartPos = null;
    });

    el.addEventListener('touchcancel', () => {
      if (touchState.touchTimer) clearTimeout(touchState.touchTimer);
      touchState.touchStartPos = null;
      touchState.didLongPress = false;
    });
  }
}
```

---

### 4.5 Clue-Assisted Auto-Elimination Component (`client/src/components/History.tsx`)

In `History.tsx`, we inspect each verified question. If an `elimination_hint` is attached (or derived from local metadata), we render an actionable deduction badge:

```tsx
// Inside History.tsx question item rendering:
{q.valid && q.answer !== null && q.elimination_hint && !isGameOver && (
  <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2.5">
    <span className="text-xs text-zinc-400">
      {t('clueAssistant.detectedDeduction', 'Deduction available:')}
    </span>
    <button
      onClick={() => handleApplyElimination(q.elimination_hint)}
      className="inline-flex items-center gap-1.5 rounded bg-zinc-800 px-2.5 py-1 text-xs font-medium text-sand-200 transition-colors hover:bg-zinc-700 hover:text-white border border-zinc-700 active:scale-95"
    >
      <FilterX size={13} className="text-rose-400" />
      {q.elimination_hint.label_en}
    </button>
  </div>
)}
```

#### Batch Application & Undo Toast:
```typescript
const handleApplyElimination = (hint: EliminationHint) => {
  const prevCandidates = [...candidateEntities];
  const prevEliminated = [...eliminatedEntities];

  batchMarkEntities(hint.entity_names, hint.action === 'eliminate' ? 'eliminated' : 'candidate');

  toast((t) => (
    <div className="flex items-center gap-3">
      <span>{hint.label_en} applied to map.</span>
      <button
        onClick={() => {
          // Revert back to previous snapshot
          useGameStore.setState({
            candidateEntities: prevCandidates,
            eliminatedEntities: prevEliminated,
          });
          toast.dismiss(t.id);
        }}
        className="rounded bg-zinc-700 px-2 py-0.5 text-xs font-semibold text-white hover:bg-zinc-600"
      >
        Undo
      </button>
    </div>
  ), { duration: 5000 });
};
```

---

## 5. Implementation Across All Game Modes

The dual-state map marking architecture is structured as a shared, reusable pattern that directly upgrades all 4 game modes:

### 5.1 Countrydle (`MapBox.tsx`)
- **Entities:** 195 Sovereign Countries.
- **GeoJSON Source:** `/countries_50m.geojson`.
- **Entity Key:** `feature.properties.SOVEREIGNT.toUpperCase()`.
- **Clue Assistant Scopes:**
  - Continents: Europe (47), Africa (54), Asia (48), Americas (35), Oceania (14).
  - Hemispheres: Northern vs Southern, Eastern vs Western.
  - Landlocked Nations (44 landlocked countries).
  - First-letter alphabetic ranges.

### 5.2 USStatedle (`USStatesMap.tsx`)
- **Entities:** 50 US States + DC.
- **GeoJSON Source:** `/us-states.geojson`.
- **Entity Key:** `feature.properties.name.toUpperCase()`.
- **Clue Assistant Scopes:**
  - Regions: Midwest (12), Northeast (9), South (16), West (13).
  - Coastline: Atlantic Coast, Pacific Coast, Gulf Coast, Inland.
  - Timezones: Eastern, Central, Mountain, Pacific, Alaska, Hawaii.
  - Mississippi River: East vs West of the Mississippi.

### 5.3 Wojewodztwodle (`WojewodztwaMap.tsx`)
- **Entities:** 16 Polish Voivodeships.
- **GeoJSON Source:** `/wojewodztwa.geojson` / `/wojewodztwa-min.geojson`.
- **Entity Key:** `feature.properties.nazwa.toUpperCase()`.
- **Clue Assistant Scopes:**
  - Sea Access: Pomorskie, Zachodniopomorskie, Warmińsko-Mazurskie (Zalew Wiślany).
  - Border Countries: Voivodeships bordering Germany, Czechia, Slovakia, Ukraine, Belarus, Lithuania, Russia (Kaliningrad).
  - Historical Macroregions: Wielkopolska, Małopolska, Mazowsze, Śląsk.

### 5.4 Powiatdle (`PowiatyMap.tsx`)
- **Entities:** 380 Polish Powiaty (66 city counties + 314 land counties).
- **GeoJSON Source:** `/powiaty-min.geojson`.
- **Entity Key:** `feature.properties.nazwa.toUpperCase()` (with disambiguation fallback via TERYT code `kod_teryt`).
- **Performance Optimizations:**
  - Canvas rendering via `L.canvas()` to eliminate 380 individual SVG DOM nodes.
  - O(1) indexed layer lookups (`layerIndexRef.current.get(name)`).
  - Clue Assistant Voivodeship Batching: Question "Is it in Mazowieckie? -> NO" can eliminate all 42 powiaty in Mazowieckie in a single 2ms canvas redraw!

---

## 6. Comprehensive Step-by-Step Implementation Checklist

### Phase 1: Store & Data Layer (`client/src/stores/gameStore.ts`)
- [ ] Add `candidateEntities: string[]`, `eliminatedEntities: string[]`, `markingMode: MapMarkingMode`, `isColorblindMode: boolean` to `GameData`.
- [ ] Add `cycleEntityMark`, `setEntityMark`, `toggleCandidate`, `toggleEliminated`, `batchMarkEntities`, `clearCandidates`, `clearEliminated`, `clearAllMarks`, `setMarkingMode`, `toggleColorblindMode` to `GameActions`.
- [ ] Preserve backward-compatible getters/setters for `selectedEntityNames` and `toggleEntitySelection`.
- [ ] Update `createGameStore` implementation across all 4 store instances (`useCountryGameStore`, `usePowiatyGameStore`, `useUSStatesGameStore`, `useWojewodztwaGameStore`).
- [ ] Update `GuestSnapshot` serialization in `readGuestSnapshot` and `saveGuestSnapshot` to persist visual markings.
- [ ] Write unit tests verifying mark cycling (`neutral -> candidate -> eliminated -> neutral`) and batch marking in `client/src/test/gameStoreMarks.test.ts`.

### Phase 2: Map Controls & Deduction Toolbar (`client/src/components/MapControls.tsx`)
- [ ] Create a shared floating toolbar `MapDeductionToolbar.tsx` with:
  - Tool switcher pills: Candidate Pen (Green), Elimination Eraser (Red/Ghost), Cycle Mode.
  - Entity counters: `Candidates: X | Eliminated: Y | Remaining: Z`.
  - Quick action buttons: `Clear Candidates`, `Clear Eliminated`, `Reset All`.
  - Colorblind / High-Contrast mode toggle.
- [ ] Inject SVG definitions for hatch and cross patterns (`<defs><pattern id="eliminated-hatch">...`) into the map container DOM.

### Phase 3: Map Component Upgrades
- [ ] **`MapBox.tsx` (Countrydle):**
  - Implement `layerIndexRef` map for O(1) feature access.
  - Replace static `#cc2222` / `#22cc22` styling with `getEntityPathStyle(...)`.
  - Bind desktop right-click (`contextmenu`) to `toggleEliminated`.
  - Bind touchstart/touchmove/touchend long-press listener (350ms) to `toggleEliminated`.
  - Mount `MapDeductionToolbar`.
- [ ] **`USStatesMap.tsx` (USStatedle):**
  - Mirror dual-state styling and pointer event bindings.
  - Mount `MapDeductionToolbar`.
- [ ] **`WojewodztwaMap.tsx` (Wojewodztwodle):**
  - Mirror dual-state styling and pointer event bindings.
  - Mount `MapDeductionToolbar`.
- [ ] **`PowiatyMap.tsx` (Powiatdle):**
  - Configure `L.canvas()` renderer to optimize 380-feature rendering.
  - Ensure TERYT/name key uniqueness for city vs land counties.
  - Optimize batch voivodeship elimination redraws.

### Phase 4: Clue-Assisted Auto-Elimination (`History.tsx` & Backend)
- [ ] Update `schemas/countrydle.py` to support optional `EliminationHint` schema in `FullQuestionDisplay`.
- [ ] In `server/countrydle/local_answering.py`, attach `elimination_hint` when answering questions on known closed categories (continent, hemisphere, coastline, landlocked).
- [ ] In `client/src/components/History.tsx`:
  - Render deduction action badge on qualifying answered questions.
  - Hook button to `batchMarkEntities`.
  - Display non-intrusive toast with `Undo` capability.
  - Mark badge as `[✓ Applied]` once active.

### Phase 5: Accessibility & Colorblind Mode Verification
- [ ] Verify Protanopia, Deuteranopia, and Tritanopia color palettes in DevTools Color Vision Deficiency emulation.
- [ ] Verify that Eliminated entities are immediately distinguishable from Candidate entities via both luminance and 45° diagonal hatch patterns.
- [ ] Add ARIA descriptions (`aria-label="${name}: ${status}"`) to interactive SVG map paths.
- [ ] Ensure full keyboard accessibility: focusing a map entity and pressing `Space` cycles state, pressing `Delete` or `E` eliminates, pressing `C` marks candidate.

---

## 7. Verification Proof & Acceptance Criteria

1. **Dual-State Cycle Verification:**
   - Clicking a neutral country (e.g. France) turns it Emerald (Candidate).
   - Clicking it a second time turns it Dimmed Slate with dashed border (Eliminated).
   - Clicking it a third time returns it to Neutral.
2. **Right-Click Desktop Shortcut:**
   - Right-clicking any neutral or candidate country instantly marks it Eliminated without displaying the browser context menu.
   - Right-clicking an eliminated country resets it to Neutral.
3. **Mobile Long-Press:**
   - Holding a finger on a country for ≥ 350ms triggers haptic vibration and toggles Eliminated.
   - Panning or dragging the map does NOT trigger long-press.
4. **Clue Assistant Opt-In:**
   - Asking "Is it in Europe?" and receiving "NO" produces a badge: `[ 🚫 Apply to Map: Eliminate Europe (47) ]`.
   - The map does NOT eliminate Europe until the player clicks the button.
   - Clicking the button dims all 47 European countries. Clicking `Undo` on the toast immediately restores their previous states.
5. **Performance Benchmark on Powiatdle:**
   - On `PowiatyMap.tsx`, batch-eliminating an entire voivodeship (e.g., 42 powiaty in Mazowieckie) completes in under 16ms (1 frame @ 60 FPS) using the indexed canvas/layer optimization without stutter.
6. **Persistence Check:**
   - Marking 3 candidates and 10 eliminated countries, then reloading the page preserves all 13 marked entities.
7. **Game Over Safety Invariant:**
   - Once the game is won or lost, the correct entity is highlighted in vivid gold/green and locked; clicking it cannot accidentally mark it as eliminated.
