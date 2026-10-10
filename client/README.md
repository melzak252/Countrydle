## Client runtime and verification

The Vite development server and `npm run build` use the existing TypeScript/Vite
pipeline. The production serving image contains Nginx and a Python standard-library
read-only artifact reader, not Chromium or websocket-client. An explicit off-host
one-shot capture image produces matching immutable publisher HTML; gameplay and
private routes retain the SPA shell. Image builds need no backend credentials or
content service. Existing Bun tests cover gameplay, publisher metadata, content
parsing, editorial conflicts and advertising/consent decisions.

## Public mobile layout

Below 1280px, navigation uses a compact header and a native modal dialog instead
of expanding the page header. Play, Blog, Leaderboard and account actions remain
direct links; game categories, guides, help and privacy use disclosures. The
dialog scrolls independently, restores focus on dismissal, and closes on route
changes, Escape, backdrop clicks and desktop resize. The technical version badge
is desktop-only. The compact footer contains Privacy, Cookies, Terms of Use,
Contact and Privacy settings; games, blog, guides and help remain in the header.

Phone map controls use 36px buttons and a compact vertical stack for zoom, reset,
clear, reference lines and the revealed-target action. Desktop sizing is unchanged.

The homepage puts one daily-puzzle action first, followed by the spinning globe
on phones as well as desktop. Guest progress controls the play/continue/result
label only when its date and loading state are current. Other games, rules and
device progress are available through disclosures. The globe supports horizontal
drag, tap and keyboard-operable pause/resume; vertical touch gestures can scroll
the page, and reduced-motion mode starts paused.
The other-games link stays on a separate line with 1rem of top spacing.

The country journal keeps search visible and groups continent, difficulty and
sorting controls in one disclosure. Articles use the country-name hero, compact
dark facts cards and the earlier two-curiosity treatment. Facts and curiosities
precede optional daily statistics and two independently ranked question lists:
most common overall and most common among recorded winners. Sharing, source
links and related articles remain available. Rankings display real recorded
questions, submission counts and YES/NO answer badges; unknown recorded answers
use a neutral badge. Counts are submissions, not unique players, and percentages
are not displayed. Empty lists say that recorded data is unavailable; generated
deduction steps, explanations, pro tips and long summary/analysis panels are not
used as fallbacks. Stored article content is not rewritten by this presentation.
Trivia appears only when a real quiz was recorded; no distractors are invented.
Public and editor response contracts share `src/blogContent.ts` Zod schemas.
When `game_debrief` is present, the native API payload must contain both
`top_questions` and `top_winner_questions`; there is no old-payload rollout shim.
Past-day, retry, editorial-review and advertising gates remain unchanged.
The question inspector stacks its tabs on phones and confines JSON/SQL scrolling
to labelled, focusable code panels.
The Americas filter includes articles tagged North America, South America or
Americas, while still combining with the search and difficulty filters.

Verification used real Chromium rendering and interactions at 320, 390, 430,
768, 1024 and 1440px in English and Polish for home, journal, article and world
game, plus narrow public-route and landscape/short-viewport checks. Expanded
navigation, long usernames, filters/search/reset, trivia, clipboard sharing,
guest-state transitions, globe gestures/reduced motion and all eight inspector
examples across three panels were exercised. API responses were controlled
fixtures because no Countrydle backend was running; live backend content, native
device sharing and physical-device keyboard/notch behavior were not verified.

## Admin workspace

`/admin` provides fourteen direct destinations: Overview, Sessions, Live feed,
Users, Suggestions, Friend duels, Blogs, Question audit, Player reports, Question
testing, Template audit, Facts editor, Cache, and AI Costs. Desktop uses one sidebar grouped into
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

On desktop, the question form restores typing focus after a submission and after
mouse clicks or right-clicks on the map. Map interaction during a pending request
restores focus when the response arrives and the input is available again.
The draft and caret survive map clicks; rejected submissions retain the draft.
Map controls, keyboard navigation, guess forms, and touch interactions do not
trigger this focus restoration. Nothing is focused automatically on page load.

`FactProvenance.tsx` retains the read-only evidence renderer for completed Countrydle
and continental questions; source links accept only HTTP(S) URLs. It does not restore
the hardening facts-editor controls. Completed guest history refreshes explanations
for its own stored question IDs without replacing browser-owned progress. Active
chat and result history never mount valid factual explanations or evidence.

Returned question responses keep the loading animation visible until at least
1,000 ms after submission. Responses taking one second or longer incur no extra
display delay. HTTP/network errors retain the existing immediate error feedback.

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

