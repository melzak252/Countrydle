import { Check, MessageSquare, Target, X } from 'lucide-react';
import ResultsQuestionHistory from '../ResultsQuestionHistory';
import type { AnswerReportMode, Guess, Question } from '../../types';
import type { GameplayNotice } from '../../lib/gameplayNotices';
import type { ResultDashboardDetailTab } from './types';

function ResultsGuessHistory({ guesses }: { guesses: Guess[] }) {
  if (!guesses.length) {
    return (
      <p className="py-4 text-center text-xs text-app-text-secondary">
        No guesses were submitted in this game.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {guesses.map((g, index) => {
        const hasDistance =
          g.distance_km !== undefined && g.distance_km !== null && !g.answer;
        const hasBearing = Boolean(g.bearing_direction && !g.answer);

        return (
          <div
            key={g.id ?? `${g.guess}-${index}`}
            className={`flex items-center justify-between gap-3 rounded-sm border px-3 py-2 text-xs ${
              g.answer
                ? 'border-app-accent/35 bg-app-accent/10'
                : 'border-app-border/70 bg-app-canvas'
            }`}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="font-mono text-[11px] font-semibold text-app-text-muted tabular-nums">
                #{index + 1}
              </span>
              {g.answer ? (
                <Check size={14} className="shrink-0 text-app-accent" aria-hidden="true" />
              ) : (
                <X size={14} className="shrink-0 text-[#c85243]" aria-hidden="true" />
              )}
              <span className="truncate font-medium text-app-text">{g.guess}</span>
            </div>

            {g.answer ? (
              <span className="shrink-0 font-mono text-[11px] font-semibold text-app-accent">
                Correct
              </span>
            ) : hasDistance ? (
              <div className="flex shrink-0 items-center gap-1.5 font-mono text-[11px] tabular-nums">
                <span className="rounded-sm border border-app-border bg-app-surface px-2 py-0.5 font-semibold text-app-text-secondary">
                  {Math.round(g.distance_km!).toLocaleString('en-US')} km
                </span>
                {hasBearing && (
                  <span
                    className="inline-flex items-center gap-0.5 rounded-sm border border-app-accent/30 bg-app-accent/10 px-1.5 py-0.5 font-semibold text-app-accent"
                    title={`${g.bearing_direction}${g.bearing_degrees !== undefined ? ` (${g.bearing_degrees}°)` : ''}`}
                  >
                    <span>{g.bearing_arrow || '↗'}</span>
                    <span>{g.bearing_direction}</span>
                  </span>
                )}
              </div>
            ) : (
              <span className="shrink-0 font-mono text-[11px] text-[#c85243]">
                Incorrect
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function buildQADetailTabs({
  reportMode,
  questions,
  guesses,
  notices,
}: {
  targetName?: string;
  reportMode: AnswerReportMode;
  questions?: Question[];
  guesses?: Guess[];
  notices?: GameplayNotice[];
}): ResultDashboardDetailTab[] {
  const safeQuestions = questions ?? [];
  const safeGuesses = guesses ?? [];

  return [
    {
      id: 'questions',
      label: 'Questions',
      badge: safeQuestions.length,
      icon: <MessageSquare size={15} className="shrink-0" aria-hidden="true" />,
      content:
        safeQuestions.length > 0 ? (
          <div className="space-y-3">
            <p className="text-xs text-app-text-secondary">
              Select a question to review its explanation or report an issue.
            </p>
            <ResultsQuestionHistory
              questions={safeQuestions}
              notices={notices}
              mode={reportMode}
              isGameOver
            />
          </div>
        ) : (
          <p className="py-4 text-center text-xs text-app-text-secondary">
            No questions were asked in this game.
          </p>
        ),
    },
    {
      id: 'guesses',
      label: 'Guesses',
      badge: safeGuesses.length,
      icon: <Target size={15} className="shrink-0" aria-hidden="true" />,
      content: <ResultsGuessHistory guesses={safeGuesses} />,
    },
  ];
}
