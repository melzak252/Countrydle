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
Valid explanations are not mounted until the game is over; invalid-question
feedback is available immediately. Post-game answer reports retain their mode and
question identifiers. `QuestionInput.tsx` and `GuessInput.tsx` supply the shared forms;
`GameActionComposer.tsx` hosts the active form in the chat footer.

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

## Mobile layout

- Daily map games use a full-width, 44px status row immediately below the app
  header, with question count, guess count, and labelled `Guide` action sharing
  equal-width sections. It remains visible with either the map or notebook open.
  Active duels use two rows to retain player counts, countdown, and secret controls.
- Daily map games and friend duels open a full-height action panel on phones,
  filling the game area below the status row. `Map` collapses the notebook;
  `Ask`/`Guess` restores the corresponding history and input.
- Opening or switching histories scrolls to the newest response or guess. History
  scrolls independently above the pinned composer; manual scrolling remains
  unchanged until a new entry arrives or the selected history changes.
- The shared fullscreen shell tracks `visualViewport` through `--app-height`,
  accounting for browser chrome and reduced keyboard space. At 560px viewport
  height or less on phones, quick-question suggestions hide to leave room for the input
  and history. Expanded active duels retain their turn status and countdown;
  at reduced heights, `Map` moves into the status row and the redundant notebook
  heading and optional composer hint hide so the input stays visible.
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

## Advertising consent and public discovery

`main.tsx` is the only AdSense loader. Set `VITE_GOOGLE_ADSENSE_ID` when building
the frontend; without it, no AdSense script or account meta tag is added. Keep
`public/ads.txt` aligned with that publisher account. Do not add another AdSense
tag to `index.html`.

Advertising consent is managed by Google's certified Privacy & messaging CMP,
not by the former `cookie-consent` localStorage banner. Existing values of that
old key are not treated as consent. `PrivacySettingsButton.tsx` invokes Google's
supported callback queue and `showRevocationMessage()` API. It is available in
the footer, desktop More menu, mobile menu, and Cookie Policy, including access
from fullscreen games whose footer is hidden. If Google's API is unavailable,
the button reports that no choices were changed.

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
