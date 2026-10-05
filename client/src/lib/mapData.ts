import type { FeatureCollection } from 'geojson';

const dataCache = new Map<string, FeatureCollection>();
const pendingRequests = new Map<string, Promise<FeatureCollection>>();

export function getCachedMapData(url: string): FeatureCollection | undefined {
  return dataCache.get(url);
}

// Share both parsed geometry and in-flight requests across routes and StrictMode mounts.
export function loadMapData(url: string): Promise<FeatureCollection> {
  const cached = dataCache.get(url);
  if (cached) return Promise.resolve(cached);
  const pending = pendingRequests.get(url);
  if (pending) return pending;

  const request = fetch(url)
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status} loading ${url}`);
      return response.json() as Promise<FeatureCollection>;
    })
    .then(data => {
      dataCache.set(url, data);
      return data;
    })
    .finally(() => pendingRequests.delete(url));
  pendingRequests.set(url, request);
  return request;
}