The Guess input recognizes question prefixes, including `do …`, and switches back
to Question with a chat notice rather than submitting a guess. Countrydle and
continental APIs also reject text that is not a known country, so bypassing the
client guard cannot consume an attempt. Selecting a valid country can still use
the preserved final guess.

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

## Publisher delivery, editorial review and advertising

### Readable initial HTML and operational readiness

Readable initial HTML covers the homepage, help and policy pages, Explore, all
nine mode guides, the journal index and published past-day recaps. Responses
contain route-specific titles, descriptions, production canonical URLs and
structured data. Capture suppresses authentication, guest synchronization,
advertising, CMP and analytics; it omits decorative globe interaction and states
the reset time as 00:00 UTC. Browser gameplay and globe interaction are unchanged.

Serving and capture are separate. The serving container runs Nginx plus the
stdlib-only reader on `127.0.0.1:8765`, with the snapshot host directory mounted
read-only. It never launches Chrome or captures on production startup. The
`publisher-capture` image explicitly runs a one-shot worker, publishing a
validated immutable `release-<uuid>` and atomically switching `current`.
Artifacts must match the deployed SPA assets/build fingerprint. Unchanged route
versions reuse validated HTML; changed articles, related links and Explore
metadata are captured incrementally. An entirely unchanged capture reuses its
release UUID without launching Chrome. Failed routes have explicit manifest 503
status, not stale successful HTML or captured error pages.

The reader polls public blog and mode metadata independently. A changed version
returns 503/noindex until matching HTML arrives; a bad article affects its route
and dependent versions, not unrelated static pages. Blog metadata failure makes
blog routes unavailable; mode failure makes Explore unavailable. A failed poll
invalidates that group immediately. Even without a reported failure, successful
metadata expires after `max(2 × poll interval, poll interval + 20 seconds)`
(120 seconds with the default 60-second poll). This is not a 10-minute stale-HTML
allowance: affected routes may remain 503 until the next capture succeeds.
Previously validated homepage/help/guides remain usable during backend or worker
failure. `/healthz` reports matching artifact/mandatory static HTML and SPA-shell
readiness, not global blog/Explore freshness or capture-job success. Missing
initial mandatory static HTML returns 503, never an empty successful SPA.
An authoritative zero-post journal retains its introduction, is noindex and has
no ads. Unknown/deleted posts return 404 when authoritative metadata is available;
unavailable metadata cannot establish a deletion. Today/future recaps remain
private. Published date aliases return 308 to the canonical slug.

#### Development Compose bootstrap

`docker-compose-dev.yml` uses the same separate serving/capture targets and shared
snapshot directory: reader read-only, opt-in worker writable. From the repository
root, with the backend environment configured:

```bash
docker compose -f docker-compose-dev.yml --profile publisher-capture build backend frontend publisher-capture
docker compose -f docker-compose-dev.yml up -d backend
# Wait for the backend's public blog and Explore endpoints to be ready.
docker compose -f docker-compose-dev.yml --profile publisher-capture run --rm publisher-capture
docker compose -f docker-compose-dev.yml up -d frontend
curl --fail http://localhost:5173/healthz
curl --fail http://localhost:5173/faq
```

Both targets must share build arguments; recapture after asset/content changes.
Default startup never launches Chromium. Before a first compatible artifact,
publisher routes and health return 503. Keep the default canonical
`PUBLISHER_ORIGIN=https://countrydle.online` even when browsing locally; captured
HTML rejects loopback origins.

#### Operator setup and scheduled refresh

1. Build/publish the paired immutable GHCR images from the same commit:
   `ghcr.io/<owner>/<repo>-frontend:sha-<40-character commit>` and
   `ghcr.io/<owner>/<repo>-publisher:sha-<same commit>` (or pinned corresponding
   digests). `.github/workflows/docker-publish.yml` shares both targets' build
   arguments: `VITE_API_URL=/api`, `VITE_RYBBIT_SCRIPT_URL`,
   `VITE_RYBBIT_SITE_ID`, `VITE_GOOGLE_ADSENSE_ID`, `VITE_ADSENSE_ENABLED`
   (default `false`) and `VITE_ADSENSE_SLOTS` (default `{}`). Changing public
   build arguments requires a newly matching pair/artifact, not floating `latest`.
