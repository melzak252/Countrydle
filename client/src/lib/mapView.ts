import type { LatLngBounds, LatLngExpression, Map } from 'leaflet';

interface ZoomState {
  active: boolean;
  pending?: () => void;
}

const zoomStates = new WeakMap<Map, ZoomState>();

// Leaflet ignores setView/fitBounds during an animated zoom. Keep only the newest
// navigation request and apply it once that zoom ends, without another animation.
export function trackMapZoom(map: Map) {
  const state: ZoomState = { active: false };
  zoomStates.set(map, state);
  const onStart = () => { state.active = true; };
  const onEnd = () => {
    state.active = false;
    const pending = state.pending;
    state.pending = undefined;
    pending?.();
  };
  map.on('zoomstart', onStart);
  map.on('zoomend', onEnd);
  return () => {
    map.off('zoomstart', onStart);
    map.off('zoomend', onEnd);
    zoomStates.delete(map);
  };
}

function changeView(map: Map, apply: (animate: boolean) => void) {
  map.stop();
  const state = zoomStates.get(map);
  if (state?.active) {
    state.pending = () => apply(false);
  } else {
    apply(!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
}

export function resetMapView(map: Map, center: LatLngExpression, zoom: number) {
  changeView(map, animate => map.setView(center, zoom, { animate, duration: 0.25 }));
}

export function focusMapBounds(map: Map, bounds: LatLngBounds) {
  changeView(map, animate => map.fitBounds(bounds, { animate, duration: 0.25, padding: [24, 24] }));
}
