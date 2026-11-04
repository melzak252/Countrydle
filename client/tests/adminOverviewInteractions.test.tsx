import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Window as TestWindow } from 'happy-dom';
import AdminOverviewTab, { type AdminOverviewData } from '../src/components/admin/AdminOverviewTab';
import { adminService } from '../src/services/api';

import type { CountryCostReport } from '../src/types/countryCostReport';
const overview: AdminOverviewData = {
  date: '2026-10-01',
  today: { total_players: 3, total_sessions: 4, total_questions: 1, total_guesses: 2, total_winners: 1, win_rate_pct: 25 },
  modes_today: [{ mode_key: 'continental:asia', mode_label: 'Asia', target_name: 'Example', players: 2, sessions: 2, winners: 1, win_rate_pct: 50, questions: 1, guesses: 2 }],
  history_14d: [],
};

test('refresh recovers an unavailable cost report', async () => {
  const dom = new TestWindow({ url: 'http://localhost/' });
  const globals: Record<string, unknown> = { window: dom, document: dom.document, navigator: dom.navigator, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, IS_REACT_ACT_ENVIRONMENT: true };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const costs = spyOn(adminService, 'getCountrydleCosts');
  costs.mockRejectedValueOnce(new Error('offline'));
  costs.mockResolvedValueOnce({ days: [{ day: '2026-09-30', cost_lower_usd: 1.25, cost_upper_usd: 1.25, cost_status: 'complete' }], period_utc: { start: '2026-09-30', end: '2026-09-30' } } as CountryCostReport);
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  try {
    await act(async () => { root.render(<AdminOverviewTab overview={overview} isLoading={false} error={null} onRefresh={() => {}} onOpenCosts={() => {}} onOpenSessions={() => {}} />); });
    expect(container.textContent).toContain('Unavailable');
    const refresh = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('refresh') || button.textContent?.includes('Refresh'))!;
    await act(async () => { refresh.click(); });
    expect(container.textContent).toContain('$1.2500');
    expect(container.textContent).toContain('2026-09-30 UTC');
  } finally {
    await act(async () => root.unmount());
    costs.mockRestore();
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
});
