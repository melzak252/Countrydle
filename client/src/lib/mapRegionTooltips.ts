import type { Layer } from 'leaflet';
import { normalizeMapRegionName } from './mapGameMode';

export function isRegionNameVisible(name: string, visibleRegionNames: readonly string[]): boolean {
  return visibleRegionNames.some(
    (visibleName) => normalizeMapRegionName(visibleName) === normalizeMapRegionName(name),
  );
}

export function getRegionHint(
  name: string,
  regionHints: Readonly<Record<string, string>>,
): string | null {
  return regionHints[normalizeMapRegionName(name).toUpperCase()] ?? null;
}

function createHintContent(name: string, hint: string): HTMLElement {
  const content = document.createElement('div');
  const label = document.createElement('strong');
  label.textContent = name;
  const detail = document.createElement('div');
  detail.textContent = hint;
  content.append(label, detail);
  return content;
}

export function bindRegionTooltip(
  layer: Layer,
  name: string,
  hideUnlistedTooltips: boolean,
  visibleRegionNames: readonly string[],
  hint?: string | null,
): void {
  const isVisited = isRegionNameVisible(name, visibleRegionNames);
  const showHint = isVisited && Boolean(hint);
  layer.unbindTooltip();
  if (!hideUnlistedTooltips || isVisited) {
    layer.bindTooltip(showHint ? createHintContent(name, hint!) : name, {
      sticky: false,
      direction: isVisited ? 'center' : 'auto',
      opacity: 0.95,
      permanent: isVisited && !showHint,
    });
  }
}

export function restoreRegionTooltip(
  layer: Layer,
  name: string,
  visibleRegionNames: readonly string[],
  hint?: string | null,
  activeHintName?: string | null,
): void {
  if (!isRegionNameVisible(name, visibleRegionNames)) {
    layer.closeTooltip?.();
    return;
  }
  if (!hint) {
    layer.openTooltip?.();
    return;
  }
  if (activeHintName && normalizeMapRegionName(activeHintName) === normalizeMapRegionName(name)) {
    layer.openTooltip?.();
  } else {
    layer.closeTooltip?.();
  }
}

export function bindMapRegionHintAccessibility(
  element: Element,
  name: string,
  hint: string | null,
  onFocus: (name: string) => void,
  onBlur: (name: string) => void,
): () => void {
  const previousAttributes = ['tabindex', 'role', 'aria-label'].map((attribute) => [
    attribute,
    element.getAttribute(attribute),
  ] as const);
  element.setAttribute('tabindex', '0');
  element.setAttribute('role', 'button');
  element.setAttribute('aria-label', hint ? `${name}. ${hint}` : name);

  const focus = () => {
    if (hint) onFocus(name);
  };
  const blur = () => {
    if (hint) onBlur(name);
  };
  const keydown = (event: Event) => {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.key !== 'Enter' && keyboardEvent.key !== ' ') return;
    keyboardEvent.preventDefault();
    element.dispatchEvent(new Event('click', { bubbles: true }));
  };
  element.addEventListener('focus', focus);
  element.addEventListener('blur', blur);
  element.addEventListener('keydown', keydown);

  return () => {
    element.removeEventListener('focus', focus);
    element.removeEventListener('blur', blur);
    element.removeEventListener('keydown', keydown);
    for (const [attribute, value] of previousAttributes) {
      if (value === null) element.removeAttribute(attribute);
      else element.setAttribute(attribute, value);
    }
  };
}

export function routeMapRegionActivation(
  name: string,
  visibleRegionNames: readonly string[],
  showHint: (name: string) => void,
  answer: (name: string) => void,
): 'hint' | 'answer' {
  if (isRegionNameVisible(name, visibleRegionNames)) {
    showHint(name);
    return 'hint';
  }
  answer(name);
  return 'answer';
}
