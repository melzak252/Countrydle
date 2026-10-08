import { spawnSync } from 'node:child_process';
import { closeSync, mkdtempSync, openSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';

const MAPSHAPER_CLI = createRequire(import.meta.url).resolve('mapshaper/bin/mapshaper');
const RING_ID_FIELD = '__countrydle_ring_id';
const MAX_BUFFER_BYTES = 256 * 1024 * 1024;

function signedArea(ring) {
  let area = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    area += x1 * y2 - x2 * y1;
  }
  return area / 2;
}

function ringHasValidCoordinates(ring) {
  return Array.isArray(ring)
    && ring.length >= 4
    && ring.every((point) => Array.isArray(point)
      && point.length >= 2
      && point.every(Number.isFinite))
    && ring[0].length === ring.at(-1).length
    && ring[0].every((coordinate, index) => coordinate === ring.at(-1)[index]);
}

function ringIsNonDegenerate(ring) {
  return ringHasValidCoordinates(ring) && signedArea(ring) !== 0;
}


function polygonsFor(geometry) {
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates;
  throw new TypeError(`Unsupported geometry type: ${geometry.type}`);
}
function ringCrossesAntimeridian(ring) {
  let minLongitude = Infinity;
  let maxLongitude = -Infinity;
  for (const point of ring) {
    minLongitude = Math.min(minLongitude, point[0]);
    maxLongitude = Math.max(maxLongitude, point[0]);
  }
  return minLongitude < -180 || maxLongitude > 180 || maxLongitude - minLongitude > 180;
}

function restoreWinding(ring, originalArea) {
  return Math.sign(signedArea(ring)) === Math.sign(originalArea) ? ring : [...ring].reverse();
}

function coordinateKey(point) {
  return `${point[0]},${point[1]}`;
}

function sourceBoundarySpurs(ring) {
  const spurs = [];
  const count = ring.length - 1;
  for (let index = 0; index < count; index++) {
    const anchor = ring[(index + count - 1) % count];
    const next = ring[(index + 1) % count];
    const tip = ring[index];
    if (coordinateKey(anchor) === coordinateKey(next) && coordinateKey(tip) !== coordinateKey(anchor)) {
      spurs.push({ anchor, tip });
    }
  }
  return spurs;
}

function projectedPoint(point) {
  return [point[0], Math.log(Math.tan((90 + point[1]) * Math.PI / 360)) * 180 / Math.PI];
}

function restoreBoundaryArtifacts(ring, sourceRing, anchors, spurs) {
  // Mapshaper cleans zero-width spurs. Restore their anchors on both sides of
  // shared borders before restoring the original selectable boundary strokes.
  const processed = new Set();
  for (const anchor of sourceRing) {
    const key = coordinateKey(anchor);
    if (!anchors.has(key) || processed.has(key)) continue;
    processed.add(key);
    if (ring.some((point) => coordinateKey(point) === key)) continue;
    const roundedKey = coordinateKey(anchor.map((value) => Math.round(value * 1e6) / 1e6));
    const roundedIndex = ring.findIndex((point) => coordinateKey(point) === roundedKey);
    if (roundedIndex !== -1 && !processed.has(coordinateKey(ring[roundedIndex]))) {
      if (roundedIndex === 0 || roundedIndex === ring.length - 1) {
        ring[0] = anchor;
        ring[ring.length - 1] = anchor;
      } else {
        ring[roundedIndex] = anchor;
      }
      continue;
    }
    const target = projectedPoint(anchor);
    let nearestIndex = 1;
    let nearestDistance = Infinity;
    for (let index = 0; index < ring.length - 1; index++) {
      const start = projectedPoint(ring[index]);
      const end = projectedPoint(ring[index + 1]);
      const dx = end[0] - start[0];
      const dy = end[1] - start[1];
      const lengthSquared = dx * dx + dy * dy;
      const t = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1,
        ((target[0] - start[0]) * dx + (target[1] - start[1]) * dy) / lengthSquared,
      ));
      const distance = (target[0] - start[0] - t * dx) ** 2 + (target[1] - start[1] - t * dy) ** 2;
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index + 1;
      }
    }
    ring.splice(nearestIndex, 0, anchor);
  }
  for (const { anchor, tip } of spurs) {
    const index = ring.findIndex((point) => coordinateKey(point) === coordinateKey(anchor));
    if (index === -1) throw new Error('Lost source boundary spur anchor');
    ring.splice(index + 1, 0, tip, anchor);
  }
  return ring;
}

