import type { Guess } from '../types';
import { Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface GuessHistoryProps {
  guesses: Guess[];
}

function getDistanceColor(distanceKm: number): string {
  if (distanceKm <= 500) {
    return 'border-app-accent/30 bg-app-accent/10 text-app-accent';
  }
  if (distanceKm <= 2000) {
    return 'border-amber-700/25 bg-amber-500/10 text-amber-800';
  }
  return 'border-app-border/15 bg-app-surface-muted text-app-text-secondary';
}

export default function GuessHistory({ guesses }: GuessHistoryProps) {
  const { t } = useTranslation();

  if (guesses.length === 0) {
    return (
      <p className="text-sm leading-relaxed text-app-text-muted">
        {t('gamePage.makeAGuess')}
      </p>
    );
  }
  const sortedGuesses = [...guesses].reverse();

  return (
    <ul className="space-y-2">
      {sortedGuesses.map((g) => {
        const hasDistance =
          g.distance_km !== undefined &&
          g.distance_km !== null &&
          !g.answer;
        const hasBearing = Boolean(g.bearing_direction && !g.answer);

        return (
          <li
            key={g.id}
            className={`flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-l-2 bg-app-surface-muted px-3 py-2.5 ${
              g.answer ? 'border-app-accent' : 'border-rose-500/60'
            }`}
          >
            <div className="flex min-w-0 items-center gap-3">
              {g.answer ? (
                <Check
                  size={16}
                  className="shrink-0 text-app-accent"
                  aria-hidden="true"
                />
              ) : (
                <X
                  size={16}
                  className="shrink-0 text-rose-600"
                  aria-hidden="true"
                />
              )}
              <span className="sr-only">
                {t(g.answer ? 'gamePage.correct' : 'gamePage.incorrect')}:{' '}
              </span>
              <span className="break-words text-sm font-medium text-app-text">
                {g.guess}
              </span>
            </div>

            {hasDistance && (
              <div
                className="flex shrink-0 items-center gap-1.5 font-mono text-xs"
                aria-label={`Distance: ${g.distance_km} kilometers${
                  hasBearing ? `, bearing ${g.bearing_direction}` : ''
                }`}
              >
                <span
                  className={`rounded border px-2 py-0.5 font-semibold ${getDistanceColor(
                    g.distance_km!
                  )}`}
                >
                  {g.distance_km!.toLocaleString('en-US')} km
                </span>

                {hasBearing && (
                  <span
                    className="inline-flex items-center gap-1 rounded border border-app-accent/30 bg-app-accent/10 px-2 py-0.5 font-semibold text-app-accent"
                    title={`${g.bearing_direction}${
                      g.bearing_degrees !== undefined && g.bearing_degrees !== null
                        ? ` (${g.bearing_degrees}°)`
                        : ''
                    }`}
                  >
                    <span className="text-sm leading-none" aria-hidden="true">
                      {g.bearing_arrow || '↗'}
                    </span>
                    <span>{g.bearing_direction}</span>
                  </span>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
