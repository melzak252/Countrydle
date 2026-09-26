import { z } from 'zod';

export interface GameplayNotice {
  id: string;
  action: 'question' | 'guess';
  input: string;
  title: string;
  reason: string;
  nextStep: string;
  createdAt: string;
}

export type GameplayNoticeInput = Omit<GameplayNotice, 'id' | 'createdAt'>;

const SubmissionError = z.object({
  response: z.object({
    status: z.number(),
    data: z.object({
      detail: z.union([z.string(), z.array(z.object({ msg: z.string() }))]).catch(''),
    }).catch({ detail: '' }),
  }).optional(),
});

export function gameplayFailure(
  action: GameplayNotice['action'],
  input: string,
  error: unknown,
): GameplayNoticeInput {
  const parsed = SubmissionError.safeParse(error);
  const response = parsed.success ? parsed.data.response : undefined;
  const status = response?.status;
  const rawDetail = response?.data.detail;
  const detail = typeof rawDetail === 'string' ? rawDetail.trim() : rawDetail?.map(item => item.msg).join(' ') || '';
  const base = { action, input };

  if (!response) {
    return { ...base, title: 'Connection interrupted', reason: `We could not confirm whether your ${action} was received.`, nextStep: 'Check your connection and refresh the game to check your history before trying again.' };
  }
  if (status === 429) {
    return { ...base, title: 'Please slow down', reason: 'Too many requests were sent in a short time. The server temporarily paused new submissions.', nextStep: 'Wait a moment, then send your question or guess again.' };
  }
  if (status === 401 || status === 403) {
    return { ...base, title: 'Submission not authorized', reason: 'The server did not allow this submission with your current session.', nextStep: 'Refresh the page. If you were signed in, sign in again before retrying.' };
  }
  if (typeof status === 'number' && status >= 500) {
    return { ...base, title: 'The server could not finish', reason: `A server problem interrupted your ${action}. We could not confirm the result.`, nextStep: 'Refresh to check your history before trying again. If the problem continues, try again later.' };
  }
  return {
    ...base,
    title: action === 'question' ? 'Question not accepted' : 'Guess not accepted',
    reason: detail || `The server rejected this ${action} without providing a reason.`,
    nextStep: status === 422
      ? 'Edit your submission to meet the requirement above, then try again.'
      : /over|no more|limit/i.test(detail)
        ? 'Check your remaining attempts. If this puzzle has ended, return for the next daily game.'
        : action === 'question'
          ? 'Ask one clear yes-or-no question about a geographic fact, then try again.'
          : 'Choose a location from the suggestions that you have not guessed yet.',
  };
}