/** Simplify a GeoJSON FeatureCollection without changing its feature or ring structure. */
export function simplifyMapGeometry(collection, toleranceMeters) {
  if (!collection || collection.type !== 'FeatureCollection' || !Array.isArray(collection.features)) {
    throw new TypeError('Expected a GeoJSON FeatureCollection');
  }
  if (!Number.isFinite(toleranceMeters) || toleranceMeters <= 0) {
    throw new RangeError('Tolerance must be a positive finite number of metres');
  }

  const rings = [];
  const ringIds = new Map();
  const boundaryAnchors = new Map();
  const spursByRing = new Map();
  const features = collection.features.map((feature, featureIndex) => {
    if (!feature.geometry || !['Polygon', 'MultiPolygon'].includes(feature.geometry.type)) {
      throw new TypeError('Every feature must have Polygon or MultiPolygon geometry');
    }
    const geometry = structuredClone(feature.geometry);
    const polygons = polygonsFor(geometry);
    const hasWrappedLongitude = polygons.some((polygon) => polygon.some(ringCrossesAntimeridian));
    for (let polygonIndex = 0; polygonIndex < polygons.length; polygonIndex++) {
      for (let ringIndex = 0; ringIndex < polygons[polygonIndex].length; ringIndex++) {
        const ring = polygons[polygonIndex][ringIndex];
        if (!ringHasValidCoordinates(ring)) {
          throw new TypeError('Source ring must be finite, closed, and contain at least four coordinates');
        }
        const ringKey = `${featureIndex}:${polygonIndex}:${ringIndex}`;
        const spurs = sourceBoundarySpurs(ring);
        if (spurs.length) spursByRing.set(ringKey, spurs);
        for (const { anchor } of spurs) boundaryAnchors.set(coordinateKey(anchor), anchor);
        // Preserve source boundary artifacts, polar rings and wrapped features;
        // simplification must not change their existing display semantics.
        if (!hasWrappedLongitude && ringIsNonDegenerate(ring)
          && !ring.some((point) => Math.abs(point[1]) > 85.05112878)) {
          const id = rings.length;
          rings.push({
            type: 'Feature',
            properties: { [RING_ID_FIELD]: id },
            geometry: {
              type: 'Polygon',
              coordinates: [ring],
            },
          });
          ringIds.set(ringKey, id);
        }
      }
    }
    return { ...feature, geometry };
  });

  if (rings.length === 0) return { ...collection, features };
  const tempDirectory = mkdtempSync(`${tmpdir()}/countrydle-mapshaper-`);
  const inputPath = `${tempDirectory}/input.geojson`;
  const outputPath = `${tempDirectory}/simplified.geojson`;
  // Route stdout to a file descriptor because Bun's buffered capture truncates large GeoJSON results.
  const outputFd = openSync(outputPath, 'w');
  let simplified;
  try {
    // Mapshaper reopens stdin, so use a file to support both Node and Bun.
    writeFileSync(inputPath, JSON.stringify({ type: 'FeatureCollection', features: rings }));
    // Tolerance is measured in projected EPSG:3857 metres for Leaflet display fidelity.
    const result = spawnSync(process.execPath, [
      MAPSHAPER_CLI,
      '-i', inputPath, '-proj', 'init=EPSG:4326', 'crs=EPSG:3857',
      '-simplify', 'dp', `interval=${toleranceMeters}m`, 'keep-shapes',
      '-proj', 'crs=EPSG:4326', '-o', 'format=geojson', 'precision=0.000001', '-',
    ], {
      encoding: 'utf8',
      maxBuffer: MAX_BUFFER_BYTES,
      stdio: ['ignore', outputFd, 'pipe'],
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`Mapshaper failed: ${result.stderr || result.stdout}`);
    simplified = JSON.parse(readFileSync(outputPath, 'utf8'));
  } finally {
    closeSync(outputFd);
    rmSync(tempDirectory, { recursive: true, force: true });
  }
  if (!Array.isArray(simplified.features) || simplified.features.length !== rings.length) {
    throw new Error(`Mapshaper changed ring count (${rings.length} source, ${simplified.features?.length ?? 'missing'} output)`);
  }

  const byId = new Map();
  for (const feature of simplified.features) {
    const id = feature.properties?.[RING_ID_FIELD];
    const ring = feature.geometry?.type === 'Polygon' && feature.geometry.coordinates?.length === 1
      ? feature.geometry.coordinates[0]
      : null;
    if (!Number.isInteger(id) || id < 0 || id >= rings.length || byId.has(id) || !ringIsNonDegenerate(ring)) {
      throw new Error('Mapshaper returned an invalid or unidentified ring');
    }
    byId.set(id, ring);
  }
  if (byId.size !== rings.length) throw new Error('Mapshaper omitted a ring');

  const outputFeatures = features.map((feature, featureIndex) => {
    const polygons = polygonsFor(feature.geometry);
    for (let polygonIndex = 0; polygonIndex < polygons.length; polygonIndex++) {
      for (let ringIndex = 0; ringIndex < polygons[polygonIndex].length; ringIndex++) {
        const sourceRing = polygons[polygonIndex][ringIndex];
        const ringKey = `${featureIndex}:${polygonIndex}:${ringIndex}`;
        const id = ringIds.get(ringKey);
        if (id === undefined) continue;
        const outputRing = restoreBoundaryArtifacts(
          restoreWinding(byId.get(id), signedArea(sourceRing)),
          sourceRing, boundaryAnchors, spursByRing.get(ringKey) ?? [],
        );
        polygons[polygonIndex][ringIndex] = outputRing;
      }
    }
    return feature;
  });

  return { ...collection, features: outputFeatures };
}

async function runCli(args) {
  if (args.length !== 3) {
    throw new Error('Usage: bun scripts/simplify-map-geometry.mjs INPUT.geojson OUTPUT.geojson INTERVAL_METRES');
  }
  const [inputPath, outputPath, tolerance] = args;
  const source = JSON.parse(await readFile(inputPath, 'utf8'));
  const output = simplifyMapGeometry(source, Number(tolerance));
  await writeFile(outputPath, `${JSON.stringify(output)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runCli(process.argv.slice(2)).catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
