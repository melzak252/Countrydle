import { useState, useEffect } from 'react';
import { Timer } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { timeService } from '../services/api';

export default function CountdownTimer() {
  const [timeLeft, setTimeLeft] = useState('');
  const [nextGameTime, setNextGameTime] = useState<Date | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    // Fetch server time to synchronize
    const syncTime = async () => {
      try {
        const data = await timeService.getServerTime();
        setNextGameTime(new Date(data.next_game_at));
      } catch (error) {
        console.error("Failed to sync time with server:", error);
        // Fallback to local midnight if server sync fails
        const now = new Date();
        const tomorrow = new Date(now);
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(0, 0, 0, 0);
        setNextGameTime(tomorrow);
      }
    };

    syncTime();
  }, []);

  useEffect(() => {
    if (!nextGameTime) return;

    const calculateTimeLeft = () => {
      const now = new Date();
      const diff = nextGameTime.getTime() - now.getTime();

      if (diff <= 0) {
        // If time passed, maybe refresh page or re-sync?
        // For now just show 00:00:00
        return "00:00:00";
      }

      const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
      const minutes = Math.floor((diff / (1000 * 60)) % 60);
      const seconds = Math.floor((diff / 1000) % 60);

      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    };

    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);

    setTimeLeft(calculateTimeLeft());

    return () => clearInterval(timer);
  }, [nextGameTime]);

  if (!timeLeft) return null;

  return (
    <div className="hidden lg:flex items-center gap-2 text-zinc-400 font-mono text-sm bg-zinc-800/50 px-3 py-1.5 rounded-md border border-zinc-700/50" title={t('countdown.title')}>
      <Timer size={14} />
      <span className="text-zinc-200 font-bold">{timeLeft}</span>
    </div>
  );
}
