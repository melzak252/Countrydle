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

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

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
