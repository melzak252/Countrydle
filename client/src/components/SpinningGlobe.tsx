import React, { useEffect, useRef, useState } from 'react';
import { CONTINENT_POINTS } from './globeData';

interface SpinningGlobeProps {
  className?: string;
  size?: number;
}

export const SpinningGlobe: React.FC<SpinningGlobeProps> = ({
  className = '',
  size = 340,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [currentLon, setCurrentLon] = useState<number>(0);
  const [isInteracting, setIsInteracting] = useState<boolean>(false);

  // Interaction refs to avoid re-renders
  const rotationRef = useRef<{
    lon: number;
    lat: number;
    velLon: number;
    velLat: number;
    isDragging: boolean;
    lastMouseX: number;
    lastMouseY: number;
  }>({
    lon: 0,
    lat: 16, // subtle tilt towards viewer so Northern Hemisphere is visible
    velLon: 0.0035, // default smooth spin
    velLat: 0,
    isDragging: false,
    lastMouseX: 0,
    lastMouseY: 0,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let lastTime = performance.now();
    let pulseTime = 0;

    // Fixed axial tilt (Earth's obliquity: 23.44 degrees)
    const AXIAL_TILT = (23.44 * Math.PI) / 180;

    // Beacon coordinates (mystery location on Earth, e.g. Central Europe 52N, 20E)
    const BEACON_LAT = 52.0;
    const BEACON_LON = 20.0;

    const render = (time: number) => {
      const dt = Math.min((time - lastTime) / 1000, 0.1);
      lastTime = time;
      pulseTime += dt;

      const state = rotationRef.current;

      // Handle momentum & continuous rotation with framerate independence
      if (!state.isDragging) {
        const frameScale = Math.max(0.5, Math.min(2.0, dt * 60));
        state.lon += state.velLon * frameScale;
        // Damping towards default rotation speed
        state.velLon = state.velLon * 0.98 + (0.0035 * (1 - 0.98));
        state.velLat *= 0.95;
        state.lat += state.velLat * frameScale;
        // Clamp vertical latitude tilt to [-40, 40]
        state.lat = Math.max(-40, Math.min(40, state.lat));
      }

      // Update readout every ~10 frames
      if (Math.floor(time / 150) !== Math.floor((time - dt * 1000) / 150)) {
        const deg = Math.floor(((-state.lon * 180) / Math.PI) % 360 + 360) % 360;
        setCurrentLon(deg);
      }

      const dpr = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.41;

      // Spherical projection helper
      const project = (latDeg: number, lonDeg: number): [number, number, number] => {
        const latRad = (latDeg * Math.PI) / 180;
        const lonRad = (lonDeg * Math.PI) / 180 + state.lon;

        // Coordinates on unit sphere
        const x0 = Math.cos(latRad) * Math.sin(lonRad);
        const y0 = -Math.sin(latRad);
        const z0 = Math.cos(latRad) * Math.cos(lonRad);

        // Tilt 1: Earth's 23.44° axial tilt (rotation in Z-axis)
        const cosAx = Math.cos(AXIAL_TILT);
        const sinAx = Math.sin(AXIAL_TILT);
        const x1 = x0 * cosAx - y0 * sinAx;
        const y1 = x0 * sinAx + y0 * cosAx;
        const z1 = z0;

        // Tilt 2: Viewer pitch angle (rotation in X-axis)
        const pitchRad = (state.lat * Math.PI) / 180;
        const cosP = Math.cos(pitchRad);
        const sinP = Math.sin(pitchRad);
        const x2 = x1;
        const y2 = y1 * cosP - z1 * sinP;
        const z2 = y1 * sinP + z1 * cosP;

        // 2D screen coordinates
        const px = cx + x2 * radius;
        const py = cy + y2 * radius;

        return [px, py, z2];
      };

      // 1. Atmosphere Radial Glow Aura
      const aura = ctx.createRadialGradient(cx, cy, radius * 0.75, cx, cy, radius * 1.15);
      aura.addColorStop(0, 'rgba(16, 185, 129, 0)');
      aura.addColorStop(0.7, 'rgba(16, 185, 129, 0.04)');
      aura.addColorStop(0.88, 'rgba(52, 211, 153, 0.22)');
      aura.addColorStop(1, 'rgba(52, 211, 153, 0)');

      ctx.fillStyle = aura;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.15, 0, Math.PI * 2);
      ctx.fill();

      // 2. Translucent Sphere Body (Dark Glass Hologram)
      const sphereFill = ctx.createRadialGradient(
        cx - radius * 0.3,
        cy - radius * 0.3,
        radius * 0.1,
        cx,
        cy,
        radius
      );
      sphereFill.addColorStop(0, 'rgba(16, 185, 129, 0.06)');
      sphereFill.addColorStop(0.7, 'rgba(6, 18, 15, 0.35)');
      sphereFill.addColorStop(1, 'rgba(16, 185, 129, 0.12)');

      ctx.fillStyle = sphereFill;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Helper to draw parallel/meridian paths
      const drawRing = (
        pointsGen: () => [number, number][],
        frontStyle: string,
        backStyle: string,
        lineWidth = 1
      ) => {
        const pts = pointsGen();
        ctx.lineWidth = lineWidth;

        // Draw back segments (z <= 0)
        ctx.strokeStyle = backStyle;
        ctx.beginPath();
        for (let i = 0; i < pts.length; i++) {
          const [px, py, z] = project(pts[i][0], pts[i][1]);
          if (z <= 0.05) {
            const prev = i > 0 ? project(pts[i - 1][0], pts[i - 1][1]) : null;
            if (prev && prev[2] <= 0.05) {
              ctx.lineTo(px, py);
            } else {
              ctx.moveTo(px, py);
            }
          }
        }
        ctx.stroke();

        // Draw front segments (z > 0)
        ctx.strokeStyle = frontStyle;
        ctx.beginPath();
        for (let i = 0; i < pts.length; i++) {
          const [px, py, z] = project(pts[i][0], pts[i][1]);
          if (z > -0.05) {
            const prev = i > 0 ? project(pts[i - 1][0], pts[i - 1][1]) : null;
            if (prev && prev[2] > -0.05) {
              ctx.lineTo(px, py);
            } else {
              ctx.moveTo(px, py);
            }
          }
        }
        ctx.stroke();
      };

      // 3. Graticule Latitudes (Equator, Tropics, Mid-latitudes)
      const latRings = [-60, -30, 0, 30, 60];
      latRings.forEach((lat) => {
        const isEquator = lat === 0;
        drawRing(
          () => {
            const res: [number, number][] = [];
            for (let deg = 0; deg <= 360; deg += 6) {
              res.push([lat, deg]);
            }
            return res;
          },
          isEquator ? 'rgba(52, 211, 153, 0.32)' : 'rgba(52, 211, 153, 0.16)',
          'rgba(16, 185, 129, 0.06)',
          isEquator ? 1.2 : 0.8
        );
      });

      // 4. Graticule Meridians (Every 45 degrees)
      for (let lon = 0; lon < 360; lon += 45) {
        drawRing(
          () => {
            const res: [number, number][] = [];
            for (let lat = -85; lat <= 85; lat += 5) {
              res.push([lat, lon]);
            }
            return res;
          },
          'rgba(52, 211, 153, 0.18)',
          'rgba(16, 185, 129, 0.05)',
          0.8
        );
      }

      // 5. Landmass Dot Constellation
      const frontDots: [number, number, number][] = [];
      const backDots: [number, number, number][] = [];

      for (let i = 0; i < CONTINENT_POINTS.length; i++) {
        const [lat, lon] = CONTINENT_POINTS[i];
        const [px, py, z] = project(lat, lon);
        if (z > 0) {
          frontDots.push([px, py, z]);
        } else {
          backDots.push([px, py, z]);
        }
      }

      // 5a. Render Back Dots (Translucent Glass Matrix)
      ctx.fillStyle = 'rgba(16, 185, 129, 0.10)';
      ctx.beginPath();
      for (let i = 0; i < backDots.length; i++) {
        const [px, py] = backDots[i];
        ctx.moveTo(px + 0.65, py);
        ctx.arc(px, py, 0.65, 0, Math.PI * 2);
      }
      ctx.fill();

      // 5b. Render Front Dots in 4 Depth Tiers for Maximum Performance & Crisp Glow
      const tier1: [number, number][] = []; // 0 < z <= 0.25
      const tier2: [number, number][] = []; // 0.25 < z <= 0.5
      const tier3: [number, number][] = []; // 0.5 < z <= 0.75
      const tier4: [number, number][] = []; // z > 0.75

      for (let i = 0; i < frontDots.length; i++) {
        const [px, py, z] = frontDots[i];
        if (z <= 0.25) {
          tier1.push([px, py]);
        } else if (z <= 0.5) {
          tier2.push([px, py]);
        } else if (z <= 0.75) {
          tier3.push([px, py]);
        } else {
          tier4.push([px, py]);
        }
      }

      // Tier 1: Rim / Horizon edge
      if (tier1.length > 0) {
        ctx.fillStyle = 'rgba(52, 211, 153, 0.35)';
        ctx.beginPath();
        for (let i = 0; i < tier1.length; i++) {
          const [px, py] = tier1[i];
          ctx.moveTo(px + 0.85, py);
          ctx.arc(px, py, 0.85, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // Tier 2: Mid-depth
      if (tier2.length > 0) {
        ctx.fillStyle = 'rgba(52, 211, 153, 0.55)';
        ctx.beginPath();
        for (let i = 0; i < tier2.length; i++) {
          const [px, py] = tier2[i];
          ctx.moveTo(px + 1.1, py);
          ctx.arc(px, py, 1.1, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // Tier 3: Near-front
      if (tier3.length > 0) {
        ctx.fillStyle = 'rgba(52, 211, 153, 0.78)';
        ctx.beginPath();
        for (let i = 0; i < tier3.length; i++) {
          const [px, py] = tier3[i];
          ctx.moveTo(px + 1.35, py);
          ctx.arc(px, py, 1.35, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // Tier 4: Direct Facing (High Intensity Emerald Glow)
      if (tier4.length > 0) {
        ctx.fillStyle = '#6ee7b7';
        ctx.beginPath();
        for (let i = 0; i < tier4.length; i++) {
          const [px, py] = tier4[i];
          ctx.moveTo(px + 1.6, py);
          ctx.arc(px, py, 1.6, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // 6. Mystery Location Beacon Ping
      const [bx, by, bz] = project(BEACON_LAT, BEACON_LON);
      if (bz > 0) {
        const pingProgress = (pulseTime * 0.9) % 1; // 0 to 1
        const pingRadius = 3 + pingProgress * 18;
        const pingAlpha = Math.max(0, (1 - pingProgress) * 0.75 * bz);

        // Expanding radar wave
        ctx.strokeStyle = `rgba(52, 211, 153, ${pingAlpha})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(bx, by, pingRadius, 0, Math.PI * 2);
        ctx.stroke();

        // Pulsing core dot
        ctx.fillStyle = '#6ee7b7';
        ctx.beginPath();
        ctx.arc(bx, by, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Micro crosshair around beacon
        ctx.strokeStyle = `rgba(110, 231, 183, ${0.4 * bz})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(bx - 6, by);
        ctx.lineTo(bx + 6, by);
        ctx.moveTo(bx, by - 6);
        ctx.lineTo(bx, by + 6);
        ctx.stroke();
      }

      // 7. Outer Horizon Perimeter Ring & Ticks
      ctx.strokeStyle = 'rgba(52, 211, 153, 0.55)';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Cardinal tick marks
      const ticks = [0, Math.PI / 2, Math.PI, (Math.PI * 3) / 2];
      ctx.strokeStyle = 'rgba(52, 211, 153, 0.8)';
      ctx.lineWidth = 1.5;
      ticks.forEach((ang) => {
        const xStart = cx + Math.cos(ang) * (radius - 5);
        const yStart = cy + Math.sin(ang) * (radius - 5);
        const xEnd = cx + Math.cos(ang) * (radius + 5);
        const yEnd = cy + Math.sin(ang) * (radius + 5);
        ctx.beginPath();
        ctx.moveTo(xStart, yStart);
        ctx.lineTo(xEnd, yEnd);
        ctx.stroke();
      });

      // Subtle Center Crosshair
      ctx.strokeStyle = 'rgba(52, 211, 153, 0.25)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 10, cy);
      ctx.lineTo(cx + 10, cy);
      ctx.moveTo(cx, cy - 10);
      ctx.lineTo(cx, cy + 10);
      ctx.stroke();

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  // Mouse / Touch handlers for tactile rotation
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsInteracting(true);
    rotationRef.current.isDragging = true;
    rotationRef.current.lastMouseX = e.clientX;
    rotationRef.current.lastMouseY = e.clientY;
    rotationRef.current.velLon = 0;
    rotationRef.current.velLat = 0;
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!rotationRef.current.isDragging) return;
    const dx = e.clientX - rotationRef.current.lastMouseX;
    const dy = e.clientY - rotationRef.current.lastMouseY;

    rotationRef.current.lastMouseX = e.clientX;
    rotationRef.current.lastMouseY = e.clientY;

    const rotScale = 0.006;
    rotationRef.current.lon += dx * rotScale;
    rotationRef.current.lat -= dy * 0.35;
    rotationRef.current.velLon = dx * rotScale * 0.5;
    rotationRef.current.velLat = -dy * 0.15;
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // Ignored if capture already lost
    }
    setIsInteracting(false);
    rotationRef.current.isDragging = false;
  };
  // Safety listener so pointer release outside canvas/window never traps isDragging
  useEffect(() => {
    const handleGlobalRelease = () => {
      if (rotationRef.current.isDragging) {
        rotationRef.current.isDragging = false;
        setIsInteracting(false);
      }
    };
    window.addEventListener('pointerup', handleGlobalRelease);
    window.addEventListener('pointercancel', handleGlobalRelease);
    return () => {
      window.removeEventListener('pointerup', handleGlobalRelease);
      window.removeEventListener('pointercancel', handleGlobalRelease);
    };
  }, []);

  return (
    <figure
      ref={containerRef}
      className={`relative mx-auto flex flex-col items-center select-none ${className}`}
    >
      <div className="relative cursor-grab active:cursor-grabbing">
        {/* Subtle background ambient radial bloom */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 rounded-full bg-emerald-500/10 blur-2xl"
        />

        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className="block touch-none"
          style={{ width: `${size}px`, height: `${size * 0.9}px` }}
          aria-label="Interactive 3D animated green holographic globe"
          role="img"
        />

        {/* Tactical Corner Crosshair Accents */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-0 top-0 h-3 w-3 border-l border-t border-emerald-500/40"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 top-0 h-3 w-3 border-r border-t border-emerald-500/40"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute bottom-0 left-0 h-3 w-3 border-b border-l border-emerald-500/40"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute bottom-0 right-0 h-3 w-3 border-b border-r border-emerald-500/40"
        />
      </div>

      {/* Technical HUD Telemetry Strip */}
      <figcaption className="mt-3 flex w-full max-w-[340px] items-center justify-between border-t border-emerald-500/20 pt-2 font-mono text-[10px] uppercase tracking-wider text-emerald-400/70">
        <span className="flex items-center gap-1.5">
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${isInteracting ? 'bg-emerald-300 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
          {isInteracting ? 'MANUAL ROTATION' : 'LIVE 3D PROJECTION'}
        </span>
        <span className="text-zinc-400">
          LON: <span className="font-semibold text-emerald-300">{currentLon}°</span> · TILT: +23.4°
        </span>
      </figcaption>
    </figure>
  );
};

export default SpinningGlobe;