2. Prepare an absolute host snapshot directory and set `PUBLISHER_SNAPSHOT_DIR`
   in Compose to it (default `./publisher-snapshots`). The frontend mounts it at
   `/var/run/countrydle-publisher:ro`. Before directing traffic to a new bundle,
   prepare its first compatible artifact and a running candidate serving
   container with that directory mounted. The transport validates inside the
   running container; it cannot bootstrap against an absent container or one
   still using incompatible assets. Coordinate candidate validation, artifact
   promotion and traffic cutover explicitly. This is not an automatic frontend
   deployment or a promise of zero downtime.
3. Configure the existing `.github/workflows/publisher-refresh.yml`: it runs
   every 10 minutes and supports `workflow_dispatch`, with non-interrupting
   concurrency. Required repository variables are `PUBLISHER_CAPTURE_IMAGE`
   (immutable matching `-publisher:sha-…` or digest), `PUBLISHER_BACKEND_URL`
   (real public HTTPS API base), `PUBLISHER_ORIGIN` (public HTTPS origin without
   a path), `PUBLISHER_REMOTE_DIR` (the absolute host directory from step 2),
   `PUBLISHER_CONTAINER_ENGINE` (`docker` or explicitly `podman`) and
   `PUBLISHER_FRONTEND_CONTAINER` (actual running serving container name/ID).
   Optional `PUBLISHER_SSH_PORT` defaults to `22`. The workflow requires
   `contents: read` and `packages: read`; its `GITHUB_TOKEN` must be able to pull
   the chosen GHCR package. Configure build workflow variables separately.
4. Supply secrets `PUBLISHER_SSH_HOST`, `PUBLISHER_SSH_USER`,
   `PUBLISHER_SSH_KEY` and `PUBLISHER_SSH_KNOWN_HOSTS`. Verify the host key
   independently and provide the matching known-hosts entry, including the port
   form if nonstandard; strict host verification is never disabled. The SSH
   account needs host Python 3/rsync, write/traverse access to the snapshot
   directory, and permission to inspect/exec the selected Docker/Podman
   container. Directories must be traversable and HTML/manifests readable by
   the serving user (transport uses directories 0755/files 0644).

The runner pulls the capture image, restores a cache isolated by immutable
image/API/origin, captures and validates, then uses
`client/scripts/publish-snapshots.sh` for SSH/rsync staging. The serving image's
validator is executed in the running container with `--assets-dir
/usr/share/nginx/html` before atomic promotion, including same-artifact retries.
Interrupted uploads or incompatible bundles must not replace `current`.
The runner cache retains current plus two validated archives. Remote retirement
retains current plus two compatible archives, prioritizing the previous release,
and additionally preserves any release held by a live reader's shared manifest
lease. This grace is lease-based, not a fixed time: exit or switching releases
releases the lease, and a subsequent promotion can retire the archive.

| Runtime setting | Default | Purpose |
|---|---|---|
| `PUBLISHER_BACKEND_URL` | `http://backend:8080` | Public API base reachable from the serving container; workflow uses the external HTTPS base |
| `PUBLISHER_ORIGIN` | `https://countrydle.online` | Canonical production origin |
| `PUBLISHER_POLL_SECONDS` | `60` | Reader metadata poll interval, allowed 5–3600 seconds |
| `PUBLISHER_CAPTURE_TIMEOUT` | `45` | Capture-only per-route timeout, allowed 5–300 seconds |

Both Compose configurations keep local capture behind the explicit
`publisher-capture` profile; normal production startup does not enable it.
`npm run publisher:build` is also an explicit standalone capture command, not
an implicit dependency of `npm run build`. Scheduled off-host refresh is the
normal operational path, not manual-only refresh. The entrypoint supervises
Nginx and the reader: loss of either terminates the container. It derives Nginx
resolver addresses from actual `/etc/resolv.conf`, validating IPv4/IPv6 entries
rather than hardcoding Docker's `127.0.0.11` or Podman's address.
The supervisor handles the Nginx base image's default `SIGQUIT`, plus TERM/INT.
It first gracefully stops Nginx, keeping the reader alive until active responses
finish, then stops the reader. Allow sufficient container stop grace for those
requests; exhausted grace can still force termination. Image-publishing CI runs
a native held-response shutdown check against the exact serving image digest.
`/sitemap.xml` comes from FastAPI through Nginx/Vite; `robots.txt` advertises it.

### Editorial workflow

Apply the normal startup migrations before serving the new API. Existing recaps
start unreviewed; source links are not fabricated and historical articles are not
automatically approved. An authenticated administrator opens Blogs, edits the
text/facts/deduction/real source links, and saves. Every edit, regeneration and
explicit revocation clears reviewer attribution and advertising eligibility.
Review requires a substantive sourced past-day article and deliberate
confirmation after personally checking the claims. These are internal safety
checks, not a claimed Google word-count threshold or approval.

