import { expect, test } from 'bun:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import GameActionComposer from '../src/components/GameActionComposer';

test('chat composer places the active game input below question and guess controls', () => {
  const markup = renderToStaticMarkup(createElement(GameActionComposer, {
    activeAction: 'guess',
    onActionChange: () => {},
    questionCount: '5/10',
    guessCount: '2/3',
    children: createElement('form', { 'aria-label': 'Guess location' }),
  }));
  const sectionStart = markup.indexOf('<section aria-label="Game action composer"');
  const formStart = markup.indexOf('<form aria-label="Guess location"></form>');
  const sectionEnd = markup.indexOf('</section>', sectionStart);

  expect(sectionStart).toBeGreaterThanOrEqual(0);
  expect(formStart).toBeGreaterThan(sectionStart);
  expect(formStart).toBeLessThan(sectionEnd);
  expect(markup).toContain('aria-label="Choose question or guess"');
  expect(markup).toContain('Question');
  expect(markup).toContain('(5/10)');
  expect(markup).toContain('Guess');
  expect(markup).toContain('(2/3)');
  expect(markup).toContain('aria-pressed="true"');
});

test('composer can omit controls selected in the chat header', () => {
  const markup = renderToStaticMarkup(createElement(GameActionComposer, {
    activeAction: 'question',
    onActionChange: () => {},
    showActionTabs: false,
    children: createElement('form', { 'aria-label': 'Question input' }),
  }));

  expect(markup).not.toContain('aria-label="Choose question or guess"');
  expect(markup).toContain('<form aria-label="Question input"></form>');
});
