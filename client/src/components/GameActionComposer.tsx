import type { ReactNode } from 'react';

type GameAction = 'question' | 'guess';

interface GameActionComposerProps {
  activeAction: GameAction;
  onActionChange: (action: GameAction) => void;
  questionCount?: string;
  guessCount?: string;
  questionDisabled?: boolean;
  trailingActions?: ReactNode;
  helperText?: ReactNode;
  children: ReactNode;
}

export default function GameActionComposer({
  activeAction,
  onActionChange,
  questionCount,
  guessCount,
  questionDisabled = false,
  trailingActions,
  helperText,
  children,
}: GameActionComposerProps) {
  return (
    <section aria-label="Game action composer" className="shrink-0 border-t border-white/10 bg-obsidian-950/90 px-3 py-2.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div role="group" aria-label="Choose question or guess" className="flex min-w-0 items-center gap-1">
          <button
            type="button"
            aria-pressed={activeAction === 'question'}
            disabled={questionDisabled}
            onClick={() => onActionChange('question')}
            className={`flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
              activeAction === 'question'
                ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
            }`}
          >
            <span>Question</span>
            {questionCount && <span className="font-mono text-[10px] text-zinc-500">({questionCount})</span>}
          </button>
          <button
            type="button"
            aria-pressed={activeAction === 'guess'}
            onClick={() => onActionChange('guess')}
            className={`flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer ${
              activeAction === 'guess'
                ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
            }`}
          >
            <span>Guess</span>
            {guessCount && <span className="font-mono text-[10px] text-zinc-500">({guessCount})</span>}
          </button>
        </div>
        {trailingActions}
      </div>
      <div className="pt-0.5">{children}</div>
      {helperText && <div className="mt-2 text-center text-xs leading-relaxed text-zinc-400">{helperText}</div>}
    </section>
  );
}
