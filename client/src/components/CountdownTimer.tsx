import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useDailyClock } from '../hooks/useDailyClock';

export interface CountdownTimerProps {
  label?: string;
  variant?: 'navbar' | 'minimal';
  className?: string;
}

export default function CountdownTimer({
  label,
  variant = 'navbar',
  className = '',
}: CountdownTimerProps) {
  const { remainingSeconds } = useDailyClock();
  const location = useLocation();
  const { i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');

  if (remainingSeconds === null) return null;

  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  const timeLeft = [hours, minutes, seconds].map((v) => v.toString().padStart(2, '0')).join(':');

  if (variant === 'minimal') {
    return (
      <span className={`font-mono tabular-nums ${className}`} title={isPl ? 'Czas do kolejnej zagadki (00:00 UTC)' : 'Time until next puzzle (00:00 UTC)'}>
        {timeLeft}
      </span>
    );
  }

  // Determine clean, human label
  const getLabel = () => {
    if (label) return label;
    const path = location.pathname;
    if (path.startsWith('/us-states')) return isPl ? 'Nowy stan za' : 'New state in';
    if (path.startsWith('/wojewodztwa')) return isPl ? 'Nowe woj. za' : 'New voivodeship in';
    if (path.startsWith('/powiaty')) return isPl ? 'Nowy powiat za' : 'New county in';
    if (path.startsWith('/flagdle')) return isPl ? 'Nowa flaga za' : 'New flag in';
    return isPl ? 'Nowe państwo za' : 'New country in';
  };

  const displayLabel = getLabel();

  return (
    <div
      className={`flex items-center gap-2 border border-white/10 bg-white/[0.02] px-2.5 py-1 sm:px-3 sm:py-1.5 rounded font-mono text-xs ${className}`}
      title={isPl ? 'Czas do kolejnej zagadki (00:00 UTC)' : 'Time until next daily puzzle (00:00 UTC)'}
    >
      <span className="text-zinc-400 whitespace-nowrap">{displayLabel}:</span>
      <span className="text-sand-50 font-bold tabular-nums text-sm sm:text-base tracking-wide whitespace-nowrap">
        {timeLeft}
      </span>
    </div>
  );
}
