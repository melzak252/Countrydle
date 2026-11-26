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

  test('toggleEntityMarker supports blue and orange colors', () => {
    const store = useCountryGameStore.getState();
    store.setActiveMarkerColor('blue');
    store.toggleEntityMarker('Greece');
    expect(useCountryGameStore.getState().entityMarkings['GREECE']).toBe('blue');

    store.setActiveMarkerColor('orange');
    store.toggleEntityMarker('Portugal');
    expect(useCountryGameStore.getState().entityMarkings['PORTUGAL']).toBe('orange');

    // Switching an entity from blue to orange
    store.toggleEntityMarker('Greece', 'orange');
    expect(useCountryGameStore.getState().entityMarkings['GREECE']).toBe('orange');

    // Clicking with the same color clears the marker
    store.toggleEntityMarker('Greece', 'orange');
    expect(useCountryGameStore.getState().entityMarkings['GREECE']).toBeUndefined();
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

  test('computeAutoEntityMarkings only colors countries specified by each question', async () => {
    const { computeAutoEntityMarkings } = await import('../src/lib/mapMarkings');

    // Q1: "Is it in Europe?" -> No => ONLY European countries are orange, rest untouched
    const qEuropeNo = {
      id: 1,
      original_question: 'Is it in Europe?',
      valid: true,
      answer: false,
      user_id: 0,
      day_id: 1,
      asked_at: '2026-11-27T00:00:00Z',
      map_highlight: {
        supported: true,
        matched: ['Japan', 'Brazil', 'Senegal'],
        eliminated: ['Poland', 'France', 'Russia'],
      },
    };
    const afterEuropeNo = computeAutoEntityMarkings([qEuropeNo]);
    expect(afterEuropeNo['POLAND']).toBe('orange');
    expect(afterEuropeNo['FRANCE']).toBe('orange');
    expect(afterEuropeNo['RUSSIA']).toBe('orange');
    expect(afterEuropeNo['JAPAN']).toBeUndefined();
    expect(afterEuropeNo['BRAZIL']).toBeUndefined();

    // Q2: "Is it in Asia?" -> Yes => Asia-only becomes blue, Russia stays orange, Brazil untouched
    const qAsiaYes = {
      id: 2,
      original_question: 'Is it in Asia?',
      valid: true,
      answer: true,
      user_id: 0,
      day_id: 1,
      asked_at: '2026-11-27T00:01:00Z',
      map_highlight: {
        supported: true,
        matched: ['Japan', 'Russia', 'India'],
        eliminated: ['Poland', 'France', 'Brazil', 'Senegal'],
      },
    };
    const afterAsiaYes = computeAutoEntityMarkings([qEuropeNo, qAsiaYes]);
    expect(afterAsiaYes['JAPAN']).toBe('blue');
    expect(afterAsiaYes['INDIA']).toBe('blue');
    expect(afterAsiaYes['RUSSIA']).toBe('orange');
    expect(afterAsiaYes['POLAND']).toBe('orange');
    expect(afterAsiaYes['BRAZIL']).toBeUndefined();
  });
});
