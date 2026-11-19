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
    <section
      aria-label={'Game action composer'}
      className="game-action-composer flex min-h-0 shrink-0 flex-col border-t border-app-border/30 bg-app-surface-raised px-3 pt-2 pb-[calc(env(safe-area-inset-bottom)+0.5rem)] max-md:[@media(max-height:560px)]:pt-1 max-md:[@media(max-height:560px)]:pb-[calc(env(safe-area-inset-bottom)+0.25rem)] md:bg-app-surface md:pt-2.5 md:pb-3"
    >
      {(showActionTabs || trailingActions) && (
        <div className="mb-2 flex items-center justify-between gap-2 max-md:[@media(max-height:560px)]:mb-1">
          {showActionTabs && (
            <div role="group" aria-label={'Choose question or guess'} className="flex min-w-0 items-center gap-1">
              <button
                type="button"
                aria-pressed={activeAction === 'question'}
                disabled={questionDisabled}
                onClick={() => onActionChange('question')}
                className={`flex min-h-11 items-center gap-1.5 rounded-sm px-3 py-2 font-mono text-sm transition-colors cursor-pointer disabled:cursor-not-allowed disabled:bg-app-surface-muted disabled:text-app-text-secondary disabled:opacity-100 max-md:[@media(max-height:560px)]:min-h-8 max-md:[@media(max-height:560px)]:py-1 ${
                  activeAction === 'question'
                    ? 'border-b-2 border-app-accent bg-app-surface-muted font-semibold text-app-text'
                    : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                }`}
              >
                <span>{'Question'}</span>
                {questionCount && <span className="font-mono text-xs text-app-text-secondary">({questionCount})</span>}
              </button>
              <button
                type="button"
                aria-pressed={activeAction === 'guess'}
                onClick={() => onActionChange('guess')}
                className={`flex min-h-11 items-center gap-1.5 rounded-sm px-3 py-2 font-mono text-sm transition-colors cursor-pointer max-md:[@media(max-height:560px)]:min-h-8 max-md:[@media(max-height:560px)]:py-1 ${
                  activeAction === 'guess'
                    ? 'border-b-2 border-app-accent bg-app-surface-muted font-semibold text-app-text'
                    : 'text-app-text-secondary hover:bg-app-surface-muted hover:text-app-text'
                }`}
              >
                <span>{'Guess'}</span>
                {guessCount && <span className="font-mono text-xs text-app-text-secondary">({guessCount})</span>}
              </button>
            </div>
          )}
          {trailingActions}
        </div>
      )}
      <div className="min-h-0 pt-0.5 max-md:[@media(max-height:560px)]:pt-0">{children}</div>
      {helperText && (
        <div className="game-action-help mt-2 text-center text-sm leading-relaxed text-app-text-secondary max-md:[@media(max-height:560px)]:mt-1 max-md:[@media(max-height:560px)]:text-xs">
          {helperText}
        </div>
      )}
    </section>
  );
}
