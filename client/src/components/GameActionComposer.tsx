import type { ReactNode } from 'react';

type GameAction = 'question' | 'guess';

interface GameActionComposerProps {
  activeAction: GameAction;
  onActionChange: (action: GameAction) => void;
  questionCount?: string;
  guessCount?: string;
  questionDisabled?: boolean;
  showActionTabs?: boolean;
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
  showActionTabs = true,
  trailingActions,
  helperText,
  children,
}: GameActionComposerProps) {
  return (
    <section aria-label="Game action composer" className="shrink-0 border-t border-white/10 bg-obsidian-950/90 px-3 py-2.5">
      {(showActionTabs || trailingActions) && (
        <div className="mb-2 flex items-center justify-between gap-2">
          {showActionTabs && (
            <div role="group" aria-label="Choose question or guess" className="inline-flex items-center gap-1 rounded-lg bg-obsidian-900/90 p-0.5 border border-white/10 shadow-inner">
              <button
                type="button"
                aria-pressed={activeAction === 'question'}
                disabled={questionDisabled}
                onClick={() => onActionChange('question')}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
                  activeAction === 'question'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/40 shadow-sm font-semibold'
                    : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5 border border-transparent font-medium'
                }`}
              >
                <span>Question</span>
                {questionCount && (
                  <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-full ${
                    activeAction === 'question'
                      ? 'bg-emerald-400/20 text-emerald-300 font-semibold'
                      : 'bg-white/5 text-zinc-400'
                  }`}>
                    ({questionCount})
                  </span>
                )}
              </button>
              <button
                type="button"
                aria-pressed={activeAction === 'guess'}
                onClick={() => onActionChange('guess')}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-all cursor-pointer ${
                  activeAction === 'guess'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-400/40 shadow-sm font-semibold'
                    : 'text-zinc-400 hover:text-sand-100 hover:bg-white/5 border border-transparent font-medium'
                }`}
              >
                <span>Guess</span>
                {guessCount && (
                  <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-full ${
                    activeAction === 'guess'
                      ? 'bg-amber-400/20 text-amber-300 font-semibold'
                      : 'bg-white/5 text-zinc-400'
                  }`}>
                    ({guessCount})
                  </span>
                )}
              </button>
            </div>
          )}
          {trailingActions}
        </div>
      )}
      <div className="pt-0.5">{children}</div>
      {helperText && <div className="mt-2 text-center text-xs leading-relaxed text-zinc-400">{helperText}</div>}
    </section>
  );
}
