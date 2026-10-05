import { afterAll, afterEach, expect, spyOn, test } from 'bun:test';
import { getCachedMapData, loadMapData } from '../src/lib/mapData';

const geometry = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { name: 'Poland' }, geometry: { type: 'Point', coordinates: [19, 52] } }] };
const fetchSpy = spyOn(globalThis, 'fetch');
afterEach(() => fetchSpy.mockReset());

afterAll(() => fetchSpy.mockRestore());

test('concurrent mounts share the download and parsed geometry on later visits', async () => {
  let respond!: (response: Response) => void;
  fetchSpy.mockImplementationOnce(() => new Promise<Response>(resolve => { respond = resolve; }));
  const first = loadMapData('/test-shared-map.geojson');
  const second = loadMapData('/test-shared-map.geojson');
  expect(first).toBe(second);
  expect(getCachedMapData('/test-shared-map.geojson')).toBeUndefined();
  respond(Response.json(geometry));
  const result = await first;
  expect(result).toEqual(geometry);
  expect(await second).toBe(result);
  expect(await loadMapData('/test-shared-map.geojson')).toBe(result);
  expect(fetchSpy).toHaveBeenCalledTimes(1);
});

test('different map URLs retain their own geometry', async () => {
  const otherGeometry = { ...geometry, features: [{ ...geometry.features[0], properties: { name: 'Ohio' } }] };
  fetchSpy.mockResolvedValueOnce(Response.json(geometry));
  fetchSpy.mockResolvedValueOnce(Response.json(otherGeometry));
  await Promise.all([loadMapData('/test-world.geojson'), loadMapData('/test-states.geojson')]);
  expect(getCachedMapData('/test-world.geojson')).toEqual(geometry);
  expect(getCachedMapData('/test-states.geojson')).toEqual(otherGeometry);
});

test('a failed download is not cached and a user retry can recover', async () => {
  fetchSpy.mockResolvedValueOnce(new Response('Unavailable', { status: 503 }));
  await expect(loadMapData('/test-retry.geojson')).rejects.toThrow('HTTP 503');
  expect(getCachedMapData('/test-retry.geojson')).toBeUndefined();
  fetchSpy.mockResolvedValueOnce(Response.json(geometry));
  expect(await loadMapData('/test-retry.geojson')).toEqual(geometry);
});

test('invalid JSON does not poison later loads', async () => {
  fetchSpy.mockResolvedValueOnce(new Response('<html>Proxy error</html>'));
  await expect(loadMapData('/test-invalid-json.geojson')).rejects.toThrow();
  expect(getCachedMapData('/test-invalid-json.geojson')).toBeUndefined();
  fetchSpy.mockResolvedValueOnce(Response.json(geometry));
  expect(await loadMapData('/test-invalid-json.geojson')).toEqual(geometry);
});
