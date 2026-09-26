## Daily game question chat

`src/components/QuestionChat.tsx` renders the shared conversation for the world,
continental, US state, powiat, and voivodeship game pages. Pages provide questions
in chronological order and retain ownership of scrolling and game state.
Player questions appear on the right; replies and answer status appear on the left.
Valid explanations are not mounted until the game is over; invalid-question
feedback is available immediately. Post-game answer reports retain their mode and
question identifiers. `QuestionInput.tsx` supplies the shared rounded composer.

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
