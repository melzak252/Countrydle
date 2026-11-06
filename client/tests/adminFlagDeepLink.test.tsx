import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Window as TestWindow } from 'happy-dom';
import axios from 'axios';
import { adminService, timeService } from '../src/services/api';
import { useAuthStore } from '../src/stores/authStore';

test('restoring an administrator keeps the county flag session deep link', async () => {
  const dom = new TestWindow({ url: 'http://localhost/admin?tab=sessions&mode=county_flags_quiz&date=2026-11-06' });
  const globals: Record<string, unknown> = { window: dom, document: dom.document, navigator: dom.navigator, localStorage: dom.localStorage, history: dom.history, location: dom.location, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, __APP_VERSION__: 'test', IS_REACT_ACT_ENVIRONMENT: true };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  dom.localStorage.setItem('user', JSON.stringify({ id: 10, username: 'admin', is_admin: true }));
  // Leaflet reads window at module load, so install the test DOM before importing App.
  const { default: App } = await import('../src/App');
  const auth = useAuthStore.getState();
  useAuthStore.setState(useAuthStore.getInitialState());
  const sessions = spyOn(adminService, 'getGameSessions').mockRejectedValue(new Error('offline'));
  const stats = spyOn(adminService, 'getTargetStrategyStats').mockRejectedValue(new Error('offline'));
  const version = spyOn(axios, 'get').mockResolvedValue({ data: { version: 'test' } });
  const time = spyOn(timeService, 'getServerTime').mockResolvedValue({ server_time: '2026-11-06T12:00:00Z', next_game_at: '2026-11-07T00:00:00Z' });
  const container = dom.document.createElement('div'); dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  try {
    await act(async () => { root.render(<App />); });
    expect(dom.location.pathname).toBe('/admin');
    expect(dom.location.search).toBe('?tab=sessions&mode=county_flags_quiz&date=2026-11-06');
    const mode = Array.from(container.querySelectorAll('select')).find(select => Array.from(select.options).some(option => option.value === 'county_flags_quiz'));
    expect(mode?.value).toBe('county_flags_quiz');
    expect(container.querySelector('input[type="date"]')?.getAttribute('value')).toBe('2026-11-06');
  } finally {
    await act(async () => root.unmount());
    sessions.mockRestore(); stats.mockRestore(); version.mockRestore(); time.mockRestore(); useAuthStore.setState(auth);
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
});