The server records the signed-in reviewer's public username and UTC review time.
Both PATCH saves and reviews require `expected_updated_at`: send the exact raw
stored `updated_at` string, including microseconds, not a display-formatted date.
Stale versions return 409 without mutation. Save conflicts retain all draft
fields; explicitly reload (cancelling preserves the draft), inspect the latest
article and deliberately reapply corrections before saving or reviewing.
Regeneration uses compare-and-swap against the original version and atomically
clears review fields even when originally null; a concurrent review/change
cannot be silently overwritten. Slow provider generation holds no database
connection. Every successful content change needs a fresh deliberate review.

Malformed nested facts/quizzes, non-finite browser numbers, unsafe source URLs
and URLs exceeding the normalized limit are rejected before mutation. Incomplete
historical or display-identical quiz answers show an honest unavailable/repair
notice while preserving factual article text and raw editable JSON for admin
repair; no answers or distractors are fabricated. Unknown historical `created_at`
stays null and omits `datePublished` from metadata rather than inventing a date.
Real `updated_at` remains available in metadata and the admin workflow.
Quiz nonblank validation uses the client's display-whitespace set: U+FEFF-only
fields cannot be saved or approved from historical storage. Heading annotations
retain their whole qualified section, including repeated facts; ordinary
unannotated duplicate claims are still removed.
Public recaps retain real source links when recorded and citation-needed markers
in article content. The article view does not display the editorial disclosure
block, editorial notes, or publication/update timestamps. Review controls and
advertising eligibility remain independent of that presentation.

### Explicit inventory and consent

`index.html` retains the publisher ownership meta tag, not an unconditional
AdSense SDK. `public/ads.txt` must match the deployed account. Advertising is
disabled by default and requires all of:

- `VITE_ADSENSE_ENABLED=true` at image/build time.
- `VITE_GOOGLE_ADSENSE_ID` matching the verified publisher
  `ca-pub-3937273134876300`.
- `VITE_ADSENSE_SLOTS`: a JSON object mapping placement names to actual
  account-generated, nonzero ten-digit slot IDs supplied as strings. Available
  names: `about-page-footer`, `how-it-works-footer`, `mode-guide-footer`,
  `explore-hub-footer`, `blog-list-footer`, `countrydle-blog-post-footer`.
  Missing, malformed or unconfigured inventory does not authorize serving.
- A substantive eligible public page and determinate permission from Google's
  Funding Choices / Privacy & messaging service.

Eligible screens are curated public help/guides and loaded substantive Explore
or reviewed journal content. Games, game results/share controls, authentication,
admin/private pages, legal/contact pages, unknown routes, loading/error/empty
screens and unreviewed articles do not load the ad SDK. The journal list cannot
authorize advertising until its loaded content satisfies editorial eligibility.
When an advertising runtime has loaded, route changes and revocation cross a
fresh-document boundary so Google Auto ads cannot linger on an excluded screen.
Check account-level Auto ads formats and placement exclusions before enabling.

Unknown, rejected or unavailable consent does not authorize ad requests.
EEA permission requires a loaded supported TCF state and affirmative Google
vendor/purpose consent; a determinate non-GDPR state is handled separately.
CMP readiness registers the single consent listener independently of a request's
ten-second timeout. Legitimate late readiness recovers automatically without
manual retry or reopening the expired privacy dialog. Readiness failures clear
on recovery; an actual dialog failure remains visible. Failed loading can be
retried, and revocation removes serving permission. Privacy settings are in the
footer, navigation and Cookie Policy; unavailable provider state reports that
no choices were changed.
Old `cookie-consent` localStorage values are not consent. Rybbit remains an
independently configured analytics integration, suppressed only during capture;
verify its deployment-specific collection, retention and legal basis separately.

**Account prerequisite:** In AdSense → Privacy & messaging → European
regulations, configure and publish the message for `countrydle.online`, with
`https://countrydle.online/privacy-policy`, required consent/refusal choices and
languages. Verify a fresh EEA visit, acceptance, refusal, reopening and
revocation with the real account. Google's documented preview URL
`https://countrydle.online/?fc=alwaysshow&fctype=gdpr` requires a published
message. Repository code does not publish a CMP message, validate account
eligibility, submit review or guarantee approval. The private rejection details,
real inventory and account settings must be checked by the operator.

### Verification evidence and remaining limits

