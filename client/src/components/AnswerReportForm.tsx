import { useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { isAxiosError } from 'axios';
import { Flag, Loader2 } from 'lucide-react';
import { reportService } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import type { AnswerReportMode } from '../types';

interface AnswerReportFormProps {
  mode: AnswerReportMode;
  questionId: number;
  reportToken?: string | null;
}

type ReportStatus = 'idle' | 'pending' | 'submitted' | 'duplicate';

export default function AnswerReportForm({ mode, questionId, reportToken }: AnswerReportFormProps) {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated);
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const submittingRef = useRef(false);
  const [isOpen, setIsOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [status, setStatus] = useState<ReportStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const pending = status === 'pending';
  const reported = status === 'submitted' || status === 'duplicate';
  const canSubmit = isAuthenticated || Boolean(reportToken);

  const close = () => {
    if (submittingRef.current) return;
    setIsOpen(false);
    setError(null);
    triggerRef.current?.focus();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current || reported || !canSubmit || questionId <= 0) return;
    const trimmedComment = comment.trim();
    if (!trimmedComment || trimmedComment.length > 2000) {
      setError('Explain what seems wrong in 1–2,000 characters.');
      return;
    }

    submittingRef.current = true;
    setStatus('pending');
    setError(null);
    try {
      await reportService.submit(mode, questionId, trimmedComment, reportToken ?? undefined);
      setStatus('submitted');
      setIsOpen(false);
    } catch (cause: unknown) {
      const responseStatus = isAxiosError(cause) ? cause.response?.status : undefined;
      if (responseStatus === 409) {
        setStatus('duplicate');
        setIsOpen(false);
      } else {
        setStatus('idle');
        if (responseStatus === 404) {
          setError('This question is no longer available to report from this session. Your comment has been kept.');
        } else if (responseStatus === 401 || responseStatus === 403) {
          setError('You do not have permission to report this question from this session. Your comment has been kept.');
        } else if (responseStatus === 422) {
          setError('The report could not be accepted. Check your comment and try again.');
        } else if (responseStatus === 429) {
          setError('Too many requests. Please wait before submitting again. Your comment has been kept.');
        } else {
          setError('Could not send your report. Please try again when connected. Your comment has been kept.');
        }
      }
    } finally {
      submittingRef.current = false;
    }
  };

  return (
    <div className="border-t border-white/10 px-4 py-3">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => isOpen ? close() : setIsOpen(true)}
        disabled={pending || reported}
        aria-expanded={isOpen}
        aria-controls={`${id}-panel`}
        className="inline-flex min-h-8 items-center gap-2 rounded-sm text-xs text-zinc-400 transition-colors hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-400 disabled:cursor-default disabled:opacity-60"
      >
        <Flag size={13} aria-hidden="true" />
        {reported ? 'Reported' : 'Report answer'}
      </button>
      <p role="status" className={reported ? 'mt-2 text-sm leading-6 text-emerald-300' : 'sr-only'}>
        {status === 'submitted' ? 'Report sent. Thank you for helping improve the answers.' : status === 'duplicate' ? 'This answer has already been reported. Thank you.' : pending ? 'Sending report…' : ''}
      </p>
      {isOpen && (
        <div id={`${id}-panel`} className="mt-3">
          {canSubmit ? (
            <form onSubmit={handleSubmit} aria-busy={pending} className="space-y-3">
              <div>
                <label htmlFor={`${id}-comment`} className="mb-2 block text-sm font-medium text-sand-100">What seems wrong?</label>
                <p id={`${id}-help`} className="mb-3 text-xs leading-5 text-zinc-400">Explain why you think this answer or question assessment is incorrect. Reporting does not change your game.</p>
                <textarea
                  id={`${id}-comment`}
                  value={comment}
                  onChange={event => setComment(event.target.value)}
                  required
                  maxLength={2000}
                  rows={4}
                  readOnly={pending}
                  aria-describedby={`${id}-help ${id}-count${error ? ` ${id}-error` : ''}`}
                  className="block w-full resize-y rounded-sm border border-white/15 bg-obsidian-900 px-3 py-2.5 text-base leading-6 text-sand-100 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 read-only:opacity-60"
                />
                <p id={`${id}-count`} className="mt-1 text-right font-mono text-xs text-zinc-500">{comment.length} / 2,000</p>
              </div>
              {error && <p id={`${id}-error`} role="alert" className="text-sm leading-6 text-rose-300">{error}</p>}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  disabled={pending || !comment.trim()}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-sm font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pending && <Loader2 size={15} className="animate-spin" aria-hidden="true" />}
                  {pending ? 'Sending…' : 'Send report'}
                </button>
                <button type="button" onClick={close} disabled={pending} className="min-h-10 rounded-sm px-2 py-2 text-sm text-zinc-400 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed disabled:opacity-50">Cancel</button>
              </div>
            </form>
          ) : (
            <div>
              <p className="text-sm leading-6 text-zinc-400">This older question has no reporting token. If you asked it while signed in, sign in to that account to report it. Older guest questions cannot be reported.</p>
              <button type="button" onClick={close} className="mt-3 min-h-10 rounded-sm px-2 py-2 text-sm text-zinc-400 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400">Cancel</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
