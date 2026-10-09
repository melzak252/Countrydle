import { expect, spyOn, test } from 'bun:test';
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { act, createElement } from 'react';
import type { ComponentType } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { createInstance } from 'i18next';
import { I18nextProvider } from 'react-i18next';
import { Window as TestWindow } from 'happy-dom';
import type { HTMLDivElement as TestContainer, Node as TestNode } from 'happy-dom';
import toast, { useToasterStore } from 'react-hot-toast';
import type * as PolicyModule from '../src/advertising';

type Policy = typeof PolicyModule;
type ConsentCallback = Parameters<NonNullable<Window['__tcfapi']>>[2];
type ConsentData = Parameters<ConsentCallback>[0];
interface Navigation {
  method: 'reload' | 'assign' | 'replace';
  url: string;
}
interface HistoryCall {
  method: string;
  url: string;
}
interface PolicyFixture {
  dom: TestWindow;
  browser: Window;
  policy: Policy;
  container: TestContainer;
  navigation: Navigation[];
  historyCalls: HistoryCall[];
  readonly requests: number;
  readonly subscriptions: number;
  readonly settingsOpened: number;
  readyCMP(): void;
  mount(privacy?: boolean, advertising?: boolean): Promise<void>;
  emitConsent(data: ConsentData, success?: boolean): Promise<void>;
  loadSDK(): Promise<void>;
  startAds(): Promise<void>;
  clickPrivacy(): Promise<void>;
  failCMP(): Promise<void>;
  advanceTime(milliseconds: number): void;
  traverse(url: string): Promise<void>;
  dispose(): Promise<void>;
}
const clientRoot = resolve(import.meta.dir, '..');
const publisher = 'ca-pub-1111111111111111';
const unavailable = 'Privacy settings could not open. No settings were changed.';

// Load a fresh real policy for each scenario without mock.module, shared module-cache
// resets, process.env changes, or replacing any of its React hooks.
async function withPolicy(path: string, run: (fixture: PolicyFixture) => Promise<void>, options: { controlledTimers?: boolean } = {}) {
  const fixture = await createFixture(path, options.controlledTimers);
  try {
    await run(fixture);
  } finally {
    await fixture.dispose();
  }
}

