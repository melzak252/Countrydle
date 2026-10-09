import { Check, Minus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useGuestHistory } from '../hooks/useGuestHistory';
import type { GuestGameType } from '../lib/guestHistory';

const modeNames: Record<GuestGameType, { en: string; pl: string }> = {
  country: { en: 'World', pl: 'Świat' },
  powiaty: { en: 'Polish counties', pl: 'Polskie powiaty' },
  us_states: { en: 'US states', pl: 'Stany USA' },
  wojewodztwa: { en: 'Polish voivodeships', pl: 'Polskie województwa' },
  europe: { en: 'Europe', pl: 'Europa' },
  asia: { en: 'Asia', pl: 'Azja' },
  africa: { en: 'Africa', pl: 'Afryka' },
  americas: { en: 'The Americas', pl: 'Ameryki' },
  flagdle: { en: 'Flagdle', pl: 'Flagdle' },
};
const weekdays = {
  en: new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: 'UTC' }),
  pl: new Intl.DateTimeFormat('pl-PL', { weekday: 'short', timeZone: 'UTC' }),
};

export default function GuestProgress({ gameType, today }: { gameType: GuestGameType; today: string }) {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const locale = isPl ? 'pl-PL' : 'en-US';
  const modeName = modeNames[gameType][isPl ? 'pl' : 'en'];
  const weekday = weekdays[isPl ? 'pl' : 'en'];
  const labels = isPl
    ? { won: 'Rozwiązane', lost: 'Nierozwiązane', unplayed: 'Bez gry' }
    : { won: 'Solved', lost: 'Not solved', unplayed: 'Not played' };
  const history = useGuestHistory(gameType, today);

  return (
    <section aria-label={isPl ? `${modeName}: postęp gościa` : `${modeName} guest progress`} className="rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold tracking-tight text-sand-50">{isPl ? 'Twoja codzienna gra' : 'Your daily habit'}</h2>
        <span className="text-xs text-zinc-400">{modeName} · {isPl ? 'To urządzenie' : 'This device'}</span>
      </div>
      <dl className="mb-5 grid grid-cols-3 divide-x divide-white/10 text-center">
        <div className="min-w-0 px-1">
          <dt className="text-xs text-zinc-400">{isPl ? 'Aktualna seria' : 'Current streak'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-emerald-400">{history.currentStreak}<span className="text-xs text-zinc-500"> {isPl ? (history.currentStreak === 1 ? 'dzień' : 'dni') : (history.currentStreak === 1 ? 'day' : 'days')}</span></dd>
        </div>
        <div className="min-w-0 px-1">
          <dt className="text-xs text-zinc-400">{isPl ? 'Rozwiązane' : 'Solved'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-sand-100">{history.solved}</dd>
        </div>
        <div className="min-w-0 px-1">
          <dt className="text-xs text-zinc-400">{isPl ? 'Najlepszy wynik' : 'Best score'}</dt>
          <dd className="mt-1 break-words font-mono text-xl text-sand-100">{history.bestScore === null ? '—' : history.bestScore.toLocaleString(locale)}</dd>
        </div>
      </dl>
      <ol aria-label={isPl ? 'Ostatnie siedem dni według UTC' : 'Last seven UTC days'} className="grid grid-cols-7 gap-1.5">
        {history.days.map(day => (
          <li key={day.date} aria-label={`${day.date}${day.date === today ? (isPl ? ', dzisiaj' : ', today') : ''}: ${labels[day.status]}`} className="min-w-0 text-center">
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
      <p className="mt-2 text-xs leading-relaxed text-zinc-500">{isPl
        ? '✓ rozwiązane · × nierozwiązane · — bez gry. Nowy dzień zaczyna się o 00:00 UTC.'
        : 'Check: solved · Cross: not solved · Dash: not played. Days reset at 00:00 UTC.'}</p>
      <p className={`mt-4 text-xs leading-relaxed ${history.storageAvailable ? 'text-zinc-400' : 'text-amber-300'}`}>
        {history.storageAvailable
          ? (isPl
            ? 'Historia gościa pozostaje w tej przeglądarce na tym urządzeniu, także po zalogowaniu. Usunięcie danych przeglądarki usuwa historię.'
            : 'Guest history stays in this browser on this device, including after sign-in. Clearing browser data removes it.')
          : (isPl
            ? 'Pamięć przeglądarki jest niedostępna lub pełna. Nowy postęp może nie zostać zapisany; pokazujemy tylko historię, którą przeglądarka nadal może odczytać.'
            : 'Browser storage is unavailable or full. New progress may not be saved; any history shown is only what this browser can still read.')}
      </p>
    </section>
  );
}
