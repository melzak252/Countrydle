#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const targetDir = process.argv[2]
  ? resolve(process.cwd(), process.argv[2])
  : resolve(__dirname, '../dist');

const indexPath = resolve(targetDir, 'index.html');
const gameShellPath = resolve(targetDir, 'game-shell.html');
const spaShellPath = resolve(targetDir, 'spa-shell.html');

const START_MARKER = '<!-- GAME_SHELL_START -->';
const END_MARKER = '<!-- GAME_SHELL_END -->';
const STYLES_START = '<!-- GAME_SHELL_STYLES_START -->';
const STYLES_END = '<!-- GAME_SHELL_STYLES_END -->';

try {
  const indexHtml = readFileSync(indexPath, 'utf-8');

  if (!indexHtml.includes(START_MARKER) || !indexHtml.includes(END_MARKER)) {
    throw new Error(`index.html is missing bounded game shell markers (${START_MARKER} / ${END_MARKER})`);
  }

  // 1. game-shell.html is the compiled index.html containing the meaningful static shell
  writeFileSync(gameShellPath, indexHtml, 'utf-8');

  // 2. spa-shell.html is the bare SPA shell with an empty #root container,
  // used for publisher snapshot capture, account/admin routes, and generic fallback.
  // Using explicit bounded markers ensures zero residue/leakage inside or outside #root.
  const domRegex = new RegExp(
    `(<div id="root">\\s*)${START_MARKER}[\\s\\S]*?${END_MARKER}(\\s*<\\/div>)`
  );
  if (!domRegex.test(indexHtml)) {
    throw new Error('Could not cleanly isolate bounded game shell markers within #root container');
  }

  let bareSpaHtml = indexHtml.replace(domRegex, '<div id="root"></div>');

  // Also strip scoped shell styles from head for bare spa-shell if present
  if (bareSpaHtml.includes(STYLES_START) && bareSpaHtml.includes(STYLES_END)) {
    const styleRegex = new RegExp(`\\s*${STYLES_START}[\\s\\S]*?${STYLES_END}\\s*`);
    bareSpaHtml = bareSpaHtml.replace(styleRegex, '\n');
  }

  // Verification guard: ensure no game markup leaked into bare SPA shell
  if (
    bareSpaHtml.includes('id="game-shell"') ||
    bareSpaHtml.includes('Play Countrydle') ||
    bareSpaHtml.includes('shell-main') ||
    bareSpaHtml.includes(START_MARKER) ||
    bareSpaHtml.includes(STYLES_START)
  ) {
    throw new Error('Residue detected in generated spa-shell.html after stripping game shell');
  }

  if (!bareSpaHtml.includes('<div id="root"></div>')) {
    throw new Error('spa-shell.html is missing empty <div id="root"></div> container');
  }

  writeFileSync(spaShellPath, bareSpaHtml, 'utf-8');

  console.log('[prepare-shells] Successfully created game-shell.html and spa-shell.html');
} catch (error) {
  console.error(`[prepare-shells] Failed: ${error.message}`);
  process.exit(1);
}
