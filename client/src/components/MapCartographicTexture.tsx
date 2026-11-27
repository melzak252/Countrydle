import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import './mapSurface.css';

// Texture: "Paper 006" by ambientCG, CC0 1.0 Universal (credit appreciated).
// Source: https://ambientcg.com/view?id=Paper006
const PAPER_TEXTURE_BACKGROUND = 'url("/assets/map-textures/paper006.webp")';

export default function MapCartographicTexture() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    const overlay = document.createElement('div');
    overlay.className = 'map-cartographic-texture';
    overlay.style.backgroundImage = PAPER_TEXTURE_BACKGROUND;
    overlay.setAttribute('aria-hidden', 'true');
    container.appendChild(overlay);
    return () => {
      overlay.remove();
    };
  }, [map]);

  return null;
}
