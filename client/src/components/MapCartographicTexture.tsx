import { useEffect } from 'react';
import L from 'leaflet';
import { useMap } from 'react-leaflet';
import './mapSurface.css';

// Texture: "Paper 006" by ambientCG, CC0 1.0 Universal (credit appreciated).
// Source: https://ambientcg.com/view?id=Paper006
const PAPER_TEXTURE_BACKGROUND = 'url("/assets/map-textures/paper006.webp")';
class PaperFiberGridLayer extends L.GridLayer {
  protected override createTile(_coords: L.Coords, done: L.DoneCallback): HTMLElement {
    const tile = L.DomUtil.create('div', 'map-cartographic-texture');
    tile.style.backgroundImage = PAPER_TEXTURE_BACKGROUND;
    tile.setAttribute('aria-hidden', 'true');
    queueMicrotask(() => done(undefined, tile));
    return tile;
  }
}


export default function MapCartographicTexture() {
  const map = useMap();

  useEffect(() => {
    const textureLayer = new PaperFiberGridLayer({
      pane: 'overlayPane',
      zIndex: 450,
      tileSize: 1024,
      opacity: 0.26,
      updateWhenZooming: false,
      keepBuffer: 2,
    });
    textureLayer.addTo(map);
    return () => {
      textureLayer.remove();
    };
  }, [map]);

  return null;
}