async function createFixture(path: string, controlledTimers = false): Promise<PolicyFixture> {
  const dom = new TestWindow({
    url: `https://countrydle.test${path}`,
    settings: {
      enableJavaScriptEvaluation: false,
      disableJavaScriptFileLoading: true,
      disableCSSFileLoading: true,
      disableIframePageLoading: true,
    },
  });
  const browser = dom as unknown as Window;
  const globals: Record<string, unknown> = {
    window: browser, document: dom.document, navigator: dom.navigator,
    HTMLElement: dom.HTMLElement, Element: dom.Element, Node: dom.Node,
    Event: dom.Event, MouseEvent: dom.MouseEvent, IS_REACT_ACT_ENVIRONMENT: true,
  };
  const previous = new Map<string, PropertyDescriptor | undefined>();
  for (const [name, value] of Object.entries(globals)) {
    previous.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  let clock = 0;
  let nextTimer = 0;
  const timeouts = new Map<number, { at: number; run: () => void }>();
  // Only the policy's window timers are controlled. Bun's supported spies leave
  // React act, toast scheduling and Happy DOM's host task manager on real timers.
  const clockSetTimeout = controlledTimers ? spyOn(browser, 'setTimeout').mockImplementation((handler, delay = 0, ...args) => {
    if (typeof handler !== 'function') throw new Error('The fixture clock requires a function callback.');
    const id = ++nextTimer;
    timeouts.set(id, { at: clock + Math.max(0, delay), run: () => { handler(...args); } });
    return id;
  }) : undefined;
  const clockClearTimeout = controlledTimers ? spyOn(browser, 'clearTimeout').mockImplementation(id => {
    if (id !== undefined) timeouts.delete(id);
  }) : undefined;
  dom.document.head.innerHTML = `<meta name="google-adsense-account" content="${publisher}">`;
  // Keep external provider scripts inert; tests deliver only disposable load/error
  // callbacks themselves, never a network request or provider implementation.
  const appendHeadChild = dom.document.head.appendChild.bind(dom.document.head);
  Object.defineProperty(dom.document.head, 'appendChild', {
    configurable: true,
    value: (node: TestNode) => {
      if (node instanceof dom.HTMLScriptElement) node.type = 'application/x-countrydle-test';
      return appendHeadChild(node);
    },
  });

  const navigation: Navigation[] = [];
  for (const method of ['reload', 'assign', 'replace'] as const) {
    Object.defineProperty(dom.location, method, {
      configurable: true,
      value: (url?: string) => navigation.push({ method, url: url || dom.location.href }),
    });
  }
  const historyCalls: HistoryCall[] = [];
  const nativeReplace = dom.history.replaceState.bind(dom.history);
  for (const method of ['pushState', 'replaceState'] as const) {
    const original = dom.history[method].bind(dom.history);
    dom.history[method] = (state, unused, url) => {
      historyCalls.push({ method, url: String(url) });
      original(state, unused, url);
    };
  }

  let bundleDirectory: string | undefined;
  let root: Root | undefined;
  toast.remove();
  async function dispose() {
    // Restore before any asynchronous unmount/close work, including failed tests.
    clockSetTimeout?.mockRestore();
    clockClearTimeout?.mockRestore();
    timeouts.clear();
    try {
      await act(async () => { root?.unmount(); toast.remove(); });
    } finally {
      // Each fixture owns a unique on-disk module graph, not global runtime plugins
      // or module mocks that can interfere with unrelated tests in this process.
      try {
        await dom.happyDOM.close();
      } finally {
        try {
          if (bundleDirectory) await rm(bundleDirectory, { recursive: true, force: true });
        } finally {
          for (const [name, descriptor] of previous) {
            if (descriptor) Object.defineProperty(globalThis, name, descriptor);
            else Reflect.deleteProperty(globalThis, name);
          }
        }
      }
    }
  }
  try {
    // Keep bare package externals under the client's real dependency-resolution
    // tree: Bun target:bun can emit bare names even for absolute external paths.
    const bundleCache = resolve(clientRoot, 'node_modules/.cache');
    await mkdir(bundleCache, { recursive: true });
    bundleDirectory = await mkdtemp(join(bundleCache, 'countrydle-policy-test-'));
    const sourceRoot = resolve(clientRoot, 'src');
    const bundle = await Bun.build({
      entrypoints: [
        resolve(sourceRoot, 'advertising.ts'),
        resolve(sourceRoot, 'components/AdSenseUnit.tsx'),
        resolve(sourceRoot, 'components/PrivacySettingsButton.tsx'),
      ],
      root: sourceRoot,
      outdir: bundleDirectory,
      naming: '[dir]/[name].[ext]',
      target: 'bun',
      format: 'esm',
      // All three entries must reference the same fresh policy instance.
      splitting: true,
      define: {
        'import.meta.env.VITE_GOOGLE_ADSENSE_ID': JSON.stringify(publisher),
        'import.meta.env.VITE_ADSENSE_ENABLED': '"true"',
        'import.meta.env.VITE_ADSENSE_SLOTS': JSON.stringify('{"journal":"1234567890"}'),
      },
      // Use the same installed real React/router/i18n/toast graph as this test.
      // Ordinary package resolution works because output remains client-local.
      packages: 'external',
    });
    if (!bundle.success) throw new AggregateError(bundle.logs, 'Could not bundle the real advertising policy fixture.');
    // Static imports cannot isolate the policy's module state between scenarios;
    // these module paths are freshly generated for each fixture at runtime.
    const policy: Policy = await import(resolve(bundleDirectory, 'advertising.js'));
    const { default: AdSenseUnit }: { default: ComponentType<{ slot: string }> } = await import(resolve(bundleDirectory, 'components/AdSenseUnit.js'));
    const { PrivacySettingsButton }: { PrivacySettingsButton: ComponentType } = await import(resolve(bundleDirectory, 'components/PrivacySettingsButton.js'));
    const i18n = createInstance();
    await i18n.init({ lng: 'en', resources: { en: { translation: { privacySettings: { label: 'Privacy settings', unavailable } } } } });
    const container = dom.document.createElement('div');
    dom.document.body.appendChild(container);
    let consentCallback: ConsentCallback | undefined;
    let requests = 0;
    let settingsOpened = 0;
    let subscriptions = 0;

    function readyCMP() {
      browser.googlefc = { callbackQueue: browser.googlefc?.callbackQueue || [], showRevocationMessage: () => { settingsOpened += 1; } };
      browser.__tcfapi = (_command, _version, callback) => { subscriptions += 1; consentCallback = callback; };
    }
    function ToastMessages() {
      const { toasts } = useToasterStore();
      return createElement('output', { 'data-visible-toasts': true },
        toasts.filter(message => message.visible).map(message => String(message.message)).join('\n'));
    }
    async function mount(privacy = false, advertising = !privacy) {
      await act(async () => {
        root = createRoot(container as unknown as HTMLElement);
        root.render(createElement(BrowserRouter, { window: browser },
          createElement(I18nextProvider, { i18n }, createElement('div', null,
            advertising ? createElement(AdSenseUnit, { slot: 'journal' }) : null,
            privacy ? createElement(PrivacySettingsButton) : null,
            privacy ? createElement(ToastMessages) : null))));
      });
    }
    async function emitConsent(data: ConsentData, success = true) {
      if (!consentCallback) throw new Error('The policy did not subscribe to the CMP.');
      await act(async () => { consentCallback!(data, success); });
    }
    async function loadSDK() {
      const script = dom.document.getElementById('countrydle-adsense');
      expect(script).not.toBeNull();
      browser.adsbygoogle = { push: () => { requests += 1; } };
      await act(async () => { script!.dispatchEvent(new dom.Event('load')); });
    }
    async function startAds() {
      readyCMP();
      policy.initializeAdvertisingPolicy();
      policy.setPageEditorialEligibility(true);
      await mount();
      await emitConsent({ gdprApplies: false });
      await loadSDK();
      expect(container.querySelectorAll('ins.adsbygoogle')).toHaveLength(1);
      expect(requests).toBe(1);
      historyCalls.length = 0;
    }
    async function clickPrivacy() {
      const button = container.querySelector('button');
      expect(button).not.toBeNull();
      await act(async () => { button!.dispatchEvent(new dom.MouseEvent('click', { bubbles: true })); });
    }
    async function failCMP() {
      const script = dom.document.getElementById('countrydle-funding-choices');
      expect(script).not.toBeNull();
      await act(async () => { script!.dispatchEvent(new dom.Event('error')); });
    }

    return {
      dom, browser, policy, container, navigation, historyCalls,
      readyCMP, mount, emitConsent, loadSDK, startAds, clickPrivacy, failCMP,
      advanceTime(milliseconds: number) {
        if (!controlledTimers) throw new Error('Window timer control is not enabled for this fixture.');
        const target = clock + milliseconds;
        while (true) {
          let next: number | undefined;
          let earliest = Infinity;
          for (const [id, timer] of timeouts) {
            if (timer.at <= target && timer.at < earliest) {
              next = id;
              earliest = timer.at;
            }
          }
          if (next === undefined) break;
          const timer = timeouts.get(next)!;
          timeouts.delete(next);
          clock = timer.at;
          timer.run();
        }
        clock = target;
      },
      get requests() { return requests; },
      get settingsOpened() { return settingsOpened; },
      get subscriptions() { return subscriptions; },
      // A native traversal changes the address before popstate and never calls the
      // intercepted application methods. Keep that browser ordering deterministic.
      async traverse(url: string) {
        await act(async () => {
          nativeReplace(dom.history.state, '', url);
          dom.dispatchEvent(new dom.PopStateEvent('popstate', { state: dom.history.state }));
        });
      },
      dispose,
    };
  } catch (error) {
    await dispose();
    throw error;
  }
}

test('a successful standard non-GDPR four-field response authorizes a rendered ad and its unit request', async () => {
  await withPolicy('/blog', async fixture => {
    fixture.readyCMP();
    fixture.policy.initializeAdvertisingPolicy();
    fixture.policy.setPageEditorialEligibility(true);
    await fixture.mount();
    expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
    await fixture.emitConsent({ gdprApplies: false, tcString: '', cmpId: 7, listenerId: 1 } as ConsentData);
    await fixture.loadSDK();
    expect(fixture.container.querySelector('ins.adsbygoogle')?.getAttribute('data-ad-slot')).toBe('1234567890');
    expect(fixture.requests).toBe(1);
  });
});

test('GDPR advertising still requires all affirmative Google purpose and vendor bases', async () => {
  await withPolicy('/blog', async fixture => {
    fixture.readyCMP();
    fixture.policy.initializeAdvertisingPolicy();
    fixture.policy.setPageEditorialEligibility(true);
    await fixture.mount();
    await fixture.emitConsent({
      gdprApplies: true, cmpStatus: 'loaded', eventStatus: 'useractioncomplete', tcString: 'fixture-consent',
      purpose: { consents: { 1: true, 2: true, 3: true, 4: true, 7: true, 9: true, 10: true } },
      vendor: { consents: { 755: true } },
    });
    await fixture.loadSDK();
    expect(fixture.container.querySelector('ins.adsbygoogle')).not.toBeNull();
    expect(fixture.requests).toBe(1);
  });
});

for (const response of [
  { name: 'failed non-GDPR response', data: { gdprApplies: false }, success: false },
  { name: 'missing jurisdiction', data: { cmpStatus: 'loaded', eventStatus: 'tcloaded' }, success: true },
  { name: 'missing GDPR-only readiness fields', data: { gdprApplies: true }, success: true },
  { name: 'unknown response', data: {}, success: true },
  { name: 'denied GDPR consent', data: { gdprApplies: true, cmpStatus: 'loaded', eventStatus: 'useractioncomplete', tcString: 'denied' }, success: true },
]) {
  test(`${response.name} remains closed without loading or requesting advertising`, async () => {
    await withPolicy('/blog', async fixture => {
      fixture.readyCMP();
      fixture.policy.initializeAdvertisingPolicy();
      fixture.policy.setPageEditorialEligibility(true);
      await fixture.mount();
      await fixture.emitConsent(response.data, response.success);
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.dom.document.getElementById('countrydle-adsense')).toBeNull();
      expect(fixture.requests).toBe(0);
    });
  });
}

