import type { Route } from '@playwright/test';
import {
  account, answeredQuestion, ask, expect, expectGuestProgress, expectProgress,
  guess, guessTab, openGame, questionTab, readAccount, readGuest, ready, signIn, test, unresolvedQuestion,
} from './fixtures';

// No route.fulfill, imported stores, fabricated API successes or seeded progress.
// The only failure interception below aborts a browser's sync request. All
// successful questions/guesses/auth/sync/readbacks reach the managed real API.

test('H05 guest answered question → miss → reload → sign in preserves history and syncs once', async ({ page }, testInfo) => {
  const syncs: number[] = [];
  page.on('response', response => {
    if (response.url().endsWith('/api/countrydle/sync') && response.request().method() === 'POST') syncs.push(response.status());
  });
  await openGame(page);
  const answer = await ask(page);
  expect(answer.status()).toBe(200);
  expect(await answer.json()).toMatchObject({ original_question: answeredQuestion, valid: true, answer: true });
  expect(await (await guess(page, 'Germany')).json()).toMatchObject({ guess: 'Germany', answer: false });
  await expectGuestProgress(page, 1, 1);
  const before = await readGuest(page);
  const guestCookies = await page.context().cookies();
  expect(guestCookies.some(cookie => cookie.name.includes('guest') && cookie.httpOnly)).toBe(true);
  await page.reload();
  await ready(page);
  await expectGuestProgress(page, 1, 1);
  expect((await readGuest(page))!.questions.map(question => question.id)).toEqual(before!.questions.map(question => question.id));
  await questionTab(page).click();
  await expect(page.getByText(answeredQuestion, { exact: true }).first()).toBeVisible();
  await guessTab(page).click();
  await expect(page.getByText('Germany', { exact: true }).filter({ visible: true })).toBeVisible();
  await signIn(page, account(testInfo.project.name, 'sync'));
  await expect.poll(async () => (await readAccount(page)).state.questions_asked).toBe(1);
  expectProgress(await readAccount(page), 1, 1);
  expect((await readAccount(page)).questions.map(question => question.id)).toEqual(before!.questions.map(question => question.id));
  await expect.poll(() => readGuest(page)).toBeNull();
  await page.reload();
  await ready(page);
  expectProgress(await readAccount(page), 1, 1);
  await expect(questionTab(page)).toContainText('1/10');
  await expect(guessTab(page)).toContainText('1/3');
  expect(syncs).toEqual([200]);
});

test('H05 normal unresolved provider result consumes neither turn nor history', async ({ page }, testInfo) => {
  await openGame(page);
  const guestBefore = await readAccount(page);
  const guestResponse = await ask(page, unresolvedQuestion);
  expect(guestResponse.status()).toBe(503);
  expectProgress(await readAccount(page), 0, 0);
  expect((await readAccount(page)).state).toEqual(guestBefore.state);
  await expect(questionTab(page)).toContainText('0/10');
  await signIn(page, account(testInfo.project.name, 'unresolved'));
  await ready(page);
  const before = await readAccount(page);
  expectProgress(before, 0, 0);
  const response = await ask(page, unresolvedQuestion);
  // Production's unavailable/unknown semantics, not the global exception
  // fallback's synthetic 200. This traverses planner/fallback/route normally.
  expect(response.status()).toBe(503);
  const after = await readAccount(page);
  expect(after.state).toEqual(before.state);
  expect(after.questions).toEqual(before.questions);
  await expect(questionTab(page)).toContainText('0/10');
  expect((await ask(page)).status()).toBe(200);
  await expect.poll(async () => (await readAccount(page)).state.questions_asked).toBe(1);
  expectProgress(await readAccount(page), 1, 0);
});

