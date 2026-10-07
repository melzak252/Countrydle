import { expect, test as base, type Page, type Response } from '@playwright/test';

export const answeredQuestion = 'Is it in Europe?';
export const unresolvedQuestion = 'Did its prime minister eat an apple at 09:17 today?';
export const password = 'browser-only-disposable-password';
export interface Progress {
  state: { questions_asked: number; remaining_questions: number; guesses_made: number; remaining_guesses: number; won: boolean; is_game_over: boolean; points?: number };
  questions: { id: number; original_question: string; valid: boolean; answer: boolean | null; context?: string }[];
  guesses: { id: number; guess: string; answer: boolean }[];
  date: string;
  user?: { username: string } | null;
}
interface Manifest {
  revision: string; serverDigest: string; clientDigest: string; clientVersion: string; serverVersion: string;
  database: string; schema: string; provider: string; factsDigest: string; expiredTokens: Record<string, string>;
}

export const test = base.extend<{ manifest: Manifest }>({
  manifest: [async ({ page, baseURL }, use, testInfo) => {
    if (!baseURL) throw new Error('Gameplay requires the managed Playwright baseURL');
    const local = new URL(baseURL).origin;
    // Browser-local failure only for unrelated external assets/tracking. Every
    // successful API response below comes from the actual managed FastAPI app.
    await page.route('**/*', route => new URL(route.request().url()).origin === local
      ? route.continue() : route.abort('blockedbyclient'));
    await page.addInitScript(() => {
      // Preferences only: never install auth/game state or call a Zustand store.
      localStorage.setItem('countrydle_guide_seen', 'true');
      localStorage.setItem('flagdle_guide_seen', 'true');
      localStorage.setItem('i18nextLng', 'en');
    });
    const response = await page.request.get('/api/__e2e__/revision');
    expect(response.status()).toBe(200);
    const manifest = await response.json() as Manifest;
    expect(manifest).toMatchObject({
      revision: process.env.E2E_REVISION, serverDigest: process.env.E2E_SERVER_DIGEST,
      clientDigest: process.env.E2E_CLIENT_DIGEST, clientVersion: process.env.E2E_CLIENT_VERSION,
      schema: process.env.E2E_SCHEMA, database: 'countrydle_e2e', provider: 'offline-unresolved',
    });
    const version = await page.request.get('/api/version');
    expect(await version.json()).toEqual({ version: manifest.serverVersion });
    expect(manifest.serverVersion).toBe(manifest.clientVersion);
    await testInfo.attach('same-revision-real-api', { body: JSON.stringify({ ...manifest, expiredTokens: undefined }, null, 2), contentType: 'application/json' });
    await use(manifest);
  }, { auto: true }],
});
export { expect };

export function account(project: string, scenario: string) { return `e2e_${project}_${scenario}`; }
export function composer(page: Page) { return page.getByRole('region', { name: 'Game action composer', exact: true }); }
export function questionTab(page: Page) { return page.getByRole('group', { name: 'Choose question or guess', exact: true }).getByRole('button', { name: /^(?:Questions|Ask)\b/ }); }
export function guessTab(page: Page) { return page.getByRole('group', { name: 'Choose question or guess', exact: true }).getByRole('button', { name: /^(?:Guesses|Guess)\b/ }); }
export async function ready(page: Page) {
  await expect(composer(page)).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Yes-or-no question', exact: true })).toBeEnabled();
}
export async function openGame(page: Page) { await page.goto('/game'); await ready(page); }
export async function signIn(page: Page, username: string) {
  await page.goto('/login');
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  const response = page.waitForResponse(response => response.url().endsWith('/api/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(page).toHaveURL(/\/game$/);
}
export async function ask(page: Page, question = answeredQuestion): Promise<Response> {
  await questionTab(page).click();
  await page.getByRole('textbox', { name: 'Yes-or-no question', exact: true }).fill(question);
  const response = page.waitForResponse(response => response.url().endsWith('/api/countrydle/question') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Ask question', exact: true }).click();
  return response;
}
export async function guess(page: Page, name: string): Promise<Response> {
  await guessTab(page).click();
  const input = page.getByRole('combobox', { name: 'Search for a location', exact: true });
  await expect(input).toBeEnabled();
  await input.fill(name);
  const response = page.waitForResponse(response => response.url().endsWith('/api/countrydle/guess') && response.request().method() === 'POST');
  await input.press('Enter');
  const result = await response;
  expect(result.status()).toBe(200);
  return result;
}
export async function readAccount(page: Page): Promise<Progress> {
  const response = await page.request.get('/api/countrydle/state');
  expect(response.status()).toBe(200);
  return await response.json() as Progress;
}
export async function readGuest(page: Page): Promise<Progress | null> {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).find(key => /^guess_game_country_\d{4}-\d{2}-\d{2}$/.test(key));
    return key ? JSON.parse(localStorage.getItem(key)!) : null;
  }) as Promise<Progress | null>;
}
export function expectProgress(progress: Progress | null, questions: number, guesses: number) {
  expect(progress).not.toBeNull();
  expect(progress!.state).toMatchObject({ questions_asked: questions, remaining_questions: 10 - questions, guesses_made: guesses, remaining_guesses: 3 - guesses });
  expect(progress!.questions.map(question => [question.original_question, question.valid, question.answer])).toEqual(questions ? [[answeredQuestion, true, true]] : []);
  expect(progress!.guesses.map(guess => [guess.guess, guess.answer])).toEqual(guesses ? [['Germany', false]] : []);
}
export async function expectGuestProgress(page: Page, questions: number, guesses: number) {
  await expect.poll(async () => {
    const snapshot = await readGuest(page);
    return [snapshot?.state.questions_asked, snapshot?.state.guesses_made];
  }).toEqual([questions, guesses]);
  expectProgress(await readGuest(page), questions, guesses);
  await expect(questionTab(page)).toContainText(`${questions}/10`);
  await expect(guessTab(page)).toContainText(`${guesses}/3`);
}