for (const response of [
  { name: 'failed non-GDPR update', data: { gdprApplies: false }, success: false },
  { name: 'unknown update', data: {}, success: true },
]) {
  test(`${response.name} revokes an already-active unit and its document`, async () => {
    await withPolicy('/blog#sort', async fixture => {
      await fixture.startAds();
      await fixture.emitConsent(response.data, response.success);
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.navigation).toEqual([{ method: 'reload', url: 'https://countrydle.test/blog#sort' }]);
      expect(fixture.requests).toBe(1);
    });
  });
}

for (const path of ['/blog', '/blog#sort', '/blog?continent=Europe#sort']) {
  test(`revocation on ${path} hides units and reloads the document through original history, not fragment navigation`, async () => {
    await withPolicy(path, async fixture => {
      await fixture.startAds();
      await fixture.emitConsent({ gdprApplies: true, cmpStatus: 'loaded', eventStatus: 'useractioncomplete', tcString: 'denied' });
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.dom.document.getElementById('countrydle-adsense')).toBeNull();
      expect(fixture.navigation).toEqual([{ method: 'reload', url: `https://countrydle.test${path}` }]);
      expect(fixture.historyCalls).toEqual([{ method: 'replaceState', url: `https://countrydle.test${path}` }]);
      expect(fixture.requests).toBe(1);
    });
  });
}

