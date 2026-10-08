import { expect, test, type Locator, type Page } from '@playwright/test';

// H09 semantic contract. Fixtures replace HTTP responses only: production pages,
// stores, map handlers and dialog components execute unchanged in the browser.
// This is UI accessibility proof, not backend gameplay-integrity evidence.
const modes = [
  { path: '/game', api: '/countrydle', pool: 'countries', storage: 'country', entity: 'Poland', field: 'country' },
  { path: '/powiaty', api: '/powiatdle', pool: 'powiaty', storage: 'powiaty', entity: 'powiat krakowski', field: 'powiat' },
  { path: '/wojewodztwa', api: '/wojewodztwodle', pool: 'wojewodztwa', storage: 'wojewodztwa', entity: 'małopolskie', field: 'wojewodztwo' },
  { path: '/us-states', api: '/us_statedle', pool: 'states', storage: 'us_states', entity: 'Texas', field: 'us_state' },
  { path: '/europe', api: '/continental/europe', pool: 'countries', storage: 'europe', entity: 'Poland', field: 'country' },
  { path: '/asia', api: '/continental/asia', pool: 'countries', storage: 'asia', entity: 'Japan', field: 'country' },
  { path: '/africa', api: '/continental/africa', pool: 'countries', storage: 'africa', entity: 'Egypt', field: 'country' },
  { path: '/americas', api: '/continental/americas', pool: 'countries', storage: 'americas', entity: 'Brazil', field: 'country' },
] as const;
const flag = { path: '/flagdle', api: '/flagdle', pool: 'countries', storage: 'flagdle', entity: 'Poland', field: 'country' } as const;
type Mode = (typeof modes)[number] | typeof flag;
const date = '2026-10-06';
const country = { id: 1, name: 'Poland', iso2: 'PL', iso3: 'POL', code: 'PL' };

async function fixture(page: Page, mode: Mode, completed?: 'won' | 'lost', firstVisit = false) {
  const entity = { ...country, name: mode.entity, nazwa: mode.entity, code: mode.storage === 'us_states' ? 'TX' : 'PL' };
  const state = {
    questions_asked: 0, guesses_made: completed ? 1 : 0,
    remaining_questions: 5, remaining_guesses: completed ? 0 : 2,
    is_game_over: Boolean(completed), won: completed === 'won', points: completed === 'won' ? 1000 : 0,
    revealed_stage: completed ? 12 : 1,
  };
  const frontendOrigin = new URL(test.info().project.use.baseURL!).origin;
  await page.route('**/*', route => {
    if (new URL(route.request().url()).origin !== frontendOrigin) return route.abort();
    return route.continue();
  });
  await page.addInitScript(({ key, snapshot, firstVisit }) => {
    localStorage.clear();
    if (!firstVisit) {
      localStorage.setItem('countrydle_guide_seen', 'true');
      localStorage.setItem('flagdle_guide_seen', 'true');
    }
    if (snapshot) localStorage.setItem(key, JSON.stringify(snapshot));
  }, {
    key: `guess_game_${mode.storage}_${date}`, firstVisit,
    snapshot: completed ? { state, questions: [], guesses: [], correctEntity: entity } : null,
  });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, '');
    // No fixture test may accidentally submit a mutation to a real provider/database.
    if (route.request().method() !== 'GET') return route.fulfill({ status: 405, json: { detail: 'Fixture blocks writes' } });
    if (path === `${mode.api}/state`) return route.fulfill({ json: {
      date, user: null, state, questions: [], guesses: [],
      [mode.field]: completed ? entity : null, flag_asset_url: '/flags/pl.svg',
    } });
    if (path === `${mode.api}/${mode.pool}`) return route.fulfill({ json: [entity] });
    if (path === '/time') return route.fulfill({ json: {
      server_time: `${date}T12:00:00Z`, next_game_at: '2026-10-07T00:00:00Z',
    } });
    return route.fulfill({ status: 404, json: { detail: 'No accessibility fixture for this request' } });
  });
  await page.goto(mode.path, { waitUntil: 'domcontentloaded' });
}

async function inside(dialog: Locator) {
  await expect.poll(() => dialog.evaluate(node => node.contains(document.activeElement))).toBe(true);
}

