import { useEffect, useState } from 'react';
import { emptyGuestHistory, getGuestHistory, GUEST_HISTORY_EVENT } from '../lib/guestHistory';
import type { GuestGameType, GuestHistory } from '../lib/guestHistory';

export function useGuestHistory(gameType: GuestGameType, today: string): GuestHistory {
  const [snapshot, setSnapshot] = useState<{ gameType: GuestGameType; today: string; history: GuestHistory } | null>(null);

  useEffect(() => {
    const refresh = () => {
      setSnapshot({ gameType, today, history: getGuestHistory(gameType, today) });
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === null || event.key.startsWith(`guess_game_${gameType}_`)
        || event.key.startsWith(`countrydle_guest_result_v1_${gameType}_`)) refresh();
    };
    window.addEventListener(GUEST_HISTORY_EVENT, refresh);
    window.addEventListener('storage', onStorage);
    refresh();
    return () => {
      window.removeEventListener(GUEST_HISTORY_EVENT, refresh);
      window.removeEventListener('storage', onStorage);
    };
  }, [gameType, today]);

  return snapshot?.gameType === gameType && snapshot.today === today
    ? snapshot.history
    : emptyGuestHistory(today);
}