test('loaded-content revocation on a fragment also forces a real document reload', async () => {
  await withPolicy('/blog#sort', async fixture => {
    await fixture.startAds();
    await act(async () => { fixture.policy.setPageEditorialEligibility(false); });
    expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
    expect(fixture.navigation).toEqual([{ method: 'reload', url: 'https://countrydle.test/blog#sort' }]);
    expect(fixture.historyCalls).toHaveLength(1);
  });
});

test('same-page sort and hash Back retain loaded editorial eligibility and the existing requested unit', async () => {
  await withPolicy('/blog', async fixture => {
    await fixture.startAds();
    const unit = fixture.container.querySelector('ins.adsbygoogle');
    await act(async () => { fixture.browser.history.pushState({ sort: 'recent' }, '', '/blog#sort'); });
    await act(async () => { fixture.browser.history.back(); });
    expect(fixture.dom.location.hash).toBe('');
    expect(fixture.container.querySelector('ins.adsbygoogle')).toBe(unit);
    expect(fixture.navigation).toEqual([]);
    expect(fixture.requests).toBe(1);
  });
});

for (const transition of [
  { method: 'pushState' as const, target: '/admin', navigation: 'assign' },
  { method: 'replaceState' as const, target: '/blog?continent=Asia', navigation: 'replace' },
]) {
  test(`${transition.method} to ${transition.target} retains the fresh-document ad boundary`, async () => {
    await withPolicy('/blog', async fixture => {
      await fixture.startAds();
      await act(async () => { fixture.browser.history[transition.method]({}, '', transition.target); });
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.navigation).toEqual([{ method: transition.navigation, url: `https://countrydle.test${transition.target}` }]);
      expect(fixture.historyCalls).toEqual([]);
      expect(fixture.requests).toBe(1);
    });
  });
}

