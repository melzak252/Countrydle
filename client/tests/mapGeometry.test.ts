import { beforeAll, describe, expect, test } from 'bun:test';
import { simplifyMapGeometry } from '../scripts/simplify-map-geometry.mjs';

const toleranceMeters = 150;
const sharedBorder = Array.from({ length: 121 }, (_, index): [number, number] => {
  const y = index / 1000;
  const offset = index === 0 || index === 120 ? 0 : index % 2 === 0 ? 0.00012 : -0.00012;
  return [offset, y];
});

const collection = {
  type: 'FeatureCollection' as const,
  features: [
    {
      type: 'Feature' as const,
      id: 'west-entity',
      properties: { entityId: 'west-entity', displayName: 'West entity', regionCode: 'W' },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [[
          ...sharedBorder.slice(0, 61),
          [0.002, 0.06],
          sharedBorder[60],
          ...sharedBorder.slice(61),
          [-0.2, 0.12],
          [-0.2, 0],
          sharedBorder[0],
        ]],
      },
    },
    {
      type: 'Feature' as const,
      id: 'east-entity',
      properties: { entityId: 'east-entity', displayName: 'East entity', regionCode: 'E' },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [[
          ...sharedBorder.slice().reverse(),
          [0.2, 0],
          [0.2, 0.12],
          sharedBorder[sharedBorder.length - 1],
        ]],
      },
    },
    {
      type: 'Feature' as const,
      id: 'island-group',
      properties: { entityId: 'island-group', displayName: 'Island group', regionCode: 'I' },
      geometry: {
        type: 'MultiPolygon' as const,
        coordinates: [
          [
            [[0.5, 0], [0.7, 0], [0.7, 0.2], [0.5, 0.2], [0.5, 0]],
            [[0.5998, 0.0998], [0.5998, 0.1004], [0.6004, 0.0998], [0.5998, 0.0998]],
          ],
          [[
            [0.8, 0.04], [0.8005, 0.04], [0.8, 0.0405], [0.8, 0.04],
          ]],
          [[
            [0.84, 0.04], [0.8404, 0.04], [0.84, 0.0404], [0.84, 0.04],
          ]],
        ],
      },
    },
  ],
};

type Position = [number, number];
type Ring = Position[];
type PolygonCoordinates = Ring[];
type PolygonGeometry = { type: 'Polygon'; coordinates: PolygonCoordinates };
type MultiPolygonGeometry = { type: 'MultiPolygon'; coordinates: PolygonCoordinates[] };
type Geometry = PolygonGeometry | MultiPolygonGeometry;
type Feature = {
  type: 'Feature';
  id?: string | number;
  properties: Record<string, unknown>;
  geometry: Geometry;
};

let simplified: { type: 'FeatureCollection'; features: Feature[] };

beforeAll(() => {
  simplified = simplifyMapGeometry(collection, toleranceMeters) as typeof simplified;
});

function feature(id: string): Feature {
  const result = simplified.features.find((candidate) => candidate.properties.entityId === id);
  if (!result) throw new Error(`Missing simplified feature ${id}`);
  return result;
}


function pointInRing(point: Position, ring: Ring): boolean {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index];
    const [previousX, previousY] = ring[previous];
    const crosses = (y > point[1]) !== (previousY > point[1]);
    if (crosses && point[0] < ((previousX - x) * (point[1] - y)) / (previousY - y) + x) {
      inside = !inside;
    }
  }
  return inside;
}

function pointInPolygon(point: Position, polygon: PolygonCoordinates): boolean {
  return pointInRing(point, polygon[0]) && !polygon.slice(1).some((hole) => pointInRing(point, hole));
}

function coordinateKey([x, y]: Position): string {
  return `${x},${y}`;
}

function boundaryContainsPoint(point: Position, ring: Ring, radius: number): boolean {
  return ring.slice(1).some((end, index) => {
    const start = ring[index];
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const lengthSquared = dx * dx + dy * dy;
    const t = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1,
      ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / lengthSquared,
    ));
    return Math.hypot(point[0] - start[0] - t * dx, point[1] - start[1] - t * dy) <= radius;
  });
}

