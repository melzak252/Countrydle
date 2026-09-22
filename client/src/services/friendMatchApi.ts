import axios from 'axios';
import api, { API_URL } from './api';
import type { FriendAction, FriendEntity, FriendHistoryPage, FriendInvite, FriendMode, FriendSnapshot } from '../types/friendMatch';

const root = '/friend-matches';
const segment = encodeURIComponent;

let sessionQueue: Promise<void> = Promise.resolve();

async function prepareFriendSession(): Promise<void> {
  const bootstrap = async () => {
    await api.post(`${root}/session`, {}, { timeout: 15000 });
  };
  // The cookie is HttpOnly: always ask the server to reuse or establish it.
  // Wait for Set-Cookie before releasing the same-origin cross-tab lock.
  if (navigator.locks) {
    await navigator.locks.request('countrydle-friend-session', bootstrap);
    return;
  }
  // Older/non-secure browsers still support single-tab play without storage.
  // Cross-tab serialization is available only where Web Locks are supported.
  const pending = sessionQueue.then(bootstrap);
  sessionQueue = pending.catch(() => {});
  await pending;
}

export const friendMatchApi = {
  async entities(mode: FriendMode): Promise<FriendEntity[]> {
    return (await api.get<{ entities: FriendEntity[] }>(`${root}/entities`, { params: { mode }, timeout: 15000 })).data.entities;
  },
  async create(body: { name: string; mode: FriendMode; request_id: string }): Promise<FriendSnapshot> {
    await prepareFriendSession();
    return (await api.post<FriendSnapshot>(root, body, { timeout: 15000 })).data;
  },
  async invite(code: string): Promise<FriendInvite> {
    return (await api.get<FriendInvite>(`${root}/invites/${segment(code)}`, { timeout: 15000 })).data;
  },
  async join(code: string, body: { name: string; request_id: string }): Promise<FriendSnapshot> {
    await prepareFriendSession();
    return (await api.post<FriendSnapshot>(`${root}/invites/${segment(code)}/join`, body, { timeout: 15000 })).data;
  },
  async snapshot(id: string): Promise<FriendSnapshot> {
    return (await api.get<FriendSnapshot>(`${root}/${segment(id)}`, { timeout: 15000 })).data;
  },
  async action(id: string, action: FriendAction): Promise<FriendSnapshot> {
    return (await api.post<FriendSnapshot>(`${root}/${segment(id)}/actions`, action, { timeout: 15000 })).data;
  },
  async history(id: string, before: number): Promise<FriendHistoryPage> {
    return (await api.get<FriendHistoryPage>(`${root}/${segment(id)}/history`, { params: { before }, timeout: 15000 })).data;
  },
  async report(id: string, questionId: string, comment: string): Promise<void> {
    await api.post(`${root}/${segment(id)}/questions/${segment(questionId)}/reports`, { comment }, { timeout: 15000 });
  },
  socketUrl(id: string): string {
    const url = new URL(`${API_URL.replace(/\/$/, '')}${root}/${segment(id)}/ws`, window.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.toString();
  },
};

export function friendError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return error instanceof Error ? error.message : fallback;
  const detail: unknown = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') return detail.message;
  return fallback;
}

export function friendStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

export function uncertainFriendRequest(error: unknown): boolean {
  const status = friendStatus(error);
  return status === undefined || status >= 500 || status === 408;
}

export function friendRequestId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
