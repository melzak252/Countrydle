import { expect, spyOn, test } from 'bun:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';
import PowiatHeraldryPage from '../src/pages/PowiatHeraldryPage';
import { countyFlagsService } from '../src/services/api';
import { useAuthStore } from '../src/stores/authStore';

test('publisher capture does not create or synchronize a county flag challenge', async () => {
  const dom = new TestWindow({ url: 'http://localhost/flagi-powiatow' });
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { value: true });
  const globals: Record<string, unknown> = { window: dom, document: dom.document, navigator: dom.navigator, localStorage: dom.localStorage, HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node, IS_REACT_ACT_ENVIRONMENT: true };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  const auth = useAuthStore.getState();
  useAuthStore.setState({ isLoading: false, isAuthenticated: true });
  const counties = spyOn(countyFlagsService, 'getCounties').mockResolvedValue([]);
  const challenge = spyOn(countyFlagsService, 'getChallenge');
  const sync = spyOn(countyFlagsService, 'sync');
  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  try {
    await act(async () => { root.render(<MemoryRouter><PowiatHeraldryPage flags /></MemoryRouter>); });
    expect(challenge).not.toHaveBeenCalled();
    expect(sync).not.toHaveBeenCalled();
  } finally {
    await act(async () => root.unmount());
    counties.mockRestore(); challenge.mockRestore(); sync.mockRestore();
    useAuthStore.setState(auth);
    await dom.happyDOM.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
});