test('H05 authenticated hard reload restores state and logout does not leak account progress to a guest', async ({ page }, testInfo) => {
  const username = account(testInfo.project.name, 'auth');
  await signIn(page, username);
  await ready(page);
  expect((await ask(page)).status()).toBe(200);
  await guess(page, 'Germany');
  const before = await readAccount(page);
  expectProgress(before, 1, 1);
  await page.reload();
  await ready(page);
  expectProgress(await readAccount(page), 1, 1);
  await expect(questionTab(page)).toContainText('1/10');
  const logout = page.getByRole('button', { name: 'Logout', exact: true });
  if (!await logout.isVisible()) await page.getByRole('button', { name: 'Navigation menu', exact: true }).click();
  const response = page.waitForResponse(response => response.url().endsWith('/api/logout') && response.request().method() === 'POST');
  await logout.click();
  expect((await response).status()).toBe(200);
  await expect.poll(async () => page.evaluate(() => localStorage.getItem('user'))).toBeNull();
  const guest = await readAccount(page);
  expect(guest.user).toBeNull();
  expectProgress(guest, 0, 0);
  await expect(questionTab(page)).toContainText('0/10');
  await expect(guessTab(page)).toContainText('0/3');
  await page.reload();
  await ready(page);
  expectProgress(await readAccount(page), 0, 0);
  await signIn(page, username);
  await ready(page);
  expectProgress(await readAccount(page), 1, 1);
  expect((await readAccount(page)).questions.map(question => question.id)).toEqual(before.questions.map(question => question.id));
});

