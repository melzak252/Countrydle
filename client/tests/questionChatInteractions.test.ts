import { expect, test } from 'bun:test';
import { createInstance } from 'i18next';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import type { GameplayNotice } from '../src/lib/gameplayNotices';
import type { Question } from '../src/types';
import QuestionChat from '../src/components/QuestionChat';

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

function renderChat() {
  return renderToStaticMarkup(createElement(
    I18nextProvider,
    { i18n },
    createElement(QuestionChat, {
      questions: [question],
      notices: [notice],
      mode: 'countrydle',
      isGameOver: false,
      isLoading: true,
      pendingQuestion: 'Is it north of the equator?',
    }),
  ));
}

test('player chat questions are selectable and each has a copy action', () => {
  const markup = renderChat();

  expect(markup).toContain('select-text');
  expect(markup.match(/aria-label="Copy question"/g)).toHaveLength(3);
  expect(markup).toContain('Is it in Europe?');
  expect(markup).toContain('Does it have a coastline?');
  expect(markup).toContain('Is it north of the equator?');
});
