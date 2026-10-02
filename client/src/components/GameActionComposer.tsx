import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

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
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  return (
    <section aria-label={isPl ? 'Panel akcji gry' : 'Game action composer'} className="game-action-composer flex min-h-0 shrink-0 flex-col border-t border-white/10 bg-obsidian-950/90 px-3 pt-2.5 pb-[calc(env(safe-area-inset-bottom)+0.625rem)]">
      {(showActionTabs || trailingActions) && (
        <div className="mb-2 flex items-center justify-between gap-2">
          {showActionTabs && (
            <div role="group" aria-label={isPl ? 'Wybierz pytanie lub strzał' : 'Choose question or guess'} className="flex min-w-0 items-center gap-1">
              <button
                type="button"
                aria-pressed={activeAction === 'question'}
                disabled={questionDisabled}
                onClick={() => onActionChange('question')}
                className={`flex min-h-11 items-center gap-1.5 rounded-sm px-2.5 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 ${
                  activeAction === 'question'
                    ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                    : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                }`}
              >
                <span>{isPl ? 'Pytanie' : 'Question'}</span>
                {questionCount && <span className="font-mono text-[10px] text-zinc-500">({questionCount})</span>}
              </button>
              <button
                type="button"
                aria-pressed={activeAction === 'guess'}
                onClick={() => onActionChange('guess')}
                className={`flex min-h-11 items-center gap-1.5 rounded-sm px-2.5 py-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors cursor-pointer ${
                  activeAction === 'guess'
                    ? 'border-b-2 border-emerald-400 bg-white/5 font-semibold text-sand-100'
                    : 'text-zinc-400 hover:bg-white/5 hover:text-sand-100'
                }`}
              >
                <span>{isPl ? 'Strzał' : 'Guess'}</span>
                {guessCount && <span className="font-mono text-[10px] text-zinc-500">({guessCount})</span>}
              </button>
            </div>
          )}
          {trailingActions}
        </div>
      )}
      <div className="min-h-0 pt-0.5">{children}</div>
      {helperText && <div className="game-action-help mt-2 text-center text-xs leading-relaxed text-zinc-400">{helperText}</div>}
    </section>
  );
}
