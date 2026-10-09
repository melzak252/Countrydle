import L from 'leaflet';

// Leaflet 1.9 renderer internals: updating bounds also redraws its paths. Keep
// this adapter here rather than reaching into renderers from map components.
type AnimatedMap = L.Map & { _animatingZoom?: boolean };
type BufferedCanvas = L.Canvas & {
  _map: AnimatedMap;
  _bounds: L.Bounds;
  _center: L.LatLng;
  _zoom: number;
  _onZoomEnd: () => void;
  _container: HTMLCanvasElement;
  _ctx: CanvasRenderingContext2D;
  _postponeUpdatePaths?: boolean;
  _update: () => void;
};

export function createMapRenderer(): L.Canvas {
  // Animate a bitmap with the tiles instead of repainting SVG strokes per frame.
  const renderer = L.canvas({ padding: 0.5 }) as BufferedCanvas;
  // Leaflet's public typings omit the renderer internals used by this adapter.
  const rendererPrototype = L.Renderer.prototype as unknown as Pick<BufferedCanvas, '_update'>;
  const updateBounds = rendererPrototype._update;
  renderer._update = function () {
    const map = this._map;
    if (map._animatingZoom && this._bounds) return;
    const size = map.getSize();
    const ratio = L.Browser.retina ? 2 : 1;
    const canvas = this._container;
    // A rebuffer during move already paints the final camera. Leaflet's following
    // moveend must not clear and paint that same bitmap again.
    if (this._bounds && !this._postponeUpdatePaths &&
        this._zoom === map.getZoom() && this._center.equals(map.getCenter()) &&
        canvas.width === size.x * 2 * ratio && canvas.height === size.y * 2 * ratio) return;

    updateBounds.call(this);
    const bounds = this._bounds;
    const width = bounds.max!.x - bounds.min!.x;
    const height = bounds.max!.y - bounds.min!.y;
    L.DomUtil.setPosition(canvas, bounds.min!);
    // Setting either dimension, even to the same value, discards the backing
    // store and resets context state. Allocate only when the viewport changes.
    if (canvas.width !== width * ratio) canvas.width = width * ratio;
    if (canvas.height !== height * ratio) canvas.height = height * ratio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    this._ctx.setTransform(ratio, 0, 0, ratio, -bounds.min!.x * ratio, -bounds.min!.y * ratio);
    this.fire('update');
  };
  let map: AnimatedMap | undefined;
  let zooming = false;

  const rebuffer = () => {
    if (!map) return;
    if (zooming) {
      // Continuous pinch-out can shrink even a buffered bitmap below the view.
      // Rebase only when more coverage is needed, not on every gesture frame.
      if (map._animatingZoom ||
          map.getZoom() >= renderer._zoom) return;
      const scale = map.getZoomScale(map.getZoom(), renderer._zoom);
      const size = map.getSize();
      const currentCenter = map.project(map.getCenter(), renderer._zoom);
      const drawnCenter = map.project(renderer._center, renderer._zoom);
      const bounds = renderer._bounds;
      const halfWidth = (bounds.max!.x - bounds.min!.x) / 2;
      const halfHeight = (bounds.max!.y - bounds.min!.y) / 2;
      if (Math.abs(currentCenter.x - drawnCenter.x) + size.x / (2 * scale) > halfWidth - size.x * 0.05 ||
          Math.abs(currentCenter.y - drawnCenter.y) + size.y / (2 * scale) > halfHeight - size.y * 0.05) {
        renderer._onZoomEnd();
        renderer._update();
      }
      return;
    }
    const origin = map.containerPointToLayerPoint([0, 0]);
    const size = map.getSize();
    const bounds = renderer._bounds;
    const marginX = size.x * 0.25;
    const marginY = size.y * 0.25;
    if (origin.x < bounds.min!.x + marginX ||
        origin.y < bounds.min!.y + marginY ||
        origin.x + size.x > bounds.max!.x - marginX ||
        origin.y + size.y > bounds.max!.y - marginY) {
      // Leaflet normally clips again only at moveend. Refresh before the camera
      // reaches the buffer edge, including during a held drag or its inertia.
      renderer._update();
    }
  };
  const startZoom = () => { zooming = true; };
  const endZoom = () => { zooming = false; };
  renderer.on('add', () => {
    map = renderer._map;
    map.on('move', rebuffer);
    map.on('zoomstart', startZoom);
    map.on('zoomend', endZoom);
  });
  renderer.on('remove', () => {
    map?.off('move', rebuffer);
    map?.off('zoomstart', startZoom);
    map?.off('zoomend', endZoom);
    map = undefined;
    zooming = false;
  });
  return renderer;
}
