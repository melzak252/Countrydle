import { defineConfig } from '@playwright/test';
import { createHash, randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const client = dirname(fileURLToPath(import.meta.url));
const root = resolve(client, '..');
function digest(directory: string, backendOnly = false): string {
  const files: string[] = [];
  function visit(current: string) {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (entry.name === '__pycache__' || (backendOnly && entry.name === 'tests')) continue;
      const path = join(current, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (entry.isFile() && (!backendOnly || entry.name.endsWith('.py') || entry.name.endsWith('.sql'))) files.push(path);
    }
  }
  visit(directory);
  const hash = createHash('sha256');
  for (const path of files.sort()) {
    hash.update(relative(directory, path).replaceAll('\\', '/') + '\0');
    hash.update(readFileSync(path));
    hash.update('\0');
  }
  return hash.digest('hex');
}
function port(name: string, fallback: number) {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isInteger(value) || value < 1024 || value > 65535 || [8080, 8086, 5179].includes(value)) {
    throw new Error(`${name} must be a dedicated E2E port, not an existing preview port`);
  }
  return value;
}
const webPort = port('E2E_WEB_PORT', 5181);
const apiPort = port('E2E_API_PORT', 8087);
if (apiPort === webPort) throw new Error('E2E HTTP API and frontend need separate ports');
if (!process.env.E2E_DATABASE_URL) {
  throw new Error('Set E2E_DATABASE_URL=postgresql+asyncpg://e2e:<disposable-password>@127.0.0.1:<port>/countrydle_e2e; never use the root .env');
}
const schema = process.env.E2E_SCHEMA ?? `countrydle_e2e_${randomBytes(8).toString('hex')}`;
if (!/^countrydle_e2e_[0-9a-f]{16}$/.test(schema)) throw new Error('E2E_SCHEMA must identify a fresh test-only schema');
const version = JSON.parse(readFileSync(join(client, 'package.json'), 'utf8')).version as string;
const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const serverDigest = digest(join(root, 'server'), true);
const clientDigest = digest(join(client, 'src'));
const baseURL = `http://127.0.0.1:${webPort}`;
const apiURL = `http://127.0.0.1:${apiPort}`;
const env = {
  E2E_DATABASE_URL: process.env.E2E_DATABASE_URL,
  E2E_SCHEMA: schema, E2E_WEB_PORT: String(webPort), E2E_API_PORT: String(apiPort),
  E2E_REVISION: revision, E2E_SERVER_DIGEST: serverDigest, E2E_CLIENT_DIGEST: clientDigest,
  E2E_CLIENT_VERSION: version, PYTHON_DOTENV_DISABLED: '1',
};
// Tests and webServer processes consume one manifest from this configuration load.
Object.assign(process.env, env);
const python = process.env.E2E_PYTHON ?? 'python3';
if (!/^[a-zA-Z0-9_./-]+$/.test(python)) throw new Error('E2E_PYTHON must be an executable path without shell metacharacters');

export default defineConfig({
  testDir: './e2e',
  testMatch: ['gameplay.spec.ts', 'accessibility.spec.ts'],
  fullyParallel: false,
  workers: 1,
  retries: 0, // Each run owns unique identities; never reuse mutated fixtures in a retry.
  timeout: 45_000,
  expect: { timeout: 10_000 },
  forbidOnly: Boolean(process.env.CI),
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL, locale: 'en-US', timezoneId: 'UTC', serviceWorkers: 'block', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    {
      command: `${python} scripts/e2e_server.py`, cwd: join(root, 'server'),
      url: `${apiURL}/__e2e__/revision`, env, timeout: 120_000, reuseExistingServer: false,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 20_000 },
    },
    {
      // Compile and bundle this worktree, then use its Vite HTTP proxy. This
      // intentionally does not invoke SEO prerendering/Chrome or an older API.
      command: `bunx --bun tsc -b && bunx --bun vite build --mode e2e && bunx --bun vite --mode e2e --host 127.0.0.1 --port ${webPort} --strictPort`,
      cwd: client, url: baseURL, timeout: 120_000, reuseExistingServer: false,
      env: { ...env, API_PROXY_TARGET: apiURL, VITE_API_URL: '/api', VITE_GOOGLE_CLIENT_ID: 'offline-browser-suite' },
      gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
    },
  ],
});
