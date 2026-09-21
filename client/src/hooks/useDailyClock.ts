import { useSyncExternalStore } from 'react';
import { timeService } from '../services/api';

interface DailyClock {
  today: string;
  remainingSeconds: number | null;
  nextGameAt: string | null;
}

const dayMilliseconds = 24 * 60 * 60 * 1000;
const listeners = new Set<() => void>();
let snapshot: DailyClock = {
  today: new Date().toISOString().slice(0, 10),
  remainingSeconds: null,
  nextGameAt: null,
};
let serverAnchor = Date.now();
let elapsedAnchor = performance.now();
let nextGameTime = 0;
let interval: number | undefined;
let syncing = false;

function publishTime() {
  const now = serverAnchor + performance.now() - elapsedAnchor;
  const crossedMidnight = nextGameTime > 0 && now >= nextGameTime;
  if (!nextGameTime || crossedMidnight) {
    nextGameTime = (Math.floor(now / dayMilliseconds) + 1) * dayMilliseconds;
  }
  const today = new Date(now).toISOString().slice(0, 10);
  const remainingSeconds = Math.max(0, Math.ceil((nextGameTime - now) / 1000));
  const nextGameAt = new Date(nextGameTime).toISOString();
  if (today !== snapshot.today || remainingSeconds !== snapshot.remainingSeconds || nextGameAt !== snapshot.nextGameAt) {
    snapshot = { today, remainingSeconds, nextGameAt };
    listeners.forEach(listener => listener());
  }
  if (crossedMidnight) void synchronize();
}

async function synchronize() {
  if (syncing) return;
  syncing = true;
  try {
    const data = await timeService.getServerTime();
    const serverTime = Date.parse(data.server_time);
    const next = Date.parse(data.next_game_at);
    if (!Number.isFinite(serverTime) || !Number.isFinite(next) || next <= serverTime) return;
    serverAnchor = serverTime;
    elapsedAnchor = performance.now();
    nextGameTime = next;
  } catch {
    // Keep the monotonic clock running; before the first sync it uses local UTC.
  } finally {
    syncing = false;
    publishTime();
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') void synchronize();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) {
    publishTime();
    void synchronize();
    interval = window.setInterval(publishTime, 1000);
    window.addEventListener('focus', synchronize);
    document.addEventListener('visibilitychange', onVisibilityChange);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.clearInterval(interval);
      interval = undefined;
      window.removeEventListener('focus', synchronize);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
  };
}

const getSnapshot = () => snapshot;

export function useDailyClock(): DailyClock {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

const getDateSnapshot = () => snapshot.today;

export function useDailyDate(): string {
  return useSyncExternalStore(subscribe, getDateSnapshot, getDateSnapshot);
}
