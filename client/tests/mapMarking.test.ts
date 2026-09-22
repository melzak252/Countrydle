import { describe, test, expect, beforeEach } from 'bun:test';
import { useCountryGameStore } from '../src/stores/gameStore';

describe('Dual-State Map Marking & Elimination Store Logic', () => {
  beforeEach(() => {
    useCountryGameStore.getState().clearMapMarkings();
    useCountryGameStore.getState().setMapInteractionMode('candidate');
  });

  test('toggleEntityCandidate adds and removes candidate entities', () => {
    const store = useCountryGameStore.getState();
    expect(store.candidateEntities).toEqual([]);

    store.toggleEntityCandidate('Poland');
    expect(useCountryGameStore.getState().candidateEntities).toEqual(['POLAND']);

    useCountryGameStore.getState().toggleEntityCandidate('Poland');
    expect(useCountryGameStore.getState().candidateEntities).toEqual([]);
  });

  test('toggleEntityEliminated adds and removes eliminated entities', () => {
    const store = useCountryGameStore.getState();
    expect(store.eliminatedEntities).toEqual([]);

    store.toggleEntityEliminated('Germany');
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual(['GERMANY']);

    useCountryGameStore.getState().toggleEntityEliminated('Germany');
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual([]);
  });

  test('marking as candidate removes from eliminated entities', () => {
    const store = useCountryGameStore.getState();
    store.toggleEntityEliminated('France');
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual(['FRANCE']);
    expect(useCountryGameStore.getState().candidateEntities).toEqual([]);

    useCountryGameStore.getState().toggleEntityCandidate('France');
    expect(useCountryGameStore.getState().candidateEntities).toEqual(['FRANCE']);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual([]);
  });

  test('marking as eliminated removes from candidate entities', () => {
    const store = useCountryGameStore.getState();
    store.toggleEntityCandidate('Spain');
    expect(useCountryGameStore.getState().candidateEntities).toEqual(['SPAIN']);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual([]);

    useCountryGameStore.getState().toggleEntityEliminated('Spain');
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual(['SPAIN']);
    expect(useCountryGameStore.getState().candidateEntities).toEqual([]);
  });

  test('handleEntityMapClick applies active mode on primary click', () => {
    useCountryGameStore.getState().setMapInteractionMode('candidate');
    useCountryGameStore.getState().handleEntityMapClick('Italy', false);
    expect(useCountryGameStore.getState().candidateEntities).toEqual(['ITALY']);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual([]);

    useCountryGameStore.getState().setMapInteractionMode('eliminate');
    useCountryGameStore.getState().handleEntityMapClick('Norway', false);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual(['NORWAY']);
  });

  test('handleEntityMapClick applies alternate mode on secondary click (right-click)', () => {
    useCountryGameStore.getState().setMapInteractionMode('candidate');
    // In candidate mode, right-click (secondary = true) should eliminate
    useCountryGameStore.getState().handleEntityMapClick('Sweden', true);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual(['SWEDEN']);
    expect(useCountryGameStore.getState().candidateEntities).toEqual([]);

    useCountryGameStore.getState().setMapInteractionMode('eliminate');
    // In eliminate mode, right-click (secondary = true) should mark candidate
    useCountryGameStore.getState().handleEntityMapClick('Finland', true);
    expect(useCountryGameStore.getState().candidateEntities).toEqual(['FINLAND']);
  });

  test('clearMapMarkings removes all candidate and eliminated entities', () => {
    const store = useCountryGameStore.getState();
    store.toggleEntityCandidate('Poland');
    store.toggleEntityEliminated('Germany');
    expect(useCountryGameStore.getState().candidateEntities.length).toBe(1);
    expect(useCountryGameStore.getState().eliminatedEntities.length).toBe(1);

    useCountryGameStore.getState().clearMapMarkings();
    expect(useCountryGameStore.getState().candidateEntities).toEqual([]);
    expect(useCountryGameStore.getState().eliminatedEntities).toEqual([]);
  });
});
