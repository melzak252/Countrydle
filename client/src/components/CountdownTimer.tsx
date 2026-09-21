import { Timer } from 'lucide-react';
import { useDailyClock } from '../hooks/useDailyClock';

export default function CountdownTimer() {
  const { remainingSeconds } = useDailyClock();
  if (remainingSeconds === null) return null;

  const hours = Math.floor(remainingSeconds / 3600);
  const minutes = Math.floor((remainingSeconds % 3600) / 60);
  const seconds = remainingSeconds % 60;
  const timeLeft = [hours, minutes, seconds].map(value => value.toString().padStart(2, '0')).join(':');

  return (
    <div className="flex items-center gap-1.5 font-mono text-xs text-zinc-400" title="Time until next daily puzzle (00:00 UTC)">
      <Timer size={14} aria-hidden="true" />
      <span className="whitespace-nowrap tabular-nums text-zinc-300">{timeLeft}</span>
    </div>
  );
}
