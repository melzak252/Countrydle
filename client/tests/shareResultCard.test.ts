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
          reviewHelp: 'Review explanations and report any issues',
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

test('results modal renders chat history with question explanations and report button', () => {
  const markup = renderCard({
    questions: [sampleQuestion],
    mode: 'countrydle',
  });

  expect(markup).toContain('Question History');
  expect(markup).toContain('Is it in Europe?');
  expect(markup).toContain('The target country is located in Southern Europe.');
  expect(markup).toContain('Report answer');
});

test('results modal omits question history section when no questions were asked', () => {
  const markup = renderCard({
    questions: [],
  });

  expect(markup).not.toContain('Question History');
  expect(markup).not.toContain('Report answer');
});