for (const target of ['/admin', '/blog?continent=Asia']) {
  test(`Back across a path/query boundary to ${target} reloads the already-selected history entry`, async () => {
    await withPolicy('/blog', async fixture => {
      await fixture.startAds();
      await fixture.traverse(target);
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.navigation).toEqual([{ method: 'reload', url: `https://countrydle.test${target}` }]);
      expect(fixture.requests).toBe(1);
    });
  });
}

test('an immediate startup privacy failure survives mounting and retries clear, fail visibly, then recover', async () => {
  await withPolicy('/cookie-policy#privacy-settings', async fixture => {
    fixture.policy.initializeAdvertisingPolicy();
    await fixture.failCMP();
    await fixture.mount(true);
    const visibleMessages = () => fixture.container.querySelector('[data-visible-toasts]')?.textContent;
    expect(visibleMessages()).toContain(unavailable);
    expect(fixture.settingsOpened).toBe(0);

    await fixture.clickPrivacy();
    expect(visibleMessages()).not.toContain(unavailable);
    expect(fixture.container.querySelector('button')?.disabled).toBe(true);
    expect(fixture.dom.document.getElementById('countrydle-funding-choices')).not.toBeNull();
    await fixture.failCMP();
    expect(visibleMessages()).toContain(unavailable);
    expect(fixture.container.querySelector('button')?.disabled).toBe(false);

    fixture.readyCMP();
    await fixture.clickPrivacy();
    expect(visibleMessages()).not.toContain(unavailable);
    expect(fixture.container.querySelector('button')?.disabled).toBe(false);
    expect(fixture.settingsOpened).toBe(1);
  });
});

