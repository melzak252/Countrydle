import { useEffect, useState } from 'react';
import type { FeatureCollection } from 'geojson';
import { getCachedMapData, loadMapData } from '../lib/mapData';

interface MapDataState {
  url: string;
  data: FeatureCollection | null;
  error: boolean;
}

export function useMapData(url: string) {
  const [state, setState] = useState<MapDataState>(() => ({
    url, data: getCachedMapData(url) ?? null, error: false,
  }));
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    loadMapData(url).then(
      data => { if (active) setState({ url, data, error: false }); },
      () => { if (active) setState({ url, data: null, error: true }); },
    );
    return () => { active = false; };
  }, [url, attempt]);

  // Never display geometry or an error from the previous URL while its replacement loads.
  const data = state.url === url ? state.data : getCachedMapData(url) ?? null;
  const error = state.url === url && state.error;
  const retry = () => {
    setState({ url, data: null, error: false });
    setAttempt(value => value + 1);
  };
  return { data, error, retry };
}
