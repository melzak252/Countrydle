import { useLocation } from 'react-router-dom';
import { useDailyClock } from '../hooks/useDailyClock';
import { isPrerenderCapture } from '../lib/pageMetadata'

export interface CountdownTimerProps {
  label?: string;
  variant?: 'navbar' | 'minimal';
  className?: string;
}

export default function CountdownTimer(props: CountdownTimerProps) {
  if (isPrerenderCapture()) {
    return (
      <span className={`text-xs text-zinc-400 ${props.className ?? ''}`}>
        New daily puzzles at 00:00 UTC
      </span>
    );
  }
  return <LiveCountdownTimer {...props} />;
}

function LiveCountdownTimer({
  label,
  variant = 'navbar',
  className = '',
}: CountdownTimerProps) {
  const { remainingSeconds } = useDailyClock();
  const location = useLocation();
  

  if (remainingSeconds === null) return null;

  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  const timeLeft = [hours, minutes, seconds].map((v) => v.toString().padStart(2, '0')).join(':');

  if (variant === 'minimal') {
    return (
      <span className={`font-mono tabular-nums ${className}`} title={'Time until next puzzle (00:00 UTC)'}>
        {timeLeft}
      </span>
    );
  }

  // Determine clean, human label
  const getLabel = () => {
    if (label) return label;
    const path = location.pathname;
    if (path.startsWith('/us-states')) return 'New state in';
    if (path.startsWith('/wojewodztwa')) return 'New voivodeship in';
    if (path.startsWith('/powiaty')) return 'New county in';
    if (path.startsWith('/flagdle')) return 'New flag in';
    return 'New country in';
  };

  const displayLabel = getLabel();

  return (
    <div
      className={`flex items-center gap-2 border border-white/10 bg-white/[0.02] px-2.5 py-1 sm:px-3 sm:py-1.5 rounded font-mono text-xs ${className}`}
      title={'Time until next daily puzzle (00:00 UTC)'}
    >
      <span className="text-zinc-400 whitespace-nowrap">{displayLabel}:</span>
      <span className="text-sand-50 font-bold tabular-nums text-sm sm:text-base tracking-wide whitespace-nowrap">
        {timeLeft}
      </span>
    </div>
  );
}
