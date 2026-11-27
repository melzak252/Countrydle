import { expect, test } from 'bun:test';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { Window as TestWindow } from 'happy-dom';

function CurrentPath() {
  const { pathname } = useLocation();
  return <output data-testid="current-path">{pathname}</output>;
}

function setup() {
  const dom = new TestWindow({ url: 'http://localhost/' });
  Object.defineProperty(dom.HTMLElement.prototype, 'attachEvent', { configurable: true, value: () => {} });
  Object.defineProperty(dom.HTMLElement.prototype, 'detachEvent', { configurable: true, value: () => {} });
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries({
    window: dom,
    document: dom.document,
    navigator: dom.navigator,
    localStorage: dom.localStorage,
    HTMLElement: dom.HTMLElement,
    Element: dom.Element,
    Node: dom.Node,
    IS_REACT_ACT_ENVIRONMENT: true,
  })) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }

  const container = dom.document.createElement('div');
  dom.document.body.appendChild(container);
  const root = createRoot(container as unknown as HTMLElement);
  return {
    dom,
    container,
    root,
    async dispose() {
      await act(async () => root.unmount());
      await dom.happyDOM.close();
      for (const [name, descriptor] of previous) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else Reflect.deleteProperty(globalThis, name);
      }
    },
  };
}

async function renderHeader(root: Root) {
  // Header's privacy/advertising imports read the DOM during module evaluation.
  const { default: Header } = await import('../src/components/Header');
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={['/game']}>
        <Header />
        <CurrentPath />
      </MemoryRouter>,
    );
  });
}

function findExploreMoreLink(nav: ParentNode) {
  return [...nav.querySelectorAll('a')].find((link) => link.textContent?.trim().startsWith('Explore more'))!;
}

test('desktop Explore more link opens the Explore view', async () => {
  const { dom, container, root, dispose } = setup();
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
  try {
    await renderHeader(root);
    const nav = container.querySelector('nav[aria-label="Main navigation"]')!;
    nav.querySelector('summary[aria-label="Choose a game"]')!.closest('details')!.setAttribute('open', '');
    const exploreMore = findExploreMoreLink(nav);

    await act(async () => {
      exploreMore.dispatchEvent(new dom.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
    });

    expect(container.querySelector('[data-testid="current-path"]')?.textContent).toBe('/explore');
  } finally {
    await dispose();
  }
});

test('mobile Explore more link opens the Explore view', async () => {
  const { dom, container, root, dispose } = setup();
  Object.defineProperty(dom, '__COUNTRYDLE_PRERENDER__', { configurable: true, value: true });
  try {
    await renderHeader(root);
    const menuButton = container.querySelector('button[aria-label="Navigation menu"]')!;
    await act(async () => {
      menuButton.dispatchEvent(new dom.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
    });
    const nav = dom.document.querySelector('nav[aria-label="Mobile navigation"]')!;
    nav.querySelector('summary[aria-label="Choose a game"]')!.closest('details')!.setAttribute('open', '');
    const exploreMore = findExploreMoreLink(nav);

    await act(async () => {
      exploreMore.dispatchEvent(new dom.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
    });

    expect(container.querySelector('[data-testid="current-path"]')?.textContent).toBe('/explore');
  } finally {
    await dispose();
  }
});
