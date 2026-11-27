import { Check, Minus, X } from 'lucide-react';

import { useGuestHistory } from '../hooks/useGuestHistory';
import type { GuestGameType } from '../lib/guestHistory';

const modeNames: Record<GuestGameType, string> = {
  country: 'World',
  powiaty: 'Polish counties',
  us_states: 'US states',
  wojewodztwa: 'Polish voivodeships',
  countydle: 'English counties',
  europe: 'Europe',
  asia: 'Asia',
  africa: 'Africa',
  americas: 'The Americas',
  flagdle: 'Flagdle',
};
const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: 'UTC' });

export default function GuestProgress({ gameType, today }: { gameType: GuestGameType; today: string }) {
  
  
  const locale = 'en-US';
  const modeName = modeNames[gameType];
  const labels = { won: 'Solved', lost: 'Not solved', unplayed: 'Not played' };
  const history = useGuestHistory(gameType, today);

  return (
    <section aria-label={`${modeName} guest progress`} className="rounded-sm border border-app-border/20 bg-app-surface p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight text-app-text">{'Your daily habit'}</h2>
        <span className="text-xs text-app-text-muted">{modeName} · {'This device'}</span>
      </div>
      <dl className="mb-5 grid grid-cols-3 divide-x divide-app-border/20 text-center">
        <div className="min-w-0 px-1">
          <dt className="text-xs text-app-text-muted">{'Current streak'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-emerald-700">{history.currentStreak}<span className="text-xs text-app-text-muted"> {(history.currentStreak === 1 ? 'day' : 'days')}</span></dd>
        </div>
        <div className="min-w-0 px-1">
          <dt className="text-xs text-app-text-muted">{'Solved'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-app-text">{history.solved}</dd>
        </div>
        <div className="min-w-0 px-1">
          <dt className="text-xs text-app-text-muted">{'Best score'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-app-text">{history.bestScore === null ? '—' : history.bestScore.toLocaleString(locale)}</dd>
        </div>
      </dl>
      <ol aria-label={'Last seven UTC days'} className="grid grid-cols-7 gap-1.5">
        {history.days.map(day => (
          <li key={day.date} aria-label={`${day.date}${day.date === today ? (', today') : ''}: ${labels[day.status]}`} className="min-w-0 text-center">
            <span aria-hidden="true" className="mb-1.5 block font-mono text-[10px] text-app-text-muted">{weekday.format(new Date(`${day.date}T00:00:00Z`))}</span>
            <span aria-hidden="true" className={`flex h-9 items-center justify-center rounded-sm border ${
              day.status === 'won' ? 'border-emerald-700/30 bg-emerald-600/10 text-emerald-700'
                : day.status === 'lost' ? 'border-amber-700/30 bg-amber-600/10 text-amber-800'
                  : 'border-app-border/20 bg-app-surface-muted/50 text-app-text-muted'
            } ${day.date === today ? 'ring-1 ring-app-accent/60' : ''}`}>
              {day.status === 'won' ? <Check size={16} /> : day.status === 'lost' ? <X size={16} /> : <Minus size={14} />}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs leading-relaxed text-app-text-muted">{'Check: solved · Cross: not solved · Dash: not played. Days reset at 00:00 UTC.'}</p>
      <p className={`mt-4 text-xs leading-relaxed ${history.storageAvailable ? 'text-app-text-muted' : 'text-amber-800'}`}>
        {history.storageAvailable
          ? ('Guest history stays in this browser on this device, including after sign-in. Clearing browser data removes it.')
          : ('Browser storage is unavailable or full. New progress may not be saved; any history shown is only what this browser can still read.')}
      </p>
    </section>
  );
}
