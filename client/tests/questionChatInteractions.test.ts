import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import type { GameplayNotice } from '../src/lib/gameplayNotices';
import type { Question } from '../src/types';
import QuestionChat from '../src/components/QuestionChat';
import ResultsQuestionHistory from '../src/components/ResultsQuestionHistory';

const i18n = createInstance();
await i18n.init({
  lng: 'en',
  resources: { en: { translation: { chat: { copyQuestion: 'Copy question' } } } },
});

const question: Question = {
  id: 1,
  original_question: 'Is it in Europe?',
  valid: true,
  answer: false,
  explanation: 'Poland is in Europe.',
  fact_provenance: [{
    relation: 'membership',
    value: 'Europe',
    provenance: {
      status: 'cited', citation: 'Geographic evidence for Poland',
      source_url: 'https://example.com/poland', effective_from: null,
      effective_to: null, retrieved_at: null, updated_at: null, convention: null,
    },
  }],
  user_id: 1,
  day_id: 1,
  asked_at: '2026-09-26T10:00:00Z',
};
const notice: GameplayNotice = {
  id: 'warning',
  action: 'question',
  input: 'Does it have a coastline?',
  title: 'Question not answered',
  reason: 'This is not a yes-or-no question.',
  nextStep: 'Rephrase it.',
  createdAt: '2026-09-26T10:01:00Z',
};

function renderChat(isGameOver = false) {
  return renderToStaticMarkup(createElement(
    I18nextProvider,
    { i18n },
    createElement(QuestionChat, {
      questions: [question],
      notices: [notice],
      mode: 'countrydle',
      isGameOver,
      isLoading: true,
      pendingQuestion: 'Is it north of the equator?',
    }),
  ));
}

test('chat has a copy action for each displayed question', () => {
  const markup = renderChat();

  expect(markup.match(/aria-label="Copy question"/g)).toHaveLength(3);
  expect(markup).toContain('Is it in Europe?');
  expect(markup).toContain('Does it have a coastline?');
  expect(markup).toContain('Is it north of the equator?');
});


test('active chat never mounts target-bearing explanations or evidence', () => {
  const markup = renderChat();
  expect(markup).not.toContain('Poland');
  expect(markup).not.toContain('https://example.com/poland');
  expect(markup).toContain(notice.reason);
});

test('completed chat displays named factual explanations and evidence', () => {
  const markup = renderChat(true);
  expect(markup).toContain(question.explanation!);
  expect(markup).toContain('Geographic evidence for Poland');
  expect(markup).toContain('https://example.com/poland');
});

test('result history gates explanations and evidence on completion', () => {
  const renderHistory = (isGameOver: boolean) => renderToStaticMarkup(createElement(
    I18nextProvider, { i18n },
    createElement(ResultsQuestionHistory, {
      questions: [question], notices: [notice], mode: 'countrydle', isGameOver,
    }),
  ));
  const active = renderHistory(false);
  expect(active).not.toContain('Poland');
  expect(active).not.toContain('https://example.com/poland');
  expect(active).toContain(notice.reason);
  const completed = renderHistory(true);
  expect(completed).toContain(question.explanation!);
  expect(completed).toContain('Geographic evidence for Poland');
});
