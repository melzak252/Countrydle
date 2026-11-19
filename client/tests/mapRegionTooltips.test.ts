import { expect, mock, test } from 'bun:test';
import type { Layer } from 'leaflet';
import { Window as TestWindow } from 'happy-dom';
import { bindRegionTooltip } from '../src/lib/mapRegionTooltips';
function tooltipText(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (typeof value === 'object' && value !== null && 'textContent' in value && typeof value.textContent === 'string') {
    return value.textContent;
  }
  return undefined;
}


test('Powiat and state hints are sourced from catalog and detail facts only', async () => {
  const hints = await import('../src/lib/mapChallengeHints').catch(() => null);
  expect(hints).not.toBeNull();
  if (!hints) return;

  const powiatHint = hints.getMapChallengePowiatHint('POWIAT aleksandrowski');
  expect(powiatHint).toContain('kujawsko-pomorskie');
  expect(powiatHint).toContain('Aleksandrów Kujawski');
  expect(powiatHint).toContain('CAL');
  expect(hints.getMapChallengePowiatHint('Not in the catalog')).toBeNull();

  expect(hints.getMapChallengeStateHint({ neighboring_states: ['Georgia', 'Florida'] }))
    .toBe('Neighboring states: Georgia, Florida');
  expect(hints.getMapChallengeStateHint({ neighboring_states: [], major_rivers: ['Tennessee River'] }))
    .toBe('Major rivers: Tennessee River');
  expect(hints.getMapChallengeStateHint({ neighboring_states: [], major_rivers: [] })).toBeNull();
});

test('marked regions bind their fact as a transient map tooltip', async () => {
  const dom = new TestWindow();
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: dom.document });
  try {
    let content: unknown;
    let options: unknown;
    const layer = {
      unbindTooltip: () => undefined,
      bindTooltip: (value: unknown, config: unknown) => {
        content = value;
        options = config;
      },
    } as unknown as Layer;
    bindRegionTooltip(layer, 'Powiat aleksandrowski', true, ['POWIAT ALEKSANDROWSKI'], 'Voivodeship: kujawsko-pomorskie');
    expect(tooltipText(content)).toContain('Voivodeship: kujawsko-pomorskie');
    const permanent = typeof options === 'object' && options !== null && 'permanent' in options
      ? options.permanent
      : undefined;
    expect(permanent).toBe(false);
  } finally {
    if (previousDocument) Object.defineProperty(globalThis, 'document', previousDocument);
    else Reflect.deleteProperty(globalThis, 'document');
    await dom.happyDOM.close();
  }
});

test('marked regions become keyboard-focusable and focus opens their hint', async () => {
  const tooltips = await import('../src/lib/mapRegionTooltips');
  expect(typeof tooltips.bindMapRegionHintAccessibility).toBe('function');
  if (typeof tooltips.bindMapRegionHintAccessibility !== 'function') return;

  const dom = new TestWindow();
  const path = dom.document.createElementNS('http://www.w3.org/2000/svg', 'path');
  const openHint = mock(() => undefined);
  const closeHint = mock(() => undefined);
  const unbind = tooltips.bindMapRegionHintAccessibility(path, 'Powiat aleksandrowski', 'Voivodeship: kujawsko-pomorskie', openHint, closeHint);
  expect(path.getAttribute('tabindex')).toBe('0');
  expect(path.getAttribute('role')).toBe('button');
  expect(path.getAttribute('aria-label')).toContain('kujawsko-pomorskie');
  path.dispatchEvent(new dom.FocusEvent('focus'));
  expect(openHint).toHaveBeenCalledTimes(1);
  path.dispatchEvent(new dom.FocusEvent('blur'));
  expect(closeHint).toHaveBeenCalledTimes(1);
  unbind();
  expect(path.hasAttribute('tabindex')).toBe(false);
  expect(path.hasAttribute('aria-label')).toBe(false);
  await dom.happyDOM.close();
});

test('tapping a marked region shows its hint instead of answering a new round', async () => {
  const tooltips = await import('../src/lib/mapRegionTooltips');
  expect(typeof tooltips.routeMapRegionActivation).toBe('function');
  if (typeof tooltips.routeMapRegionActivation !== 'function') return;

  const showHint = mock(() => undefined);
  const answer = mock(() => undefined);
  const result = tooltips.routeMapRegionActivation('Powiat aleksandrowski', ['POWIAT ALEKSANDROWSKI'], showHint, answer);
  expect(result).toBe('hint');
  expect(showHint).toHaveBeenCalledTimes(1);
  expect(answer).not.toHaveBeenCalled();

  tooltips.routeMapRegionActivation('Powiat łosicki', ['POWIAT ALEKSANDROWSKI'], showHint, answer);
  expect(answer).toHaveBeenCalledTimes(1);
});