test('CMP readiness at eleven seconds recovers privacy state and subscribes automatically without reopening the timed-out request', async () => {
  await withPolicy('/blog', async fixture => {
    fixture.policy.initializeAdvertisingPolicy();
    fixture.policy.setPageEditorialEligibility(true);
    await fixture.mount(true, true);
    await fixture.clickPrivacy();
    const ready = fixture.browser.googlefc!.callbackQueue[0].CONSENT_API_READY;
    fixture.browser.setTimeout(() => { fixture.readyCMP(); ready(); }, 11000);

    await act(async () => { fixture.advanceTime(10000); });
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).toContain(unavailable);
    expect(fixture.container.querySelector('button')?.disabled).toBe(false);
    expect(fixture.subscriptions).toBe(0);
    expect(fixture.dom.document.getElementById('countrydle-adsense')).toBeNull();
    expect(fixture.requests).toBe(0);

    await act(async () => { fixture.advanceTime(1000); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).not.toContain(unavailable);
    expect(fixture.container.querySelector('button')?.disabled).toBe(false);
    expect(fixture.settingsOpened).toBe(0);
    // Readiness alone, and even a failed non-GDPR response, cannot authorize ads.
    await fixture.emitConsent({ gdprApplies: false }, false);
    expect(fixture.dom.document.getElementById('countrydle-adsense')).toBeNull();
    await fixture.emitConsent({ gdprApplies: false });
    await fixture.loadSDK();
    expect(fixture.container.querySelector('ins.adsbygoogle')).not.toBeNull();
    expect(fixture.requests).toBe(1);
    await act(async () => { ready(); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.settingsOpened).toBe(0);
    expect(fixture.requests).toBe(1);
  }, { controlledTimers: true });
});

test('an expired readiness callback after retry subscribes once without settling or reopening either privacy request', async () => {
  await withPolicy('/cookie-policy#privacy-settings', async fixture => {
    fixture.policy.initializeAdvertisingPolicy();
    await fixture.mount(true);
    const expiredReady = fixture.browser.googlefc!.callbackQueue[0].CONSENT_API_READY;
    await act(async () => { fixture.advanceTime(10000); });
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).toContain(unavailable);

    await fixture.clickPrivacy();
    expect(fixture.browser.googlefc!.callbackQueue).toHaveLength(2);
    const retryReady = fixture.browser.googlefc!.callbackQueue[1].CONSENT_API_READY;
    fixture.readyCMP();
    await act(async () => { expiredReady(); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.settingsOpened).toBe(0);
    expect(fixture.container.querySelector('button')?.disabled).toBe(true);
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).not.toContain(unavailable);

    await act(async () => { retryReady(); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.settingsOpened).toBe(1);
    expect(fixture.container.querySelector('button')?.disabled).toBe(false);
    await act(async () => { expiredReady(); retryReady(); fixture.advanceTime(10000); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.settingsOpened).toBe(1);
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).not.toContain(unavailable);
  }, { controlledTimers: true });
});

for (const failure of ['missing revocation API', 'missing consent API', 'throwing consent API'] as const) {
  test(`late readiness with a ${failure} remains unavailable and ad-free until working APIs arrive`, async () => {
    await withPolicy('/blog', async fixture => {
      fixture.policy.initializeAdvertisingPolicy();
      fixture.policy.setPageEditorialEligibility(true);
      await fixture.mount(true, true);
      await fixture.clickPrivacy();
      const ready = fixture.browser.googlefc!.callbackQueue[0].CONSENT_API_READY;
      await act(async () => { fixture.advanceTime(10000); });
      fixture.readyCMP();
      if (failure === 'missing revocation API') delete fixture.browser.googlefc!.showRevocationMessage;
      else if (failure === 'missing consent API') delete fixture.browser.__tcfapi;
      else fixture.browser.__tcfapi = () => { throw new Error('Fixture CMP registration failed.'); };

      await act(async () => { ready(); });
      expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).toContain(unavailable);
      expect(fixture.subscriptions).toBe(0);
      expect(fixture.settingsOpened).toBe(0);
      expect(fixture.container.querySelector('ins.adsbygoogle')).toBeNull();
      expect(fixture.dom.document.getElementById('countrydle-adsense')).toBeNull();
      expect(fixture.requests).toBe(0);

      fixture.readyCMP();
      await act(async () => { ready(); });
      expect(fixture.subscriptions).toBe(1);
      expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).not.toContain(unavailable);
      await fixture.emitConsent({ gdprApplies: false });
      await fixture.loadSDK();
      expect(fixture.requests).toBe(1);
    }, { controlledTimers: true });
  });
}

test('a later readiness callback does not hide a failed revocation dialog or reopen the settled request', async () => {
  await withPolicy('/blog', async fixture => {
    fixture.policy.initializeAdvertisingPolicy();
    await fixture.mount(true);
    await fixture.clickPrivacy();
    const ready = fixture.browser.googlefc!.callbackQueue[0].CONSENT_API_READY;
    fixture.readyCMP();
    fixture.browser.googlefc!.showRevocationMessage = () => { throw new Error('Fixture privacy dialog failed.'); };
    await act(async () => { ready(); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).toContain(unavailable);

    fixture.readyCMP();
    await act(async () => { ready(); });
    expect(fixture.subscriptions).toBe(1);
    expect(fixture.settingsOpened).toBe(0);
    expect(fixture.container.querySelector('[data-visible-toasts]')?.textContent).toContain(unavailable);
  }, { controlledTimers: true });
});
