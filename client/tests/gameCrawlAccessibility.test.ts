import { expect, test } from 'bun:test';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const clientRoot = resolve(import.meta.dir, '..');
const prepareScript = resolve(clientRoot, 'scripts/prepare-shells.mjs');

test('prepare-shells creates truthful game-shell and bare spa-shell using bounded markers without residue', () => {
  const tempDir = mkdtempSync(join(tmpdir(), 'countrydle-shell-artifact-'));

  try {
    // Representative fixture with nested tags and bounded comment markers
    const fixtureHtml = `<!doctype html>
<html>
  <head>
    <title>Fixture App</title>
    <!-- GAME_SHELL_STYLES_START -->
    <style>#game-shell { color: red; }</style>
    <!-- GAME_SHELL_STYLES_END -->
    <script type="module" src="/assets/index-test.js"></script>
    <link rel="stylesheet" href="/assets/index-test.css">
  </head>
  <body>
    <div id="root"><!-- GAME_SHELL_START -->
      <div id="game-shell">
        <header><div><nav><a href="/guide">Guide</a></nav></div></header>
        <main>
          <h1>Game Heading</h1>
          <section><h2>Rules Section</h2><p>Rules content</p></section>
        </main>
      </div>
    <!-- GAME_SHELL_END --></div>
    <noscript><p>JavaScript required</p></noscript>
  </body>
</html>`;

    writeFileSync(join(tempDir, 'index.html'), fixtureHtml, 'utf-8');

    const result = spawnSync('node', [prepareScript, tempDir], { encoding: 'utf-8' });
    expect(result.status).toBe(0);

    const gameShell = readFileSync(join(tempDir, 'game-shell.html'), 'utf-8');
    const spaShell = readFileSync(join(tempDir, 'spa-shell.html'), 'utf-8');

    // 1. game-shell maintains full shell structure and script assets
    expect(gameShell).toContain('id="game-shell"');
    expect(gameShell).toContain('<h1>Game Heading</h1>');
    expect(gameShell).toContain('<h2>Rules Section</h2>');
    expect(gameShell).toContain('src="/assets/index-test.js"');

    // 2. spa-shell must have exactly empty <div id="root"></div> and ZERO headings/styles/residue
    expect(spaShell).toContain('<div id="root"></div>');
    expect(spaShell).not.toContain('<!-- GAME_SHELL_START -->');
    expect(spaShell).not.toContain('<!-- GAME_SHELL_END -->');
    expect(spaShell).not.toContain('id="game-shell"');
    expect(spaShell).not.toContain('<h1');
    expect(spaShell).not.toContain('<h2');
    expect(spaShell).not.toContain('GAME_SHELL_STYLES');
    expect(spaShell).not.toContain('#game-shell {');

    // Script and link assets remain preserved in spa-shell
    expect(spaShell).toContain('src="/assets/index-test.js"');
    expect(spaShell).toContain('href="/assets/index-test.css"');
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});