for (const won of [true, false]) {
  test(`H05 final ${won ? 'winning' : 'losing'} guess, result and dismissal survive reload`, async ({ page, manifest }, testInfo) => {
    expect(manifest.serverDigest).toBe(process.env.E2E_SERVER_DIGEST);
    await openGame(page);
    expect((await ask(page)).status()).toBe(200);
    await guess(page, 'Germany');
    await guess(page, 'France');
    await guess(page, won ? 'Poland' : 'Italy');
    const result = page.getByRole('dialog', { name: 'Daily Results', exact: true });
    await expect(result).toBeVisible();
    await expect(result.getByText(won ? 'Solved' : 'Game Over', { exact: true })).toBeVisible();
    await expect(result.getByText('Poland', { exact: true }).first()).toBeVisible();
    await testInfo.attach(`${testInfo.project.name}-${won ? 'win' : 'loss'}`, { body: await page.screenshot(), contentType: 'image/png' });
    const snapshot = await readGuest(page);
    expect(snapshot!.state).toMatchObject({ questions_asked: 1, remaining_questions: 9, guesses_made: 3, remaining_guesses: 0, is_game_over: true, won });
    expect(snapshot!.guesses.map(guess => guess.answer)).toEqual([false, false, won]);
    await result.getByRole('button', { name: 'Close result modal', exact: true }).click();
    await expect(result).toBeHidden();
    await expect(page.getByRole('button', { name: 'View Result Card', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'View Result Card', exact: true }).click();
    await expect(result).toBeVisible();
    await page.reload();
    await expect(result).toBeVisible();
    await expect(result.getByText(won ? 'Solved' : 'Game Over', { exact: true })).toBeVisible();
    // Read the final state back from actual account storage, not just localStorage.
    await signIn(page, account(testInfo.project.name, won ? 'win' : 'loss'));
    await expect.poll(async () => (await readAccount(page)).state.is_game_over).toBe(true);
    const stored = await readAccount(page);
    expect(stored.state).toMatchObject({ questions_asked: 1, guesses_made: 3, remaining_guesses: 0, is_game_over: true, won });
    expect(stored.guesses.map(guess => [guess.guess, guess.answer])).toEqual([
      ['Germany', false], ['France', false], [won ? 'Poland' : 'Italy', won],
    ]);
    expect(stored.questions.map(question => question.original_question)).toEqual([answeredQuestion]);
    if (won) expect(stored.state.points).toBeGreaterThan(0);
    else expect(stored.state.points).toBe(0);
  });
}

test('H05 expired signed session rejects the action and reauthentication recovers account history', async ({ page, manifest, baseURL }, testInfo) => {
  const username = account(testInfo.project.name, 'expired');
  await signIn(page, username);
  await ready(page);
  expect((await ask(page)).status()).toBe(200);
  await guess(page, 'Germany');
  const before = await readAccount(page);
  expectProgress(before, 1, 1);
  // Let the successful guess's state refresh finish before expiring the cookie;
  // otherwise that background GET can redirect before the action under test.
  await questionTab(page).click();
  await ready(page);
  await page.context().addCookies([{ name: 'access_token', value: manifest.expiredTokens[username], url: baseURL!, httpOnly: true, sameSite: 'Lax' }]);
  const rejected = await ask(page);
  expect(rejected.status()).toBe(401);
  await expect(page).toHaveURL(/\/login$/);
  await signIn(page, username);
  await ready(page);
  const restored = await readAccount(page);
  expectProgress(restored, 1, 1);
  expect(restored.questions.map(question => question.id)).toEqual(before.questions.map(question => question.id));
  expect(restored.guesses.map(guess => guess.id)).toEqual(before.guesses.map(guess => guess.id));
  await page.reload();
  await ready(page);
  expectProgress(await readAccount(page), 1, 1);
});

test('H05 browser-local failed sync retains guest progress and later real sync recovers exactly once', async ({ page }, testInfo) => {
  await openGame(page);
  expect((await ask(page)).status()).toBe(200);
  await guess(page, 'Germany');
  await expectGuestProgress(page, 1, 1);
  const before = await readGuest(page);
  let failures = 0;
  const failure = async (route: Route) => {
    if (route.request().method() === 'POST') { failures++; await route.abort('failed'); }
    else await route.continue();
  };
  await page.route('**/api/countrydle/sync', failure);
  await signIn(page, account(testInfo.project.name, 'recovery'));
  await expect.poll(() => failures).toBeGreaterThan(0);
  expectProgress(await readGuest(page), 1, 1);
  expectProgress(await readAccount(page), 0, 0);
  // Reload with the outage still in place: recoverable browser history must not
  // be discarded because account hydration succeeded but the transfer failed.
  const previousFailures = failures;
  await page.reload();
  await expect.poll(() => failures).toBeGreaterThan(previousFailures);
  expectProgress(await readGuest(page), 1, 1);
  await page.unroute('**/api/countrydle/sync', failure);
  const successes: number[] = [];
  page.on('response', response => {
    if (response.url().endsWith('/api/countrydle/sync') && response.request().method() === 'POST') successes.push(response.status());
  });
  await page.reload();
  await ready(page);
  await expect.poll(async () => (await readAccount(page)).state.questions_asked).toBe(1);
  expectProgress(await readAccount(page), 1, 1);
  expect((await readAccount(page)).questions.map(question => question.id)).toEqual(before!.questions.map(question => question.id));
  await expect.poll(() => readGuest(page)).toBeNull();
  await page.reload();
  await ready(page);
  expectProgress(await readAccount(page), 1, 1);
  expect(successes).toEqual([200]);
});

test('named factual explanations appear only after the game ends; warnings remain target-free', async ({ page }, testInfo) => {
  await openGame(page);
  const warning = await ask(page, unresolvedQuestion);
  expect(warning.status()).toBe(503);
  expect(await warning.text()).not.toMatch(/\b(?:Poland|Warsaw)\b/i);
  await expect(page.getByRole('alert').filter({ hasText: /question/i }).first()).toBeVisible();
  expect((await page.getByRole('alert').allTextContents()).join(' ')).not.toMatch(/\b(?:Poland|Warsaw)\b/i);
  expectProgress(await readAccount(page), 0, 0);

  const answered = await ask(page);
  expect(answered.status()).toBe(200);
  const activeQuestion = await answered.json();
  expect(activeQuestion).toMatchObject({ valid: true, answer: true });
  expect(activeQuestion.explanation).toBeFalsy();
  expect(JSON.stringify(activeQuestion)).not.toMatch(/\bPoland\b/i);
  await expectGuestProgress(page, 1, 0);
  await expect(page.getByRole('list', { name: 'Question conversation', exact: true }).getByText(/Poland.*Europe/)).toHaveCount(0);

  await guess(page, 'Poland');
  const stateResponse = await page.request.get('/api/countrydle/state');
  const terminal = await stateResponse.json();
  expect(terminal.state).toMatchObject({ is_game_over: true, won: true });
  expect(terminal.questions[0].explanation).toMatch(/\bPoland\b/);
  expect(terminal.questions[0].explanation).toMatch(/\bEurope\b/);
  await page.getByRole('tab', { name: /Question History/ }).click();
  const history = page.getByRole('list', { name: 'Question History', exact: true });
  await history.locator('summary').filter({ hasText: answeredQuestion }).click();
  await expect(history.getByText(/Poland.*Europe/)).toBeVisible();
  await testInfo.attach('named-post-game-template-explanation', { body: await page.screenshot(), contentType: 'image/png' });

  await page.reload();
  const restored = await (await page.request.get('/api/countrydle/state')).json();
  expect(restored.questions[0].explanation).toMatch(/\bPoland\b/);
  expect(restored.questions[0].explanation).toMatch(/\bEurope\b/);
});
