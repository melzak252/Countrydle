import type { FactProvenance } from '../types';

export const UNKNOWN_FACT_PROVENANCE: FactProvenance = {
  status: 'unknown', citation: null, source_url: null, effective_from: null,
  effective_to: null, retrieved_at: null, updated_at: null, convention: null,
};

export const PROVENANCE_TEXT_FIELDS = [
  'citation', 'source_url', 'effective_from', 'effective_to', 'retrieved_at', 'updated_at', 'convention',
] as const;

export function safeFactSourceUrl(value: string | null | undefined): string | null {
  const source = value?.trim();
  if (!source || !/^https?:\/\//i.test(source)) return null;
  const authority = source.match(/^https?:\/\/([^/?#]*)/i)?.[1];
  if (authority?.includes('@')) return null;
  try {
    const url = new URL(source);
    if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !url.hostname || url.username || url.password) return null;
    return source;
  } catch {
    return null;
  }
}

export function factProvenanceLabels(isPl: boolean) {
  return isPl ? {
    title: 'Pochodzenie faktów', unknown: 'Nieznane', cited: 'Ze źródłem',
    aggregate: 'Cała relacja / brak wartości', edit: 'Edytuj pochodzenie',
    status: 'Status źródła', citation: 'Cytat / odniesienie', source_url: 'Adres źródła',
    effective_from: 'Obowiązuje od', effective_to: 'Obowiązuje do',
    retrieved_at: 'Data pobrania', updated_at: 'Data aktualizacji dowodu', convention: 'Konwencja',
  } : {
    title: 'Fact provenance', unknown: 'Unknown', cited: 'Cited',
    aggregate: 'Whole relation / absence', edit: 'Edit provenance',
    status: 'Evidence status', citation: 'Citation', source_url: 'Source URL',
    effective_from: 'Effective from', effective_to: 'Effective to',
    retrieved_at: 'Retrieved at', updated_at: 'Evidence updated at', convention: 'Convention',
  };
}