The initial integration's offline backend run passed **11,363 tests**, with
165 skipped and eight credential-dependent live Gemini cases deselected
(195.95 seconds). Focused PostgreSQL generation/editorial suites passed 108
tests, including single-slot pools, simultaneous generation, review-clearing
CAS and 409 conflicts. Frontend tests passed 138 cases, including 19 real
React/happyDOM consent cases; publisher tests passed 42. Focused changed-file
lint passed apart from 36 existing `api.ts` `any` errors outside the blog
contract. Node 20 paired serving/capture image builds and Node 22 host production
compilation passed. These are local checks, not evidence of GitHub Action runs.
Full-repository lint still reports 80 errors and 14 warnings in inherited code;
it is not a fully green repository-wide lint gate.

The four follow-up review corrections passed 116 focused backend tests, 152
frontend tests, changed-file lint and paired Node 20 production image builds.
Actual native HTTP rejected display-blank fields with PATCH 422 and historical
review 400 for all four quiz fields; a meaningful repair and deliberate review
returned 200. Native Chromium observed the ten-second privacy failure with zero
subscriptions/ad requests, then eleven-second readiness established one
subscription and one authorized fixture ad request without retry or reopening
the expired dialog. The visible error cleared. A 390-pixel article retained its
warning-bearing population heading beside the repeated claim without overflow.
The exact migrated development frontend/worker configuration, against an
isolated native API, captured 20 routes with no unavailable routes; checked
home/help/policy/Explore/journal/health responses were 200. An unchanged capture
reused its release, and the serving snapshot mount was read-only with no Chromium.
These disposable CMP/SDK fixtures make no real Google requests or impressions.

Actual owned FastAPI/PostgreSQL/HTTP checks exercised source CAS and null
creation reads. Independent Chromium editor tabs exercised save 200/409 with
all ten draft fields retained, reload cancellation, explicit reload/fresh save,
and stale/fresh review 409/200. Native Chromium with disposable intercepted
SDK/CMP fixtures exercised a four-field successful `gdprApplies=false` response,
same-document hash Back preserving the unit, fragment revocation crossing a
document boundary with no SDK in the denied new document, and a visible
pre-mount privacy failure with failed/successful retry. These fixtures make no
Google requests or real impressions and do not verify real account consent.

Actual UID-1000 capture produced 22 readable initial-HTML routes; standalone
reader/Nginx served all 22 with 200. Checks covered partial-quiz notice/raw
preservation, honest null-creation metadata, known-to-null SPA metadata removal,
unknown/private 404, date-alias 308, API and sitemap 200. Real strict-key SSH/rsync
promotion and identical-artifact retry succeeded, including execution of the
validator inside the serving container. Actual Docker DNS `127.0.0.11` carried
API traffic; an injected `10.89.3.1` plus IPv6 nameserver configuration generated
valid Nginx resolver syntax. This does **not** verify an actual Podman engine.

Real wrong-bundle publication was rejected by the deployed container's validator;
an interrupted native rsync transfer left the prior current release unchanged.
Restarting serving still delivered the complete valid artifact. Malformed mandatory
article content returned 503 only for that article; home, help, the journal and
other articles remained 200. Deletion returned 404 before recapture. An authoritative
empty journal delivered useful initial HTML, noindex and no ads. During an actual
API outage, dynamic pages returned 503 after the configured metadata freshness
deadline while static pages and health remained 200; publishing retained 17 static
routes, then recovery restored all 22. Real SSH retirement retained current plus
two compatible archives. Killing either reader or Nginx exited the paired container
with status 1, and both restart checks recovered HTTP 200. Native 390-pixel mobile
and 1440-pixel desktop home checks preserved navigation/globe controls without
horizontal overflow; the mobile quiz repair disclosure retained its raw evidence.

The serving image measured 106,937,330 bytes, contained no Chrome/websocket
dependency, used a read-only artifact mount and observed 46.62 MiB idle memory.
The capture image measured 864,971,144 bytes; observed capture memory was
325.2 MiB at a sample, **not a measured peak**. A 22-route first capture took
35.26 seconds, four changed routes 10.14 seconds and unchanged metadata/UUID
reuse 1.29 seconds without Chrome. These local observations are not production
measurements or capacity guarantees.

Earlier main-branch 1.26.0 mobile/design evidence elsewhere in this README is
historical and separate from this integration. Actual Podman execution,
production deployment, physical devices, live provider credentials, real Google
account/CMP flow and Google's review decision are not verified.
No push, merge or deployment authorization is implied. Operators must configure
the workflow and host prerequisites, curate historical recaps and inspect the
real production surface before requesting review; repository checks cannot
guarantee approval.

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
