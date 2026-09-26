import { expect, test } from 'bun:test';
import type { Question } from '../src/types';
import type { GameplayNotice } from '../src/lib/gameplayNotices';
import { getConversationMessages } from '../src/lib/chatMessages';

const notice: GameplayNotice = {
  id: 'warning', action: 'question', input: 'Where is it?', title: 'Question not answered',
  reason: 'This is not a yes-or-no question.', nextStep: 'Rephrase it.', createdAt: '2026-09-26T10:01:00Z',
};
const question: Question = {
  id: 1, original_question: 'Is it in Europe?', valid: true, answer: false,
  user_id: 1, day_id: 1, asked_at: '2026-09-26T10:00:00.123456',
};

test('a warning stays between earlier and later server questions regardless of browser timezone', () => {
  const later = { ...question, id: 2, asked_at: '2026-09-26T10:02:00.123456' };
  const messages = getConversationMessages([question, later], [notice]);
  expect(messages.map(message => message.kind)).toEqual(['question', 'notice', 'question']);
  expect(messages[0].time).toBe(Date.UTC(2026, 8, 26, 10, 0, 0, 123));
});

test('explicit timestamp offsets are respected instead of being interpreted as UTC twice', () => {
  const later = { ...question, asked_at: '2026-09-26T12:02:00+02:00' };
  const messages = getConversationMessages([later], [notice]);
  expect(messages.map(message => message.kind)).toEqual(['notice', 'question']);
  expect(messages[1].time).toBe(Date.UTC(2026, 8, 26, 10, 2));
});
