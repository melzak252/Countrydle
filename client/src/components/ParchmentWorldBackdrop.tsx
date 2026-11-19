import { useEffect, useMemo } from 'react';
import L from 'leaflet';
import type { Feature, FeatureCollection, Geometry, Position } from 'geojson';
import { useMap } from 'react-leaflet';
import { useMapData } from '../hooks/useMapData';

interface ParchmentWorldBackdropProps {
  bounds?: L.LatLngBoundsExpression;
}

function clipRing(ring: Position[], west: number, south: number, east: number, north: number): Position[] {
  const edges: Array<{
    inside: (p: Position) => boolean;
    intersect: (a: Position, b: Position) => Position;
  }> = [
    {
      inside: (p) => p[0] >= west,
      intersect: (a, b) => [west, a[1] + ((b[1] - a[1]) * (west - a[0])) / (b[0] - a[0] || 1e-9)],
    },
    {
      inside: (p) => p[0] <= east,
      intersect: (a, b) => [east, a[1] + ((b[1] - a[1]) * (east - a[0])) / (b[0] - a[0] || 1e-9)],
    },
    {
      inside: (p) => p[1] >= south,
      intersect: (a, b) => [a[0] + ((b[0] - a[0]) * (south - a[1])) / (b[1] - a[1] || 1e-9), south],
    },
    {
      inside: (p) => p[1] <= north,
      intersect: (a, b) => [a[0] + ((b[0] - a[0]) * (north - a[1])) / (b[1] - a[1] || 1e-9), north],
    },
  ];

  let output = ring;
  for (const edge of edges) {
    const input = output;
    output = [];
    if (input.length === 0) break;
    let prev = input[input.length - 1];
    for (const curr of input) {
      if (edge.inside(curr)) {
        if (!edge.inside(prev)) output.push(edge.intersect(prev, curr));
        output.push(curr);
      } else if (edge.inside(prev)) {
        output.push(edge.intersect(prev, curr));
      }
      prev = curr;
    }
  }
  return output;
}

function clipGeometryToBounds(geom: Geometry, west: number, south: number, east: number, north: number): Geometry | null {
  if (geom.type === 'Polygon') {
    const rings = geom.coordinates
      .map((ring) => clipRing(ring, west, south, east, north))
      .filter((ring) => ring.length >= 3);
    return rings.length > 0 ? { type: 'Polygon', coordinates: rings } : null;
  }
  if (geom.type === 'MultiPolygon') {
    const polygons = geom.coordinates
      .map((poly) =>
        poly.map((ring) => clipRing(ring, west, south, east, north)).filter((ring) => ring.length >= 3),
      )
      .filter((poly) => poly.length > 0);
    return polygons.length > 0 ? { type: 'MultiPolygon', coordinates: polygons } : null;
  }
  return null;
}

function clipFeatureCollection(data: FeatureCollection, bounds: L.LatLngBounds): FeatureCollection {
  const west = bounds.getWest();
  const south = bounds.getSouth();
  const east = bounds.getEast();
  const north = bounds.getNorth();
  const features: Feature[] = [];
  for (const feature of data.features) {
    if (!feature.geometry) continue;
    const clipped = clipGeometryToBounds(feature.geometry, west, south, east, north);
    if (clipped) {
      features.push({ ...feature, geometry: clipped });
    }
  }
  return { type: 'FeatureCollection', features };
}

function shiftGeometryLng(geom: Geometry, offsetLng: number): Geometry {
  const shiftRing = (ring: Position[]): Position[] => ring.map(([lng, lat]) => [lng + offsetLng, lat]);
  if (geom.type === 'Polygon') {
    return { type: 'Polygon', coordinates: geom.coordinates.map(shiftRing) };
  }
  if (geom.type === 'MultiPolygon') {
    return { type: 'MultiPolygon', coordinates: geom.coordinates.map((poly) => poly.map(shiftRing)) };
  }
  return geom;
}

function wrapWorldFeatureCollection(data: FeatureCollection): FeatureCollection {
  const features: Feature[] = [...data.features];
  for (const feature of data.features) {
    if (!feature.geometry) continue;
    // Mirror eastern-hemisphere landmasses (-360°) to the left of Alaska and western (+360°) to the right.
    features.push({ ...feature, geometry: shiftGeometryLng(feature.geometry, -360) });
    features.push({ ...feature, geometry: shiftGeometryLng(feature.geometry, 360) });
  }
  return { type: 'FeatureCollection', features };
}

/**
 * Pure GeoJSON Paradox-style parchment landmass backdrop.
 * When `bounds` is provided (Poland modes), clips neighbor landmasses cleanly at the neatline.
 * When omitted (Countrydle, US Statedle), wraps landmasses across the dateline (-360° / +360°)
 * so the Pacific & Asia appear naturally to the left of Alaska and the map never ends on the left.
 */
export default function ParchmentWorldBackdrop({ bounds: explicitBounds }: ParchmentWorldBackdropProps = {}) {
  const map = useMap();
  const { data } = useMapData('/countries_50m.geojson');

  const clippedData = useMemo(() => {
    if (!data) return null;
    if (!explicitBounds) return wrapWorldFeatureCollection(data);
    const latLngBounds = explicitBounds instanceof L.LatLngBounds
      ? explicitBounds
      : L.latLngBounds(explicitBounds as L.LatLngExpression[]);
    return clipFeatureCollection(data, latLngBounds);
  }, [data, explicitBounds]);

  useEffect(() => {
    if (!clippedData) return;

    const paneName = 'parchment-backdrop';
    const pane = map.getPane(paneName) ?? map.createPane(paneName);
    pane.style.zIndex = '150';
    pane.style.pointerEvents = 'none';

    const renderer = L.canvas({ pane: paneName, padding: 0.5 });
    const layer = L.geoJSON(clippedData, {
      pane: paneName,
      renderer,
      interactive: false,
      style: {
        fillColor: '#ded4bc',
        fillOpacity: 0.9,
        color: '#a39478',
        weight: 0.75,
        opacity: 0.8,
      },
    } as L.GeoJSONOptions & { renderer: L.Renderer }).addTo(map);

    return () => {
      layer.remove();
    };
  }, [map, clippedData]);

  return null;
}
