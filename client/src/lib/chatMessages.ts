import type { Question } from '../types';
import type { GameplayNotice } from './gameplayNotices';

export function getConversationMessages(questions: Question[], notices: GameplayNotice[]) {
  return [
    ...questions.map((question, index) => {
      // The API's timezone-naive database timestamps are UTC, not browser-local time.
      const timestamp = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(question.asked_at)
        ? question.asked_at
        : `${question.asked_at}Z`;
      return { kind: 'question' as const, question, index, time: Date.parse(timestamp) || 0 };
    }),
    ...notices.map(notice => ({ kind: 'notice' as const, notice, time: Date.parse(notice.createdAt) || 0 })),
  ].sort((a, b) => a.time - b.time);
}