async function trapped(page: Page, dialog: Locator) {
  await expect(dialog).toBeVisible();
  await inside(dialog);
  // Traverse beyond the full current focus order in both directions. This also
  // includes links/disclosures/tabpanel focus targets, not just close buttons.
  const count = await dialog.evaluate(node => [...node.querySelectorAll<HTMLElement>(
    'button, a[href], input, select, textarea, summary, [tabindex]',
  )].filter(el => el.tabIndex >= 0 && !el.matches(':disabled') && el.getClientRects().length > 0).length);
  for (const key of ['Tab', 'Shift+Tab']) {
    for (let step = 0; step < count + 2; step++) {
      await page.keyboard.press(key);
      await inside(dialog);
    }
  }
}

async function keyboardActivate(locator: Locator) {
  await locator.focus();
  await locator.press('Enter');
}

async function selectFirstEntity(page: Page, entity: string) {
  const region = page.getByRole('region', { name: 'Entity markings', exact: true });
  const select = region.getByRole('combobox', { name: 'Entity', exact: true });
  await select.focus();
  // Fixture has exactly one eligible entity: no pointer or store injection.
  await select.press('Home');
  await select.press('ArrowDown');
  await select.press('Enter');
  await expect(select.locator('option:checked')).toHaveText(entity);
  return region;
}

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test.describe(`H09 ${viewport.width}px`, () => {
    test.use({ viewport });

    for (const mode of modes) {
      test(`${mode.path}: keyboard candidate, excluded and removal share real map state`, async ({ page }) => {
        await fixture(page, mode);
        // The mobile notebook must not hide the keyboard map alternative.
        const back = page.getByRole('button', { name: 'Back to map', exact: true });
        if (await back.isVisible()) await keyboardActivate(back);
        const region = await selectFirstEntity(page, mode.entity);
        const candidate = region.getByRole('button', { name: 'Mark candidate', exact: true });
        const excluded = region.getByRole('button', { name: 'Mark excluded', exact: true });
        const remove = region.getByRole('button', { name: 'Remove marking', exact: true });
        const status = region.getByRole('status', { name: 'Marking status', exact: true });
        await keyboardActivate(candidate);
        await expect(candidate).toHaveAttribute('aria-pressed', 'true');
        await expect(excluded).toHaveAttribute('aria-pressed', 'false');
        await expect(status).toContainText(mode.entity);
        await expect(status).toContainText(/candidate/i);
        await keyboardActivate(remove);
        await expect(candidate).toHaveAttribute('aria-pressed', 'false');
        await expect(status).toContainText(/unmarked/i);
        await keyboardActivate(candidate);
        await expect(candidate).toHaveAttribute('aria-pressed', 'true');
        // Existing clear-all must affect the new controls too: this prevents a
        // second fake marking state from satisfying the keyboard-only assertions.
        await keyboardActivate(page.getByRole('button', { name: 'Clear all map markings', exact: true }));
        await expect(candidate).toHaveAttribute('aria-pressed', 'false');
        await expect(status).toContainText(/unmarked/i);
        await keyboardActivate(excluded);
        await expect(excluded).toHaveAttribute('aria-pressed', 'true');
        await expect(candidate).toHaveAttribute('aria-pressed', 'false');
        await expect(status).toContainText(/excluded/i);
        await keyboardActivate(remove);
        await expect(excluded).toHaveAttribute('aria-pressed', 'false');
        await expect(status).toContainText(/unmarked/i);
        await expect(remove).toBeDisabled();
      });

      test(`${mode.path}: guide traps focus, Escape and close restore the opener`, async ({ page }) => {
        await fixture(page, mode);
        const trigger = page.getByRole('button', { name: /rules.*guide|how to play.*(?:guide|info)/i });
        await keyboardActivate(trigger);
        const dialog = page.getByRole('dialog', { name: /rules.*guide|how to play.*(?:guide|info)/i });
        await trapped(page, dialog);
        await page.keyboard.press('Escape');
        await expect(dialog).toBeHidden();
        await expect(trigger).toBeFocused();
        await trigger.press('Enter');
        await inside(dialog);
        await keyboardActivate(dialog.getByRole('button', { name: 'Close', exact: true }));
        await expect(dialog).toBeHidden();
        await expect(trigger).toBeFocused();
      });
    }

    test('automatic guide places focus inside and restores a meaningful guide fallback', async ({ page }) => {
      await fixture(page, modes[0], undefined, true);
      const dialog = page.getByRole('dialog', { name: /rules.*guide|how to play.*(?:guide|info)/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(page.getByRole('button', { name: /rules.*guide|how to play.*(?:guide|info)/i })).toBeFocused();
    });

    for (const mode of [...modes, flag]) {
      for (const outcome of ['won', 'lost'] as const) {
        test(`${mode.path}: terminal ${outcome} restores an operable result-dialog opener`, async ({ page }) => {
          await fixture(page, mode, outcome);
          const dialog = page.getByRole('dialog');
          await trapped(page, dialog);
          await expect(dialog).toHaveAccessibleName(/\S/);
          await page.keyboard.press('Escape');
          await expect(dialog).toBeHidden();
          await expect(page.locator(':focus')).toHaveRole('button');
          await expect(page.locator(':focus')).toHaveAccessibleName(/\S/);
          const opener = await page.locator(':focus').elementHandle();
          expect(opener).not.toBeNull();
          await opener!.press('Enter');
          await inside(dialog);
          await keyboardActivate(dialog.getByRole('button', { name: /^(close|close result modal)$/i }));
          await expect(dialog).toBeHidden();
          await expect.poll(() => opener!.evaluate(node => node === document.activeElement)).toBe(true);
        });
      }
    }

    test('Flagdle guide follows the same focus contract', async ({ page }) => {
      await fixture(page, flag);
      const trigger = page.getByRole('button', { name: /how to play flagdle/i });
      await keyboardActivate(trigger);
      const dialog = page.getByRole('dialog', { name: /how to play flagdle/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
    });

    test('390px notebook/map switching preserves markings and keyboard controls', async ({ page }) => {
      test.skip(viewport.width !== 390, 'Narrow-screen notebook contract');
      await fixture(page, modes[0]);
      const back = page.getByRole('button', { name: 'Back to map', exact: true });
      if (await back.isVisible()) await keyboardActivate(back);
      const region = await selectFirstEntity(page, 'Poland');
      await keyboardActivate(region.getByRole('button', { name: 'Mark candidate', exact: true }));
      await keyboardActivate(page.getByRole('button', { name: /^Ask\s/ }));
      await expect(back).toBeVisible();
      await keyboardActivate(back);
      await expect(region.getByRole('button', { name: 'Mark candidate', exact: true })).toHaveAttribute('aria-pressed', 'true');
      await keyboardActivate(region.getByRole('button', { name: 'Remove marking', exact: true }));
      await expect(region.getByRole('status', { name: 'Marking status', exact: true })).toContainText(/unmarked/i);
    });
  });
}

async function friendFixture(page: Page, phase: 'thinking' | 'answering' | 'finished', mode = 'countrydle') {
  await fixture(page, modes[0]);
  const player = (id: string, name: string) => ({
    id, name, ready: true, connected: true, guess_count: 0, question_count: 0,
    rematch_ready: false, timeout_count: 0,
  });
  const question = {
    id: 'question-1', ordinal: 1, type: 'question', player_id: 'friend', subject_id: 'self',
    question: 'Is it in Europe?', entity: null, answer: null, correct: null, revision: 1,
    created_at: `${date}T12:00:00Z`, revisions: [],
  };
  const snapshot = {
    id: 'accessibility-room', invite_code: 'H09TEST', mode, version: 1,
    status: phase === 'finished' ? 'finished' : 'active', phase, you: 'self',
    players: [player('self', 'Keyboard player'), player('friend', 'Friend')],
    own_secret: { id: '1', name: 'Poland', code: 'PL' },
    active_player_id: phase === 'answering' ? 'friend' : 'self',
    pending_question_id: phase === 'answering' ? question.id : null,
    pending_winner_id: null, winner_id: phase === 'finished' ? 'self' : null,
    result: phase === 'finished' ? 'solved' : null, draw_offer_by: null, turn: 1,
    deadline: null, history: phase === 'answering' ? [question] : [],
    history_has_more: false, guidance: [], rematch_id: null, rematch_code: null,
    reveals: phase === 'finished' ? [
      { player_id: 'self', entity: { id: '1', name: 'Poland', code: 'PL' } },
      { player_id: 'friend', entity: { id: '2', name: 'Germany', code: 'DE' } },
    ] : null,
  };
  await page.route('**/api/friend-matches/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') return route.fulfill({ status: 405, json: {} });
    if (path.endsWith('/invites/H09TEST')) return route.fulfill({ json: {
      id: snapshot.id, invite_code: snapshot.invite_code, mode, status: snapshot.status,
      players: snapshot.players, full: true,
    } });
    if (path.endsWith('/entities')) return route.fulfill({ json: { entities: [
      { id: '1', name: 'Poland', code: 'PL' }, { id: '2', name: 'Germany', code: 'DE' },
    ] } });
    if (path.endsWith('/accessibility-room')) return route.fulfill({ json: snapshot });
    return route.fulfill({ status: 404, json: {} });
  });
  // Prevent polling transport from reaching a real duel service. HTTP snapshots
  // remain the actual production recovery path.
  await page.routeWebSocket('**/friend-matches/**/ws', socket => socket.close());
  await page.goto('/duel/H09TEST', { waitUntil: 'domcontentloaded' });
}

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test.describe(`H09 friend ${viewport.width}px`, () => {
    test.use({ viewport });
    test('friend private markings share clear-all state without changing daily marks', async ({ page }) => {
      await friendFixture(page, 'thinking');
      const back = page.getByRole('button', { name: 'Back to map', exact: true });
      if (await back.isVisible()) await keyboardActivate(back);
      const region = page.getByRole('region', { name: 'Entity markings', exact: true });
      const select = region.getByRole('combobox', { name: 'Entity', exact: true });
      await select.focus();
      await select.press('Home');
      await select.press('ArrowDown');
      await select.press('Enter');
      const candidate = region.getByRole('button', { name: 'Mark candidate', exact: true });
      await keyboardActivate(candidate);
      await expect(candidate).toHaveAttribute('aria-pressed', 'true');
      await keyboardActivate(page.getByRole('button', { name: 'Clear all map markings', exact: true }));
      await expect(candidate).toHaveAttribute('aria-pressed', 'false');
      await keyboardActivate(region.getByRole('button', { name: 'Mark excluded', exact: true }));
      await expect(region.getByRole('status', { name: 'Marking status', exact: true })).toContainText(/excluded/i);
      await keyboardActivate(region.getByRole('button', { name: 'Remove marking', exact: true }));
      await expect(region.getByRole('status', { name: 'Marking status', exact: true })).toContainText(/unmarked/i);
      await page.goto('/game', { waitUntil: 'domcontentloaded' });
      const daily = page.getByRole('region', { name: 'Entity markings', exact: true });
      await expect(daily.getByRole('button', { name: 'Mark candidate', exact: true })).toHaveAttribute('aria-pressed', 'false');
    });

    test('friend entry rules also name, trap and restore their opener', async ({ page }) => {
      await fixture(page, modes[0]);
      await page.goto('/friends', { waitUntil: 'domcontentloaded' });
      const trigger = page.getByRole('button', { name: /^(how to play|guide)$/i });
      await keyboardActivate(trigger);
      const dialog = page.getByRole('dialog', { name: /how to play/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
    });

    test('friend rules name, trap, Escape and restore their opener', async ({ page }) => {
      await friendFixture(page, 'thinking');
      const trigger = page.getByRole('button', { name: /^(how to play|guide)$/i });
      await keyboardActivate(trigger);
      const dialog = page.getByRole('dialog', { name: /how to play/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
    });

    test('friend result has a name, traps focus and restores Result after Escape', async ({ page }) => {
      await friendFixture(page, 'finished');
      const dialog = page.getByRole('dialog', { name: /duel results/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      const trigger = page.getByRole('button', { name: 'Result', exact: true });
      await expect(trigger).toBeFocused();
      await trigger.press('Enter');
      await inside(dialog);
      await keyboardActivate(dialog.getByRole('button', { name: /close modal and explore map/i }));
      await expect(dialog).toBeHidden();
      await expect(trigger).toBeFocused();
    });

    test('required friend answer traps focus and Escape cannot discard the turn', async ({ page }) => {
      await friendFixture(page, 'answering');
      const dialog = page.getByRole('dialog', { name: /is it in europe/i });
      await trapped(page, dialog);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeVisible();
      await inside(dialog);
    });
  });
}
