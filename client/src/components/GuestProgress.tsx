import { Check, Minus, X } from 'lucide-react';
import { useGuestHistory } from '../hooks/useGuestHistory';
import type { GuestGameType } from '../lib/guestHistory';

const modeNames: Record<GuestGameType, string> = {
  country: 'World',
  powiaty: 'Polish counties',
  us_states: 'US states',
  wojewodztwa: 'Polish voivodeships',
  flagdle: 'Flagdle',
};
const labels = { won: 'Solved', lost: 'Not solved', unplayed: 'Not played' };
const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: 'UTC' });

export default function GuestProgress({ gameType, today }: { gameType: GuestGameType; today: string }) {
  const history = useGuestHistory(gameType, today);

  return (
    <section aria-label={`${modeNames[gameType]} guest progress`} className="rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-serif text-xl text-sand-100">Your daily habit</h2>
        <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">{modeNames[gameType]} · This device</span>
      </div>
      <dl className="mb-5 grid grid-cols-3 divide-x divide-white/10 text-center">
        <div className="px-1">
          <dt className="text-xs text-zinc-400">Current streak</dt>
          <dd className="mt-1 font-mono text-xl text-emerald-400">{history.currentStreak}<span className="text-xs text-zinc-500"> {history.currentStreak === 1 ? 'day' : 'days'}</span></dd>
        </div>
        <div className="px-1">
          <dt className="text-xs text-zinc-400">Solved</dt>
          <dd className="mt-1 font-mono text-xl text-sand-100">{history.solved}</dd>
        </div>
        <div className="px-1">
          <dt className="text-xs text-zinc-400">Best score</dt>
          <dd className="mt-1 font-mono text-xl text-sand-100">{history.bestScore === null ? '—' : history.bestScore.toLocaleString('en-US')}</dd>
        </div>
      </dl>
      <ol aria-label="Last seven UTC days" className="grid grid-cols-7 gap-1.5">
        {history.days.map(day => (
          <li key={day.date} aria-label={`${day.date}${day.date === today ? ', today' : ''}: ${labels[day.status]}`} className="min-w-0 text-center">
            <span aria-hidden="true" className="mb-1.5 block font-mono text-[10px] text-zinc-500">{weekday.format(new Date(`${day.date}T00:00:00Z`))}</span>
            <span aria-hidden="true" className={`flex h-9 items-center justify-center rounded-sm border ${
              day.status === 'won' ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-400'
                : day.status === 'lost' ? 'border-amber-400/20 bg-amber-400/5 text-amber-300'
                  : 'border-white/10 text-zinc-600'
            } ${day.date === today ? 'ring-1 ring-sand-100/40' : ''}`}>
              {day.status === 'won' ? <Check size={16} /> : day.status === 'lost' ? <X size={16} /> : <Minus size={14} />}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[10px] text-zinc-500">Check: solved · Cross: not solved · Dash: not played. Days reset at 00:00 UTC.</p>
      <p className={`mt-4 text-xs leading-relaxed ${history.storageAvailable ? 'text-zinc-400' : 'text-amber-300'}`}>
        {history.storageAvailable
          ? 'Guest history stays in this browser on this device, including after sign-in. Clearing browser data removes it.'
          : 'Browser storage is unavailable or full. New progress may not be saved; any history shown is only what this browser can still read.'}
      </p>
    </section>
  );
}
