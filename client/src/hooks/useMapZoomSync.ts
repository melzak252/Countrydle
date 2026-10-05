import { useEffect } from 'react';
import type { Map } from 'leaflet';

export function useMapZoomSync(map: Map) {
  useEffect(() => {
    const container = map.getContainer();
    container.classList.add('map-zoom-synchronized');

    // New and retained fallback tile levels can animate on different timelines.
    // Scale only the active background level with the borders until zoom finishes.
    const onZoomStart = () => {
      container.querySelectorAll('.leaflet-layer').forEach(layer => {
        let base: HTMLElement | undefined;
        for (const level of layer.querySelectorAll<HTMLElement>('.leaflet-tile-container')) {
          if (!base || Number(level.style.zIndex) > Number(base.style.zIndex)) base = level;
        }
        base?.classList.add('map-zoom-base');
      });
    };
    const onZoomEnd = () => {
      // Leaflet ends zoom on a fixed timer; finish late transforms before revealing
      // new detail so the final frame cannot crossfade a still-moving tile level.
      container.querySelectorAll('.leaflet-zoom-animated').forEach(layer => {
        for (const animation of layer.getAnimations()) {
          if (animation instanceof CSSTransition && animation.transitionProperty === 'transform') {
            animation.finish();
          }
        }
      });
      container.querySelectorAll('.map-zoom-base').forEach(level => {
        level.classList.remove('map-zoom-base');
      });
    };
    map.on('zoomstart', onZoomStart);
    map.on('zoomend', onZoomEnd);
    return () => {
      map.off('zoomstart', onZoomStart);
      map.off('zoomend', onZoomEnd);
      onZoomEnd();
      container.classList.remove('map-zoom-synchronized');
    };
  }, [map]);
}
