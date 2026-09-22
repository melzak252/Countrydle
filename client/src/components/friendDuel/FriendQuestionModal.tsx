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
      className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-xl max-h-[92vh] overflow-y-auto rounded-sm border border-emerald-500/30 bg-obsidian-950/95 p-5 sm:p-6 shadow-2xl space-y-4 border-t-4 border-t-amber-400 custom-scrollbar">
        {/* Top Header: Badge & Live Countdown Timer */}
        <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-sm bg-amber-500/20 border border-amber-500/40 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-amber-300 animate-pulse">
              <Zap size={13} className="text-amber-400" />
              <span>{copy.actionRequired}</span>
            </span>
            <span className="font-mono text-xs text-zinc-400">
              · {copy.answering}
            </span>
          </div>

          <div
            className={`flex items-center gap-1.5 font-mono text-xs font-semibold px-2.5 py-1 rounded-sm border ${
              isUrgent
                ? 'border-rose-500/50 bg-rose-950/70 text-rose-300 animate-pulse'
                : 'border-white/15 bg-obsidian-900 text-zinc-300'
            }`}
          >
            <Clock size={13} className={isUrgent ? 'text-rose-400' : 'text-zinc-400'} />
            <span className="tabular-nums">
              {seconds > 0
                ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
                : copy.expired}
            </span>
          </div>
        </div>

        {/* Inquirer Subhead */}
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-zinc-400">
          <HelpCircle size={14} className="text-emerald-400" />
          <span>
            <strong className="text-sand-100">{opponentName}</strong> asks about your secret:
          </span>
        </div>

        {/* The Question Card (Large, Prominent, Highly Legible) */}
        <div className="rounded-sm border border-white/15 bg-obsidian-900/90 p-4 sm:p-5 shadow-inner">
          <p
            id="question-modal-title"
            className="whitespace-pre-wrap break-words text-base sm:text-lg font-medium text-sand-100 leading-relaxed"
          >
            &quot;{pendingQuestion.question}&quot;
          </p>
        </div>

        {/* Context Reminder: Your Secret */}
        {ownSecret && (
          <div className="flex items-center justify-between rounded-sm border border-emerald-500/25 bg-emerald-950/30 px-3.5 py-2 text-xs">
            <span className="text-zinc-400 font-mono text-[11px] uppercase tracking-wider">
              Answering for your secret:
            </span>
            <span className="font-mono font-bold text-emerald-300 text-sm tracking-wide">
              {ownSecret.name}
            </span>
          </div>
        )}

        {/* Private AI Guidance Card */}
        <PrivateAdvice guidance={advice} copy={copy} />

        {/* Answer Options Grid */}
        <div className="space-y-2 pt-1">
          <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-400">
            Select your response:
          </div>

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {/* 1. YES */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('yes')}
              className="flex items-center justify-center gap-1.5 rounded-sm border border-emerald-500/40 bg-emerald-950/80 px-3 py-2.5 text-xs font-bold uppercase tracking-wider text-emerald-300 shadow-sm transition-all hover:bg-emerald-500/20 hover:border-emerald-400 hover:text-emerald-200 active:scale-[0.98] disabled:opacity-40 cursor-pointer"
            >
              <Check size={14} className="stroke-[3]" />
              <span>{copy.yes}</span>
            </button>

            {/* 2. MOSTLY YES */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('mostly_yes')}
              className="flex items-center justify-center gap-1.5 rounded-sm border border-teal-500/40 bg-teal-950/70 px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-teal-300 shadow-sm transition-all hover:bg-teal-500/20 hover:border-teal-400 hover:text-teal-200 active:scale-[0.98] disabled:opacity-40 cursor-pointer"
            >
              <Check size={13} />
              <span>{copy.mostly_yes}</span>
            </button>

            {/* 3. MOSTLY NO */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('mostly_no')}
              className="flex items-center justify-center gap-1.5 rounded-sm border border-rose-400/40 bg-rose-950/60 px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-rose-300 shadow-sm transition-all hover:bg-rose-500/20 hover:border-rose-400 hover:text-rose-200 active:scale-[0.98] disabled:opacity-40 cursor-pointer"
            >
              <X size={13} />
              <span>{copy.mostly_no}</span>
            </button>

            {/* 4. NO */}
            <button
              type="button"
              disabled={busy}
              onClick={() => onAnswer('no')}
              className="flex items-center justify-center gap-1.5 rounded-sm border border-rose-500/50 bg-rose-950/80 px-3 py-2.5 text-xs font-bold uppercase tracking-wider text-rose-300 shadow-sm transition-all hover:bg-rose-500/25 hover:border-rose-400 hover:text-rose-200 active:scale-[0.98] disabled:opacity-40 cursor-pointer"
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
            className="w-full flex items-center justify-center gap-1.5 rounded-sm border border-white/10 bg-white/5 py-2 text-xs font-medium text-zinc-400 transition-all hover:border-white/20 hover:bg-white/10 hover:text-sand-100 disabled:opacity-40 cursor-pointer mt-1"
          >
            <AlertCircle size={13} />
            <span>{copy.unknown}</span>
          </button>
        </div>

        {/* Auto-AI Fallback Reminder */}
        <p className="text-[11px] font-mono text-zinc-500 text-center leading-normal pt-1">
          If you do not answer within the deadline, an automated AI answer will be submitted to keep the duel moving.
        </p>
      </div>
    </div>
  );
}
