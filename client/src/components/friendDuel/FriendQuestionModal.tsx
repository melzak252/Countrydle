import { useEffect, useState } from 'react';
import {
  Zap,
  Clock,
  Check,
  X,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import type {
  FriendEntity,
  FriendGuidance,
  FriendHistory,
  HumanAnswer,
} from '../../types/friendMatch';
import type { DuelCopy } from './copy';
import { PrivateAdvice } from './DuelHistory';

interface FriendQuestionModalProps {
  pendingQuestion: FriendHistory;
  opponentName: string;
  ownSecret: FriendEntity | null;
  deadline: string | null;
  advice?: FriendGuidance;
  copy: DuelCopy;
  busy: boolean;
  onAnswer: (answer: HumanAnswer) => void;
}

export default function FriendQuestionModal({
  pendingQuestion,
  opponentName,
  ownSecret,
  deadline,
  advice,
  copy,
  busy,
  onAnswer,
}: FriendQuestionModalProps) {
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);

  const seconds = deadline
    ? Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000))
    : 60;
  const isUrgent = seconds <= 15;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="question-modal-title"
      className="fixed inset-0 z-[1200] flex items-center justify-center p-2 sm:p-4 bg-black/75 animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-xl max-h-[calc(var(--app-height,100dvh)-1rem)] sm:max-h-[calc(var(--app-height,100dvh)-2rem)] overflow-y-auto rounded-sm border border-app-border/30 bg-app-surface-raised p-3 sm:p-6 shadow-2xl space-y-3 sm:space-y-4 border-t-4 border-t-amber-700 custom-scrollbar">
        {/* Top Header: Badge & Live Countdown Timer */}
        <div className="flex items-center justify-between gap-3 border-b border-app-border/20 pb-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-sm bg-amber-50 border border-amber-300 px-2 py-1 font-mono text-xs font-semibold text-amber-900">
              <Zap size={13} className="text-amber-800" />
              <span>{copy.actionRequired}</span>
            </span>
            <span className="font-mono text-xs text-app-text-secondary">
              · {copy.answering}
            </span>
          </div>

          <div
            className={`flex items-center gap-1.5 font-mono text-xs font-semibold px-2.5 py-1 rounded-sm border ${
              isUrgent
                ? 'border-rose-300 bg-rose-50 text-rose-800'
                : 'border-app-border/30 bg-app-surface-muted text-app-text-secondary'
            }`}
          >
            <Clock size={13} className={isUrgent ? 'text-rose-700' : 'text-app-text-muted'} />
            <span className="tabular-nums">
              {seconds > 0
                ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
                : copy.expired}
            </span>
          </div>
        </div>

        {/* Inquirer Subhead */}
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-app-text-secondary">
          <HelpCircle size={14} className="text-app-accent" />
          <span>
            <strong className="text-app-text">{opponentName}</strong> asks about your secret:
          </span>
        </div>

        {/* The Question Card (Large, Prominent, Highly Legible) */}
        <div className="rounded-sm border border-app-border/30 bg-app-surface-muted p-4 sm:p-5 shadow-inner">
          <p
            id="question-modal-title"
            className="whitespace-pre-wrap break-words text-base sm:text-lg font-medium text-app-text leading-relaxed"
          >
            &quot;{pendingQuestion.question}&quot;
          </p>
        </div>

        {/* Context Reminder: Your Secret */}
        {ownSecret && (
          <div className="flex items-center justify-between rounded-sm border border-app-accent/25 bg-app-accent/10 px-3.5 py-2 text-xs">
            <span className="text-app-text-secondary font-mono text-[11px] uppercase tracking-wider">
              Answering for your secret:
            </span>
            <span className="font-mono font-bold text-app-accent text-sm tracking-wide">
              {ownSecret.name}
            </span>
          </div>
        )}

        {/* Private AI Guidance Card */}
        <PrivateAdvice guidance={advice} copy={copy} />

        {/* Answer Options Grid */}
        <div className="space-y-2 pt-1">
          <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-app-text-secondary">
            Select your response:
          </div>

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {/* 1. YES */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('yes')}
              className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-app-accent/30 bg-app-accent/10 px-2 sm:px-3 py-2.5 text-xs font-semibold text-app-accent shadow-sm transition-colors hover:bg-app-accent/15 hover:border-app-accent/60 active:scale-[0.98] disabled:opacity-40 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            >
              <Check size={14} className="stroke-[3]" />
              <span>{copy.yes}</span>
            </button>

            {/* 2. MOSTLY YES */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('mostly_yes')}
              className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-teal-700/30 bg-teal-50 px-2 sm:px-3 py-2.5 text-xs font-semibold text-teal-900 shadow-sm transition-colors hover:bg-teal-100 hover:border-teal-700/50 active:scale-[0.98] disabled:opacity-40 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            >
              <Check size={13} />
              <span>{copy.mostly_yes}</span>
            </button>

            {/* 3. MOSTLY NO */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('mostly_no')}
              className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-rose-300 bg-rose-50 px-2 sm:px-3 py-2.5 text-xs font-semibold text-rose-800 shadow-sm transition-colors hover:bg-rose-100 hover:border-rose-400 active:scale-[0.98] disabled:opacity-40 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            >
              <X size={13} />
              <span>{copy.mostly_no}</span>
            </button>

            {/* 4. NO */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('no')}
              className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-rose-300 bg-rose-50 px-2 sm:px-3 py-2.5 text-xs font-semibold text-rose-800 shadow-sm transition-colors hover:bg-rose-100 hover:border-rose-400 active:scale-[0.98] disabled:opacity-40 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
            >
              <X size={14} className="stroke-[3]" />
              <span>{copy.no}</span>
            </button>
          </div>

          {/* 5. I DON'T KNOW */}
          <button
            type="button"
            disabled={busy}
            onClick={() => onAnswer('unknown')}
            className="w-full flex items-center justify-center gap-1.5 rounded-sm border border-app-border/30 bg-app-surface-muted py-2 text-xs font-medium text-app-text-secondary transition-colors hover:border-app-border/50 hover:bg-app-border/20 hover:text-app-text disabled:opacity-40 cursor-pointer mt-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-app-focus"
          >
            <AlertCircle size={13} />
            <span>{copy.unknown}</span>
          </button>
        </div>

        {/* Auto-AI Fallback Reminder */}
        <p className="text-[11px] font-mono text-app-text-muted text-center leading-normal pt-1">
          If you do not answer within the deadline, an automated AI answer will be submitted to keep the duel moving.
        </p>
      </div>
    </div>
  );
}