describe('simplifyMapGeometry', () => {
  test('keeps a shared border identical when one side contains a boundary spur', () => {
    const west = feature('west-entity');
    const east = feature('east-entity');
    expect(west.geometry.type).toBe('Polygon');
    expect(east.geometry.type).toBe('Polygon');
    if (west.geometry.type !== 'Polygon' || east.geometry.type !== 'Polygon') return;

    const originalBorderKeys = new Set(sharedBorder.map(coordinateKey));
    const sharedCoordinates = (geometry: PolygonGeometry) =>
      [...new Map(geometry.coordinates[0]
        .filter((position) => originalBorderKeys.has(coordinateKey(position)))
        .map((position) => [coordinateKey(position), position] as const)).values()]
        .sort(([leftX, leftY], [rightX, rightY]) => leftY - rightY || leftX - rightX);
    const westShared = sharedCoordinates(west.geometry);
    const eastShared = sharedCoordinates(east.geometry);

    expect(westShared).toEqual(eastShared);
    for (const y of [0.03, 0.06, 0.09]) {
      expect(pointInPolygon([-0.001, y], west.geometry.coordinates)).toBe(true);
      expect(pointInPolygon([-0.001, y], east.geometry.coordinates)).toBe(false);
      expect(pointInPolygon([0.001, y], east.geometry.coordinates)).toBe(true);
      expect(pointInPolygon([0.001, y], west.geometry.coordinates)).toBe(false);
    }
  });

  test('preserves a real hole as excluded area and retains every separate island as selectable area', () => {
    const group = feature('island-group');
    expect(group.geometry.type).toBe('MultiPolygon');
    if (group.geometry.type !== 'MultiPolygon') return;

    expect(group.geometry.coordinates).toHaveLength(3);
    expect(pointInPolygon([0.53, 0.03], group.geometry.coordinates[0])).toBe(true);
    expect(pointInPolygon([0.6, 0.1], group.geometry.coordinates[0])).toBe(false);

    const islandSamples = [
      { point: [0.8001, 0.0401] as Position, polygon: group.geometry.coordinates[1] },
      { point: [0.8401, 0.0401] as Position, polygon: group.geometry.coordinates[2] },
    ];
    for (const { point, polygon } of islandSamples) {
      expect(pointInPolygon(point, polygon)).toBe(true);
      const ring = polygon[0];
      const area = Math.abs(ring.slice(0, -1).reduce((sum, [x, y], index) => {
        const [nextX, nextY] = ring[index + 1];
        return sum + x * nextY - nextX * y;
      }, 0) / 2);
      expect(area).toBeGreaterThan(0);
    }
  });

  test('keeps land touching +180 degrees on the eastern Mercator edge', () => {
    const result = simplifyMapGeometry({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { name: 'Dateline coast' },
        geometry: {
          type: 'Polygon',
          coordinates: [[[179.5, 59.5], [180, 59.5], [180, 60], [179.5, 60], [179.5, 59.5]]],
        },
      }],
    }, 100);
    const polygon = result.features[0].geometry.coordinates as PolygonCoordinates;
    expect(pointInPolygon([179.75, 59.75], polygon)).toBe(true);
    expect(pointInPolygon([-170, 59.75], polygon)).toBe(false);
  });

  test('retains the selectable stroke of an existing zero-width boundary spur', () => {
    const result = simplifyMapGeometry({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'Polygon',
          coordinates: [[[0, 0], [0.2, 0], [0.201, -0.001], [0.2, 0], [0.2, 0.2], [0, 0.2], [0, 0]]],
        },
      }],
    }, 20);
    const polygon = result.features[0].geometry.coordinates as PolygonCoordinates;
    expect(boundaryContainsPoint([0.201, -0.001], polygon[0], 0.0001)).toBe(true);
  });

});
