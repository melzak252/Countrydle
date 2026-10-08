## Installation and verification

Use **Bun 1.3.14** for the frontend regression suite. Supported Node build
runtimes are **20.19+ within Node 20, or 22.12+** (Vite 7's requirement);
the system Node 18 is not supported. Python **3.10+**, Linux and Chrome/Chromium
are needed for the build's prerender step; set `CHROME_BIN` if not auto-detected.

From `client/`:

```bash
# Reproduce the committed npm dependency lock; use a supported Node version.
npm ci

# Complete existing regression suite, including bun:test and node:test files.
bun run test

# TypeScript project-reference check, Vite bundle, then Python prerender.
# Choose the local backend built from this revision, not another running preview.
VITE_API_URL=/api PRERENDER_API_TARGET=http://127.0.0.1:8086 bun run --bun build

# Local frontend, using the backend at the configured API proxy target.
API_PROXY_TARGET=http://127.0.0.1:8080 bun run --bun dev
```

`test` runs `bun test ./tests` and then the Python prerender regressions, not an
enumerated TypeScript file list: existing Bun/Node test-API files and newly added
tests in that directory are included.
Assertion failures must return nonzero. To prove propagation, use an isolated checkout/copy, add
a temporary `tests/controlledFailure.test.ts` containing
`import { test, expect } from 'bun:test'; test('controlled failure', () => expect(1).toBe(2));`,
run `bun run test`, and remove that file afterward. Never commit that probe.

### Static HTML snapshots

`build` runs `tsc -b`, Vite, and `python3 scripts/prerender.py`; the Python step
uses only the standard library and the Chrome/Chromium CLI. The supported
container runtime is Linux with Node 20.19+, Python 3.10+ and Chromium
(`client/Dockerfile` installs Python/Chromium in its Node 20 Alpine build stage).

Use an installed Chrome/Chromium **CLI** for prerendering, not automatically
the E2E runner's executable. CDP/Playwright compatibility does not establish
working `--headless --dump-dom` process-exit behavior. The hardening smoke used
system Google Chrome and the container's Chromium; the host's Playwright-bundled
Chrome timed out even for `about:blank`, independently of the application/API.

Set `PRERENDER_API_TARGET` to the **matching local backend origin**, for example
`http://127.0.0.1:8086`. An explicitly supplied `API_PROXY_TARGET` is also accepted;
`PRERENDER_API_TARGET` takes precedence. Origins must be local HTTP addresses,
without `/api`, credentials, query parameters or fragments. Compile with
`VITE_API_URL=/api` so browser requests use the snapshot server's selected proxy,
not an absolute API URL baked into the bundle. There is no implicit port-8080
fallback. Start the matched backend before building and use disposable
local data, without production credentials/providers.

The step snapshots all sixteen declared routes, `/blog`, and every post returned
by the existing `/blog?limit=50` discovery query. Discovery failure is an error,
not permission to silently drop post snapshots. Browser traffic can only reach
the temporary asset server; its `/api/` proxy forwards **GETs only** to the selected
backend. Backend redirects, external ads/analytics and browser background traffic
are blocked during rendering, without removing their tags from output.

For a deliberately backend-free build, explicitly set `PRERENDER_STATIC_ONLY=1`
and leave both backend-target variables unset:

```bash
VITE_API_URL=/api PRERENDER_STATIC_ONLY=1 bun run --bun build
```

This still snapshots **all sixteen declared routes and `/blog`**. It logs
STATIC-ONLY, makes no backend requests, and returns real HTTP 503 responses for
API GETs: API-dependent pages therefore render their unavailable state, not
invented content. Dynamic post snapshots are intentionally unavailable in this
mode; use the configured-backend mode for complete data-backed output. Selecting
both static-only and a backend target is an error, not an ambiguous fallback.

The Docker build explicitly defaults to static-only for backend-free CI and
forwards `PRERENDER_STATIC_ONLY` and `PRERENDER_API_TARGET` build args. To include
dynamic posts, set `--build-arg PRERENDER_STATIC_ONLY=0` and
`--build-arg PRERENDER_API_TARGET=http://127.0.0.1:8086`; that matching local
backend must be reachable inside the build network (for example Linux
`--network=host`). A configured backend failure still fails the build; it does
not switch to static-only automatically.

Each route has a fresh private browser profile and a fixed 15-second browser
deadline; backend GETs and idle asset connections have five-second timeouts.
Asset/API requests are served concurrently. The script kills/reaps only its owned
browser processes (including detached helpers), removes profiles, and closes its
server on success, failure, Ctrl-C or SIGTERM. It reports the actual combined
route denominator and exits nonzero for missing prerequisites, configured-backend
discovery/API failures, failed Chrome execution or an empty/incomplete rendered
application. Failed renders are not written as successful snapshots.

Focused lifecycle/proxy regressions, separate from the Bun TypeScript suite:

```bash
python3 -m unittest discover -s tests -p 'test_prerender.py' -v
```

### Browser journeys (opt-in locally)

Playwright is a pinned development dependency, executed under supported **Node**
(not forced through Bun's runtime). Ordinary `test` does not run browser journeys;
both desktop and mobile projects are mandatory in CI.

Provision a disposable loopback PostgreSQL database named `countrydle_e2e`,
owned by a non-superuser login named `e2e`, with `vector` installed by the
bootstrap administrator. Do not reuse the application's normal database/user.
Supply that explicit URL and a Python 3.12 interpreter with the locked server
dependencies:

```bash
bunx playwright install chromium
export E2E_DATABASE_URL='postgresql+asyncpg://e2e:DISPOSABLE_PASSWORD@127.0.0.1:5432/countrydle_e2e'
E2E_PYTHON=/path/to/locked/python bun run test:e2e
```

CI Linux provisioning can use `bunx playwright install --with-deps chromium`.
The configuration owns frontend/API startup on `E2E_WEB_PORT`/`E2E_API_PORT`
(defaults 5181/8087) and a fresh `countrydle_e2e_<hex>` schema; occupied ports,
wrong database/role/host, version or source-fingerprint mismatches fail rather
than attaching to an unrelated preview. Its private fact snapshot is a reviewed
small fixture, not a complete geography database.
The sandbox disables dotenv, paid providers, mail, schedulers and production
startup effects; actual HTTP handlers, cookies, PostgreSQL and React stores are
used. Owned schema/processes are removed on exit. No live-player accounts,
production credentials or gameplay writes are permitted.

The journeys cover guest reload, false/unresolved question accounting, rejected
guesses, win/loss, login/sync, failed-sync recovery and authoritative account
precedence, with no project filter. Accessibility journeys exercise actual
eligible entity lists, keyboard markings, modal focus containment/restoration,
Escape, changing focusable controls and localized desktop/mobile surfaces.
Captured/frozen answering boundaries are behavioral fixtures, not live
interpretation or answer-quality evidence.

### Dependency lock regeneration

Edit `package.json` only for an intentional dependency change, then run:

```bash
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
```

Keep the existing lock present and review/commit `package.json` and
`package-lock.json` together. Do not use `npm update` or delete the lock during
routine regeneration: that would upgrade unrelated dependencies.

## Admin workspace

`/admin` provides thirteen direct destinations: Overview, Sessions, Live feed,
Users, Suggestions, Friend duels, Question audit, Player reports, Question testing,
Template audit, Facts editor, Cache, and AI Costs. Desktop uses one sidebar grouped into
Players, Knowledge & QA, and System; narrow layouts use a labelled native page
selector. Each destination has one page heading. Styles are scoped to
`.admin-workspace`, with visible keyboard focus and 44px primary controls; public
game and contact layouts retain their own styling.

- Sessions put the target, four summary metrics, and player list before optional
  strategy analysis. Replays retain recorded chronological questions and guesses;
  strategy lists show six entries initially.
- Question audit uses six summary columns on desktop and equivalent cards on
  phones. Details preserve complete questions, explanations, context, identifiers,
  and invalidation actions. Filters and pagination do not present old rows as new
  results while a query is pending or has failed.
- Live feed supports paused, 10-second, and 30-second refresh. Automatic refresh
  waits for completion before scheduling another request. Failed refreshes retain
  an explicitly stale snapshot without changing the last-success timestamp;
  switching modes clears the old snapshot.
- Reports and template divergences retain review/reopen and QA handoffs. Question
  testing uses current data/models, not a historical replay, and does not consume
  attempts or change player progress. It offers the nine API-supported test modes.
- Facts are selected by entity name and writes use the returned SQLite entity ID,
  not the unrelated PostgreSQL selector ID. Saves, list additions, and deletions
  take effect immediately; pending writes disable editing and failures remain visible.
- Friend-duel agreements are comparisons, not verified truth. Cache counters are
  scoped to one backend process and describe question plans, not target answers.

Admin interface copy is available in English and Polish. Recorded player text,
fact relation names, and technical identifiers retain their original values.

## General Suggestion Box

`/contact` hosts the General Suggestion Box for guests and signed-in players.
Choose general feedback, a bug report, a feature request, or a data correction;
name and email are optional. Submissions are stored through `POST /suggestions`.
The form confirms success only after the backend returns `201`, prevents repeat
submits while pending, and preserves the draft on failure. Public copy is
available in English and Polish. Direct email support remains a separate link.
Character limits count Unicode code points consistently with the backend.
Submission cooldowns show a localized message and retain the draft for retry.

In `/admin`, open **Players → Suggestions** to read the full message,
topic, submission time, guest/player identity, and any provided contact details.
The list is newest first, has 25 suggestions per page, and supports refresh and
retry. Backend authorization protects the messages and contact information;
they are not exposed in a public feed.

## Daily game question chat

`src/components/QuestionChat.tsx` renders the shared conversation for the world,
continental, US state, powiat, and voivodeship game pages. Pages provide questions
in chronological order and retain ownership of scrolling and game state.
Player questions appear on the right; replies and answer status appear on the left.
Valid explanations are not mounted until the game is over. Local Countrydle,
continental and Flagdle template explanations then include the country name and
readable stored facts. Their active API responses also omit factual explanations,
not merely hide them in the DOM. Invalid/unverified feedback remains available
immediately, with target-free guidance rather than provider facts or target-bearing
rewrites. Post-game answer reports retain their mode and question identifiers.
`QuestionInput.tsx` and `GuessInput.tsx` supply the shared forms;
`GameActionComposer.tsx` hosts the active form in the chat footer.

The shared daily question chat keeps its thinking animation visible for at least
1,000 ms from submission when a question response returns. Requests that already
take one second or longer receive no additional animation delay. Network and HTTP
failure handling remains immediate.

In daily games, the top `Questions`/`Guesses` tabs choose both displayed history and
active input; no second selector appears by the composer. Phone labels are shortened
to `Ask`/`Guess`, with attempt counts. Friend-duel controls remain in their chat footer.

Player questions, including pending and rejected submissions, remain text-selectable
and each has a copy control that copies the original text. Map tooltips stay anchored
to the hovered feature instead of following the pointer. Desktop tiles refresh
during pan; phone tiles wait for pan to settle. Existing background tiles remain
visible during zoom before fresh detail appears.

Rejected questions, duplicate guesses, and submission failures appear as chat
notices with the submitted text, a reason, and a next step instead of expiring
toasts. Notices open the question chat and remain for the current in-memory game
session, including same-day state refreshes and later successful submissions.
They clear on a new puzzle, game reset, or page reload. Notices are separate from
accepted questions/guesses: they do not consume attempts or enter guest sync.
Failed submissions retain their input for editing. Network/server failures do not
claim that a submission was rejected; they advise checking history before retrying.
Warnings are attributed to Countrydle and start expanded; their title toggles the
reason and next-step details with mouse, touch, or keyboard. New warnings expose
their reason and next step as accessible alerts without making the entire
conversation a live region. Conversation ordering
treats timezone-naive API question timestamps as UTC, keeping warnings between
the questions that precede and follow them rather than grouping warnings last.

## Daily results explorer

World, continental, US state, powiat, and voivodeship results share
`ShareResultCard.tsx`. The card owns modal scrolling; neither its dialog overlay
nor its wrapper adds a second scrollbar. Outcome, score, attempt counts, the
next-puzzle countdown, and share actions precede the geographic details.
Sharing uses native sharing when available and otherwise copies spoiler-free
result text; Copy Card always copies that text.

Location Field Notes is the initial explorer panel. Question History appears
only when both the question count and saved question list are nonzero. Tabs
support Left/Right, Home/End, and normal keyboard activation. Both panels remain
in server-rendered markup, with the inactive panel hidden from display and the
accessibility tree. Results use `ResultsQuestionHistory.tsx`, not the live-game
chat bubbles: wrapped question/answer rows start collapsed, and selecting a row
reveals its complete explanation, copy action, and report controls. Only one row
expands at a time. Notices retain chronological ordering and their full details.
Facts, neighbors, and expanded explanations use the card's sole scrollbar;
the page behind the modal is scroll-locked until dismissal. Answer reports
retain their original mode and question identifiers. Regional modes use the
returned daily Border Hop
target rather than treating a county or voivodeship as a country.

The footer retains cross-game navigation and Close and View Map, with mobile
safe-area padding. Interface labels are localized in English and Polish.

Question History renders `FactProvenance.tsx` only from the server's terminal
`fact_provenance` records. Citation, effective interval, retrieval/update dates
and convention are localized labels; unknown values stay visibly unknown.
Active question/state responses contain no detailed target-linked evidence.
Admin facts allow evidence-only edits without altering the selected fact value.
Membership accession evidence and the disputed São Tomé and Príncipe hemisphere
convention are preserved end-to-end; displaying the dispute does not resolve it.

## Mobile layout

- Daily map games use a full-width, 44px status row immediately below the app
  header, with question count, guess count, and labelled `Guide` action sharing
  equal-width sections. It remains visible with either the map or notebook open.
  Active duels use two rows to retain player counts, countdown, and secret controls.
- Daily map games and friend duels open a full-height action panel on phones,
  filling the game area below the status row. A high-contrast, 44px `Back to map`
  (`Wróć do mapy`) button collapses the notebook;
  `Ask`/`Guess` restores the corresponding history and input.
- Opening or switching histories scrolls to the newest response or guess. History
  scrolls independently above the pinned composer; manual scrolling remains
  unchanged until a new entry arrives or the selected history changes.
- The shared fullscreen shell tracks `visualViewport` through `--app-height`,
  accounting for browser chrome and reduced keyboard space. At 560px viewport
  height or less on phones, quick-question suggestions hide to leave room for the input
  and history. Expanded active duels retain their turn status and countdown;
  at reduced heights, `Back to map` moves into the status row and the redundant notebook
  heading and optional composer hint hide so the input stays visible.
- The mobile version badge uses readable text on a dark background and respects
  the bottom safe area without intercepting taps. The client version comes from
  `package.json`, including when Vite is launched directly rather than through npm.
  Desktop keeps the compact map-return icon and subdued version label.
- Phone map taps mark red; repeating a tap removes the mark. The colour picker
  is desktop-only. Zoom, reset, reference-line, clear and revealed-target controls
  form a left column with 44px touch targets. Regional maps also expose reset view;
  resetting the view preserves markings, while the eraser clears them.
- Mobile inputs use 16px text; question and answer text uses 14px. Navigation,
  autocomplete options and primary actions retain 44px touch targets. Dialogs and
  lists scroll within the available height, with safe-area padding on bottom controls.
- The phone menu fits narrow screens and restores focus to its trigger on Escape.
  Archive uses a grouped mode selector; leaderboard rows retain rank, player, and
  score without requiring horizontal scrolling.
- Desktop map panels and multi-column browsing layouts retain their existing
  breakpoint behavior. The dark palette, typography, routes, and gameplay rules are
  unchanged.

## Map interaction and loading

Daily pages load game state and entities through their mode's Zustand store, then
mount the world/continental or regional map. Friend duels supply the same controlled
maps with their own interaction state.

`EntityMarkControls.tsx` supplies a keyboard-operable eligible entity selector
and candidate, exclusion and removal controls beside every affected daily/duel
map. Pressed state and a live marking announcement use the map's existing
interaction state; no second marking store is introduced. The selector locks
revealed targets. Pointer/context-menu and trusted touch events still toggle
the actual Canvas geometry; mobile map/notebook switching retains those marks.

`src/hooks/useModalFocus.ts` owns the affected dialogs' shared lifecycle: initial
focus inside, Tab/Shift+Tab containment, Escape where dismissal is permitted,
scroll locking and restoration to a usable opener/fallback. Dynamic disabled
controls and Strict Mode mounts are part of the browser regressions.

Readability changes preserve geometry, hierarchy and dark/green styling:
important small labels use at least 12px, notebook text/placeholder contrast is
raised, controls retain visible focus and mobile targets are at least 44px.
The actual 390×844 error/active surface measured 45 visible normal/large text
pairs with no AA failures (minimum 6.19:1; composer placeholder 6.91:1).
Observed composer border contrast was 6.91:1 and its green focus indicator
9.22:1 against the opaque composer background, above the 3:1 non-text threshold.
Disabled controls are distinct and exempt from the normal-text contrast check.
Empty, active, error, disabled and result surfaces were inspected; viewport
scroll width remained 390px. Native 200% desktop zoom was also exercised.
The desktop browser's actual safe-area inset is zero; physical iOS notch and
virtual-keyboard behavior are not certified by desktop emulation.

Guest persistence is a server projection, not authoritative localStorage
counters. `gameStore.ts` single-flights account/date sync and retires only the
exact successful snapshot; a failed sync or newly saved snapshot remains
retryable. Existing meaningful account progress takes precedence. These rules
are shared by the factory's daily consumers, with explicit mode quotas/scoring.

- `src/lib/mapData.ts` shares parsed GeoJSON and in-flight requests by URL across
  map mounts. County geometry no longer uses a timestamp cache-buster. Failed
  downloads are not cached, so an explicit retry can recover.
- `src/hooks/useMapData.ts` ignores results from unmounted/obsolete loads and hides
  old geometry when the asset URL changes. `MapLoading.tsx` preserves the caller's
  map dimensions, announces loading/failure, and offers English/Polish retry copy.
- All four maps use 60px wheel sensitivity and half-level zoom buttons. Wheel/pinch
  zoom stays fractional, without snapping on release. Phone double-tap zoom is
  disabled so quick repeat taps toggle a mark without moving the camera; desktop
  double-click zoom remains enabled.
- Tile buffers retain two rows instead of eight/twelve. Desktop pan loading uses
  a 200ms update interval; phones use idle updates. Intermediate pinch zoom levels
  are not requested, and existing tiles stay visible while moving.
- Phone zoom, reset, clear, reference-line, and revealed-target controls have
  44px hit targets; desktop controls retain their compact sizing.
- `src/hooks/useMapZoomSync.ts` keeps the active background tile level synchronized
  with the borders during zoom. Other tile levels wait until the animation ends;
  late CSS transforms finish before new detail becomes visible.
- `src/lib/mapRenderer.ts` gives each map its own Leaflet Canvas renderer. Zoom
  transforms a prepainted border bitmap rather than complex SVG strokes. A
  half-viewport buffer is refreshed during movement, before the visible camera
  reaches its edge; redraw no longer waits solely for `moveend`. Continuous
  pinch-out also rebases the bitmap before it shrinks below the viewport. The
  small Leaflet 1.9 bounds/projection/update adapter is isolated in this file.
  Same-size redraws reuse the backing bitmap and replace the context transform,
  avoiding both bitmap reallocation and accumulated retina scaling. An unchanged
  camera skips the duplicate movement-end redraw; view resets and viewport resizing
  still refresh the renderer.
- Collapsed desktop notebooks use content width instead of the expanded 28rem
  width. Phone Ask/Guess bars remain full-width.
- Stable GeoJSON style callbacks avoid redrawing borders when only the selected
  marker color or unrelated game state changes. Latest interaction props are
  published in `useLayoutEffect`, not during render; markings and reveals still
  update layer styles immediately.
- `src/lib/mapView.ts` replaces long fly-to sequences with short view transitions,
  adds reveal padding, and respects reduced motion. Navigation requested during
  Leaflet's animated zoom waits for that zoom to finish; the latest request wins.
- Regional reset controls restore their original center/zoom without clearing
  markings. Country/continental maps retain reset and reference-line controls.

Regression checks: `bun test tests/mapData.test.ts tests/mapGeometry.test.ts`.
Browser verification must also cover pan/zoom in both directions (wheel and phone
pinch), in-motion border/background alignment, painted border pixels on the newly
exposed side while a drag is still held, resize at normal/retina pixel ratios,
reset during zoom, mark/unmark, reveal,
map-asset failures, and collapsed desktop/phone layouts; unit checks alone do not
prove usability.

## Display geometry

`scripts/simplify-map-geometry.mjs` regenerates display-only GeoJSON through pinned
Mapshaper 0.7.76, without adding a runtime dependency. It jointly simplifies shared
boundaries in EPSG:3857; intervals are projected metres, not ground distances.
Always use an unsimplified source asset, never a previously generated output:

```sh
bun scripts/simplify-map-geometry.mjs /path/to/original/wojewodztwa.geojson public/wojewodztwa.geojson 200
```

The generator preserves feature IDs/properties/order, polygon parts, holes, and
winding. Wrapped/dateline features, polar rings outside Web Mercator, and existing
zero-area rings remain unchanged. Shared anchors and original zero-width boundary
spurs are restored on both sides so selectable strokes are not silently removed.

| Asset | Projected interval (m) | Vertices before → after |
| --- | ---: | ---: |
| `countries_50m.geojson` | 300 | 94,718 → 90,257 |
| `europe.geojson` | 500 | 22,640 → 21,727 |
| `asia.geojson` | 500 | 30,552 → 28,137 |
| `africa.geojson` | 500 | 12,980 → 10,448 |
| `americas.geojson` | 500 | 28,868 → 27,264 |
| `wojewodztwa.geojson` | 200 | 76,881 → 18,198 |
| `powiaty-min.geojson` | 75 | 18,931 → 18,829 |
| `us-states.geojson` | 100 | 3,539 → 3,517 |

Generation checks measured less than 2 CSS pixels of original-vertex-to-output-edge
error at each map's maximum zoom, with unchanged entity/part/hole counts and shared
entity-pair boundaries. Leaflet's runtime simplification is separate from this
generation error budget. County/state sources were already coarse, so their
reductions are deliberately small.

Voivodeship vertices decreased 76.3%, and its payload decreased from 1,368,743 to
325,437 bytes (76.2%). Six synchronous zoom changes in the same desktop browser
measured a median 38.45ms with the original asset versus 15.05ms with the generated
asset using the previous SVG renderer. This isolates geometry projection/redraw
cost, not current Canvas performance or an FPS guarantee.
Fact databases, entity names, and server answering are unchanged.

## Friend duels

Create a duel at `/friends`; invitations open `/duel/:code`.

The create/join entry backdrop is confined to the game area below the navbar.
Entry is a labelled page region, not a modal dialog; desktop navigation and
the mobile menu remain available while choosing a geography or guest name.
Geography uses a grouped native select with entity counts; the browser/device
picker is not clipped by the entry card and supports keyboard and touch selection.

- Questions and guesses have no per-match limit. Daily-mode quotas do not apply.
- Each question or guess spends one turn; turn timers and final-reply rules still apply.
- The HUD displays cumulative counts as `Q:<questions> G:<guesses>`, not used/max quotas. The active-turn composer and rules explain that both action types are unlimited.
- A final reply allows one guess or a pass, not another question.

## Result sharing icons

`src/components/ShareResultCard.tsx` uses inline SVG brand marks for WhatsApp and X,
from [Simple Icons](https://github.com/simple-icons/simple-icons) (CC0), rather than
text placeholders or font-dependent glyphs. The decorative icons inherit button
colors; accessible names remain on the share buttons. Sharing URLs are unchanged.

## Remembered login

The login page offers an unchecked-by-default **Remember me** checkbox for both
password and Google login. `POST /login` accepts the optional form field
`remember_me`; `POST /google-signin` accepts the same boolean in its JSON body.
Omitting it keeps the ordinary `ACCESS_TOKEN_EXPIRE_MINUTES` lifetime (60 minutes
by default). Google registration also keeps the ordinary lifetime.

Remembered logins use `REMEMBER_ME_EXPIRE_DAYS` (90 days by default). The HttpOnly
`access_token` cookie and signed JWT expire together. Authenticated requests
renew the selected idle window, including `/users/me` and profile updates;
activity never downgrades a remembered login to one hour. Cookies use
`SameSite=Lax`, `Path=/`, and `Secure` on HTTPS requests. TLS-terminating deployments
must pass the original HTTPS scheme through a trusted proxy.

Logout removes the cookie on this device. Browser cookie deletion, private
browsing, and inactivity beyond the selected window still require login again.
Tokens remain in HttpOnly cookies, not localStorage; the existing localStorage
entry contains only user display data. Use remembered login only on private
devices: as with existing stateless JWT authentication, logout does not revoke
copies of a token obtained elsewhere before its expiry.

## About and FAQ content

`src/pages/AboutPage.tsx` and `src/pages/FAQPage.tsx` describe the nine daily modes,
friend duels, mode-specific scoring, AI/data limitations, guest persistence and
sync, archive/profile coverage, and remembered login. Translated headings live in
`src/i18n.ts`; update those alongside the page fallbacks.

Keep these claims aligned with `server/game_logic.py`, the per-mode API routes,
authentication settings, data builders, and actual analytics/ad loading. Do not
promise error-free AI answers, local-only guest activity, or lossless sync.
Content-only updates should be checked in the browser at desktop/mobile widths,
including FAQ search, topic filters, and keyboard accordion controls.

## Contact and feedback

The `/contact` page uses `melzacki.jakub@gmail.com` for direct support and feedback submissions. Keep this address aligned with support contacts in server email templates.

## Legal document presentation

`/terms`, `/privacy-policy`, and `/cookie-policy` share
`src/components/LegalDocument.tsx`: a left-aligned serif title, update date,
readable document column, and thin section dividers matching the public pages.
The component owns section, paragraph, list, and link styling; each policy page
owns its wording, links, and update date. Presentation-only changes must preserve
those values. Cookie Policy retains the existing `PrivacySettingsButton` and
Google CMP behavior described below.

Use **Countrydle** as the project name and `https://countrydle.online` for
public-site links. Keep personal author attribution and the support address
`melzacki.jakub@gmail.com` distinct from the project branding.

The October 6, 2026 disclosure update distinguishes browser expiry from server
retention, covers guest-to-account linking, Gemini question processing and
OpenAI retrieval embeddings, and identifies persistent question-plan storage.
Daily history, participation, answer reports, suggestions and planner-cache
records have no general automatic expiry. Friend-duel cleanup remains subject
to the existing 30/90-day rules and unresolved-work exceptions. Do not describe
guest identifiers as anonymous or promise self-service account deletion.

Keep the storage inventory aligned with `server/users/utils.py`,
`server/utils/guest_session.py`, `server/friend_matches/routes.py`,
`src/stores/gameStore.ts`, `src/stores/authStore.ts` and
`src/lib/guestHistory.ts`. Login durations are configurable defaults; local
history has no automatic expiry. Legal pages remain English-language documents,
as before. Verify all three routes at desktop and mobile widths after copy edits.

These disclosures do not establish deployment compliance. The operator must
verify analytics collection/storage, provider account terms and international
transfer arrangements, operational retention/deletion procedures (including
logs and backups), and actual audience/children's-data handling. Do not add
AdinPlay recipients or cookie entries until an integration actually exists.

## Advertising consent and public discovery

`index.html` currently contains an unconditional AdSense script and publisher
meta tag. `main.tsx` also has a build-configured loader, but its existing-meta
check normally skips that branch. Setting `VITE_GOOGLE_ADSENSE_ID` blank does
not disable the static tag. Keep `public/ads.txt` aligned with the deployed
publisher account. Neither the AdSense loader nor the optional Rybbit loader
has an application-side consent gate.

The privacy control delegates to Google's Privacy & messaging service, not the
former `cookie-consent` localStorage banner. Existing values of that old key
are not treated as consent. `PrivacySettingsButton.tsx` invokes Google's
callback queue and `showRevocationMessage()` API. It is available in the footer,
navigation menus and Cookie Policy. If Google's API is unavailable, the button
reports that no choices were changed. This hook alone does not prove that a
certified CMP is published, a particular TCF version is active, or that consent
is enforced. Policy copy intentionally makes no such unverified promises.

**Account prerequisite:** In AdSense → Privacy & messaging → European
regulations, configure and publish the message for `countrydle.online`. Set the
privacy policy URL to `https://countrydle.online/privacy-policy`, provide the
required consent/refusal choices and languages, then verify a fresh EEA visit,
acceptance, refusal, and reopening through Privacy settings. The existing
AdSense tag loads published Google messages; repository changes do not publish
messages or approve the website. Google's documented preview URL is
`https://countrydle.online/?fc=alwaysshow&fctype=gdpr`; it also requires a
published message. Rybbit configuration is separate from advertising consent.

The router updates one production-origin canonical URL from the normalized
pathname, excluding query parameters and fragments. `/sitemap.xml` is served
by FastAPI from current public routes and database blog records dated no later
than the current UTC date. Both Nginx configurations and the Vite proxy forward
that public URL to the backend; there is no checked-in static article sitemap.
`robots.txt` continues to advertise the same public sitemap URL.

Verify with the frontend production build, browser navigation between public
pages, the privacy settings unavailable/provider paths, and
`pytest tests/test_sitemap.py -q` in the backend environment. Check
`/sitemap.xml` through the frontend proxy as well as the backend.

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Player profiles

`/profile/:username` shows daily-game statistics for Countrydle, Flagdle,
Europe, Asia, Africa, the Americas, Powiatdle, US States, and Województwa.
The selector groups them as World, Continents, and Regional, with casual
friend matches under Just for fun. Daily games played counts actual activity;
win rate is wins divided by completed games, average points uses completed
games, average winning guesses uses successful games, and streaks follow
consecutive puzzle dates. Recent history is supplied newest first by the API,
which also keeps unreleased target names concealed for public visitors.

Friend matches show finished casual match counts, outcomes, win rate, and
recent history. They have no points and do not affect public leaderboard
rankings. Nickname editing, the server's change restriction, URL replacement,
and separate missing-player and retryable-error states remain supported.
Profile labels live under `profile` in `src/i18n.ts`.


## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
