import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter } from 'react-router-dom';
import ShareResultCard from '../src/components/ShareResultCard';
import type { Question } from '../src/types';

const i18n = createInstance();
await i18n.init({
  lng: 'en',
  resources: {
    en: {
      translation: {
        chat: {
          copyQuestion: 'Copy question',
          historyTitle: 'Question History',
        },
        share: {
          shareBtn: 'Share Result',
          copyBtn: 'Copy',
        },
      },
    },
  },
});

const sampleQuestion: Question = {
  id: 42,
  original_question: 'Is it in Europe?',
  valid: true,
  answer: true,
  explanation: 'The target country is located in Southern Europe.',
  user_id: 1,
  day_id: 1,
  asked_at: '2026-09-29T12:00:00Z',
  report_token: 'tok_42',
};

function renderCard(props: Partial<Parameters<typeof ShareResultCard>[0]> = {}) {
  return renderToStaticMarkup(
    createElement(
      MemoryRouter,
      {},
      createElement(
        I18nextProvider,
        { i18n },
        createElement(ShareResultCard, {
          gameName: 'Countrydle',
          gamePath: '/game',
          date: '2026-09-29',
          won: true,
          points: 100,
          questionsAsked: 1,
          maxQuestions: 10,
          guessesMade: 1,
          maxGuesses: 3,
          targetName: 'Italy',
          targetCountryCode: 'it',
          ...props,
        }),
      ),
    ),
  );
}

test('results explorer exposes linked tabs and keeps reviewable answers in server markup', () => {
  const markup = renderCard({ questions: [sampleQuestion], mode: 'countrydle' });
  const tabs = [...markup.matchAll(/<button[^>]*role="tab"[^>]*>/g)].map(match => match[0]);
  expect(tabs).toHaveLength(2);
  for (const tab of tabs) {
    const panelId = tab.match(/aria-controls="([^"]+)"/)?.[1];
    const tabId = tab.match(/id="([^"]+)"/)?.[1];
    expect(panelId).toBeDefined();
    expect(tabId).toBeDefined();
    expect(markup).toMatch(new RegExp(`id="${panelId}"[^>]*role="tabpanel"[^>]*aria-labelledby="${tabId}"`));
  }
  expect(tabs[0]).toContain('aria-selected="true"');
  expect(tabs[1]).toContain('aria-selected="false"');
  const disclosures = [...markup.matchAll(/<details\b[^>]*>/g)].map(match => match[0]);
  expect(disclosures).toHaveLength(1);
  expect(disclosures[0]).not.toMatch(/\bopen(?:=|\s|>)/);
  expect(markup).toContain(sampleQuestion.original_question);
  expect(markup).toContain(sampleQuestion.explanation);
  expect(markup).toContain('aria-expanded="false"');
});

test('results explorer shows notes directly when the count or question list is empty', () => {
  for (const props of [
    { questions: [] },
    { questionsAsked: 0, questions: [sampleQuestion] },
  ]) {
    const markup = renderCard(props);
    expect(markup).not.toContain('role="tab"');
    expect(markup).not.toContain('role="tablist"');
    expect(markup).not.toContain(sampleQuestion.original_question);
    expect(markup).toContain('href="/explore"');
  }
});

test('lost results retain notes navigation and answer explanations for review', () => {
  const markup = renderCard({ won: false, questions: [sampleQuestion], mode: 'countrydle' });
  expect(markup).toContain('href="/explore"');
  expect(markup).toContain(sampleQuestion.explanation);
  expect(markup.match(/role="tabpanel"/g)).toHaveLength(2);
});
