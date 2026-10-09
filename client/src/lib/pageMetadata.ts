import { useLayoutEffect, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';

export interface PageMetadataInput {
  title: string;
  description: string;
  canonicalPath?: string;
  noindex?: boolean;
  article?: {
    countryName: string;
    puzzleDate: string;
    publishedAt: string;
    updatedAt?: string;
    authorName?: string;
    reviewedBy?: string;
  };
}

export function isPrerenderCapture(): boolean {
  return typeof window !== 'undefined' &&
    (window as Window & { __COUNTRYDLE_PRERENDER__?: boolean }).__COUNTRYDLE_PRERENDER__ === true;
}

// One loaded-page override, scoped to the exact route so prior article data cannot leak.
let override: { pathname: string; metadata: PageMetadataInput; owner: symbol } | null = null;
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};
const getSnapshot = () => override;

export function usePageMetadata(metadata: PageMetadataInput | null): void {
  const { pathname } = useLocation();
  const serialized = JSON.stringify(metadata);
  useLayoutEffect(() => {
    if (serialized === 'null') return;
    const owner = Symbol('page-metadata');
    override = { pathname, metadata: JSON.parse(serialized) as PageMetadataInput, owner };
    listeners.forEach((listener) => listener());
    return () => {
      if (override?.owner === owner) {
        override = null;
        listeners.forEach((listener) => listener());
      }
    };
  }, [pathname, serialized]);
}

export function usePageMetadataOverride() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
