import { useEffect } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import './mapSurface.css';

interface MapPaperEdgeProps {
  bounds?: L.LatLngBoundsExpression;
}

const GAP_PX = 5;

/**
 * Attaches a double-rule cartographic neatline directly to the map's geographic `bounds`
 * with an exact pixel-uniform gap on all 4 sides (compensating for Mercator distortion).
 */
export default function MapPaperEdge({ bounds: explicitBounds }: MapPaperEdgeProps = {}) {
  const map = useMap();

  useEffect(() => {
    const rawBounds = explicitBounds ?? map.options.maxBounds;
    const bounds = rawBounds instanceof L.LatLngBounds
      ? rawBounds
      : rawBounds
        ? L.latLngBounds(rawBounds as L.LatLngExpression[])
        : null;
    if (!bounds) return;

    const paneName = 'map-neatline-pane';
    const pane = map.getPane(paneName) ?? map.createPane(paneName);
    pane.style.zIndex = '460';
    pane.style.pointerEvents = 'none';

    const renderer = L.canvas({ pane: paneName, padding: 0.5 });

    const south = bounds.getSouth();
    const north = bounds.getNorth();
    const west = bounds.getWest();
    const east = bounds.getEast();
    const latSpan = north - south;
    const lngSpan = east - west;
    const isFullWorldWidth = lngSpan >= 359;

    const deskStyle = {
      pane: paneName,
      renderer,
      stroke: false,
      fillColor: '#cbb890',
      fillOpacity: 0.52,
      interactive: false,
    } as L.PathOptions & { renderer: L.Renderer };
    const deskMasks = isFullWorldWidth
      ? [
          L.rectangle([[north, -540], [89.9, 540]], deskStyle),
          L.rectangle([[-89.9, -540], [south, 540]], deskStyle),
        ]
      : [
          L.rectangle([[north, -540], [89.9, 540]], deskStyle),
          L.rectangle([[-89.9, -540], [south, 540]], deskStyle),
          L.rectangle([[south, -540], [north, west]], deskStyle),
          L.rectangle([[south, east], [north, 540]], deskStyle),
        ];
    deskMasks.forEach((m) => m.addTo(map));

    // Faint cartographic graticule grid inside regional sheets (US/Poland) so the ocean feels alive.
    const graticuleLines: L.Polyline[] = [];
    if (latSpan < 100 && lngSpan < 200) {
      const step = latSpan > 25 ? 10 : 2;
      const startLat = Math.ceil(south / step) * step;
      const startLng = Math.ceil(west / step) * step;
      const gridStyle = {
        pane: paneName,
        renderer,
        color: '#8f7b59',
        weight: 0.55,
        opacity: 0.35,
        interactive: false,
      } as L.PathOptions & { renderer: L.Renderer };
      for (let lat = startLat; lat < north; lat += step) {
        graticuleLines.push(L.polyline([[lat, west], [lat, east]], gridStyle).addTo(map));
      }
      for (let lng = startLng; lng < east; lng += step) {
        graticuleLines.push(L.polyline([[south, lng], [north, lng]], gridStyle).addTo(map));
      }
    }

    const frameBounds = isFullWorldWidth
      ? L.latLngBounds([south, -540], [north, 540])
      : bounds;

    const computeOuterBounds = () => {
      const nw = map.latLngToLayerPoint(frameBounds.getNorthWest());
      const se = map.latLngToLayerPoint(frameBounds.getSouthEast());
      const outerNw = map.layerPointToLatLng(L.point(nw.x - GAP_PX, nw.y - GAP_PX));
      const outerSe = map.layerPointToLatLng(L.point(se.x + GAP_PX, se.y + GAP_PX));
      return L.latLngBounds(
        [outerSe.lat, outerNw.lng],
        [outerNw.lat, outerSe.lng],
      );
    };

    const innerRule = L.rectangle(frameBounds, {
      pane: paneName,
      renderer,
      color: '#6f5c3e',
      weight: 0.9,
      opacity: 0.6,
      fill: false,
      interactive: false,
    } as L.PathOptions & { renderer: L.Renderer }).addTo(map);

    const outerRule = L.rectangle(computeOuterBounds(), {
      pane: paneName,
      renderer,
      color: '#463926',
      weight: 1.8,
      opacity: 0.78,
      fill: false,
      interactive: false,
    } as L.PathOptions & { renderer: L.Renderer }).addTo(map);

    const syncOuter = () => {
      outerRule.setBounds(computeOuterBounds());
    };
    map.on('viewreset zoomend', syncOuter);

    return () => {
      map.off('viewreset zoomend', syncOuter);
      deskMasks.forEach((m) => m.remove());
      graticuleLines.forEach((l) => l.remove());
      outerRule.remove();
      innerRule.remove();
    };
  }, [map, explicitBounds]);

  return null;
}
