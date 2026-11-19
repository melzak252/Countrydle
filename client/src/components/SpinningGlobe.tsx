import React, { useEffect, useRef, useState } from 'react';

import { Pause, Play } from 'lucide-react';
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
  const [hudCoords, setHudCoords] = useState<{ lon: string; tilt: string; isStopped: boolean }>({
    lon: '0°',
    tilt: '+16°',
    isStopped: false,
  });
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
    lastMoveTime: number;
    dragDistance: number;
    downTime: number;
    recentMoves: Array<{ dx: number; dy: number; dt: number }>;
  }>({
    lon: 0,
    lat: 16, // subtle tilt towards viewer so Northern Hemisphere is visible
    velLon: 0.0035, // default smooth spin
    velLat: 0,
    isDragging: false,
    lastMouseX: 0,
    lastMouseY: 0,
    lastMoveTime: 0,
    dragDistance: 0,
    downTime: 0,
    recentMoves: [],
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleMotionPreference = () => {
      if (motionPreference.matches) {
        rotationRef.current.velLon = 0;
        rotationRef.current.velLat = 0;
        setHudCoords((coords) => ({ ...coords, isStopped: true }));
      }
    };
    handleMotionPreference();
    motionPreference.addEventListener('change', handleMotionPreference);

    let animationFrameId: number;
    let lastTime = performance.now();
    const theme = getComputedStyle(canvas);
    const readRgb = (name: string, fallback: readonly [number, number, number]) => {
      const channels = theme.getPropertyValue(name).trim().split(/\s+/);
      if (channels.length < 3) return fallback;
      const red = Number(channels[0]);
      const green = Number(channels[1]);
      const blue = Number(channels[2]);
      return Number.isFinite(red) && Number.isFinite(green) && Number.isFinite(blue)
        ? [red, green, blue] as const
        : fallback;
    };
    const rgba = (rgb: readonly [number, number, number], alpha: number) =>
      `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
    const ink = readRgb('--app-text', [38, 43, 36]);
    const accent = readRgb('--app-accent', [42, 89, 66]);
    const surface = readRgb('--app-surface', [250, 248, 240]);
    const surfaceMuted = readRgb('--app-surface-muted', [237, 234, 223]);
    const mapTone = accent;
    const globeColors = {
      sphereLight: rgba(surface, 0.48),
      sphereMid: rgba(surfaceMuted, 0.28),
      sphereEdge: rgba(ink, 0.12),
      backGrid: rgba(ink, 0.08),
      grid: rgba(ink, 0.22),
      equator: rgba(mapTone, 0.42),
      meridian: rgba(ink, 0.18),
      landBack: rgba(mapTone, 0.12),
      landEdge: rgba(mapTone, 0.42),
      landMid: rgba(mapTone, 0.64),
      landFront: rgba(mapTone, 0.82),
      landCenter: rgba(mapTone, 0.94),
      markerRing: rgba(ink, 0.62),
      marker: rgba(mapTone, 0.94),
      outline: rgba(ink, 0.62),
      tick: rgba(mapTone, 0.72),
    };
    // Fixed axial tilt (Earth's obliquity: 23.44 degrees)
    const AXIAL_TILT = (23.44 * Math.PI) / 180;

    // Beacon coordinates (mystery location on Earth, e.g. Central Europe 52N, 20E)
    const BEACON_LAT = 52.0;
    const BEACON_LON = 20.0;

    const render = (time: number) => {
      const dt = Math.min((time - lastTime) / 1000, 0.1);
      lastTime = time;

      const state = rotationRef.current;

      // Handle continuous rotation at the user-chosen tempo
      if (!state.isDragging) {
        const frameScale = Math.max(0.5, Math.min(2.0, dt * 60));
        state.lon += state.velLon * frameScale;
        // Damping vertical latitude pitch velocity so tilt angle settles smoothly
        state.velLat *= 0.88;
        state.lat += state.velLat * frameScale;
        state.lat = Math.max(-50, Math.min(50, state.lat));
      }

      // Update readout every ~100ms
      if (Math.floor(time / 100) !== Math.floor((time - dt * 1000) / 100)) {
        // Standard geographic center longitude (-180° to +180°)
        const rawLon = ((-state.lon * 180) / Math.PI) % 360;
        const normalizedLon = ((rawLon + 540) % 360) - 180;
        const roundedLon = Math.round(normalizedLon);
        let lonString: string;
        if (roundedLon === 0) {
          lonString = '0°';
        } else if (Math.abs(roundedLon) === 180) {
          lonString = '180°';
        } else if (roundedLon > 0) {
          lonString = `${roundedLon}° E`;
        } else {
          lonString = `${Math.abs(roundedLon)}° W`;
        }

        const roundedTilt = Math.round(state.lat);
        const tiltString = `${roundedTilt >= 0 ? '+' : ''}${roundedTilt}°`;
        const isStopped = Math.abs(state.velLon) < 0.0002;

        setHudCoords({ lon: lonString, tilt: tiltString, isStopped });
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
        const y2 = y1 * cosP + z1 * sinP;
        const z2 = -y1 * sinP + z1 * cosP;

        // 2D screen coordinates
        const px = cx + x2 * radius;
        const py = cy + y2 * radius;

        return [px, py, z2];
      };


      // 2. Shaded parchment sphere
      const sphereFill = ctx.createRadialGradient(
        cx - radius * 0.3,
        cy - radius * 0.3,
        radius * 0.1,
        cx,
        cy,
        radius
      );
      sphereFill.addColorStop(0, globeColors.sphereLight);
      sphereFill.addColorStop(0.72, globeColors.sphereMid);
      sphereFill.addColorStop(1, globeColors.sphereEdge);

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
          isEquator ? globeColors.equator : globeColors.grid,
          globeColors.backGrid,
          isEquator ? 1 : 0.7
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
          globeColors.meridian,
          globeColors.backGrid,
          0.7
        );
      }

      // 5. Landmass stipple, shaded by depth
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

      // 5a. Back hemisphere stipple
      ctx.fillStyle = globeColors.landBack;
      ctx.beginPath();
      for (let i = 0; i < backDots.length; i++) {
        const [px, py] = backDots[i];
        ctx.moveTo(px + 0.65, py);
        ctx.arc(px, py, 0.65, 0, Math.PI * 2);
      }
      ctx.fill();

      // 5b. Render front dots in four depth tiers
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
        ctx.fillStyle = globeColors.landEdge;
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
        ctx.fillStyle = globeColors.landMid;
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
        ctx.fillStyle = globeColors.landFront;
        ctx.beginPath();
        for (let i = 0; i < tier3.length; i++) {
          const [px, py] = tier3[i];
          ctx.moveTo(px + 1.35, py);
          ctx.arc(px, py, 1.35, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // Tier 4: Direct-facing land
      if (tier4.length > 0) {
        ctx.fillStyle = globeColors.landCenter;
        ctx.beginPath();
        for (let i = 0; i < tier4.length; i++) {
          const [px, py] = tier4[i];
          ctx.moveTo(px + 1.6, py);
          ctx.arc(px, py, 1.6, 0, Math.PI * 2);
        }
        ctx.fill();
      }

      // 6. Fixed atlas marker for the daily focus point
      const [bx, by, bz] = project(BEACON_LAT, BEACON_LON);
      if (bz > 0) {
        ctx.strokeStyle = globeColors.markerRing;
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.arc(bx, by, 4, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = globeColors.marker;
        ctx.beginPath();
        ctx.arc(bx, by, 1.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // 7. Inked perimeter and cardinal ticks
      ctx.strokeStyle = globeColors.outline;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Cardinal tick marks
      const ticks = [0, Math.PI / 2, Math.PI, (Math.PI * 3) / 2];
      ctx.strokeStyle = globeColors.tick;
      ctx.lineWidth = 1.2;
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


      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animationFrameId);
      motionPreference.removeEventListener('change', handleMotionPreference);
    };
  }, []);

  // Mouse / Touch handlers for tactile rotation and tempo control
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsInteracting(true);
    const now = performance.now();
    rotationRef.current.isDragging = true;
    rotationRef.current.lastMouseX = e.clientX;
    rotationRef.current.lastMouseY = e.clientY;
    rotationRef.current.lastMoveTime = now;
    rotationRef.current.downTime = now;
    rotationRef.current.dragDistance = 0;
    rotationRef.current.recentMoves = [];
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!rotationRef.current.isDragging) return;
    const now = performance.now();
    const dt = Math.max(now - rotationRef.current.lastMoveTime, 1);
    const dx = e.clientX - rotationRef.current.lastMouseX;
    const dy = e.clientY - rotationRef.current.lastMouseY;

    rotationRef.current.lastMouseX = e.clientX;
    rotationRef.current.lastMouseY = e.clientY;
    rotationRef.current.lastMoveTime = now;
    rotationRef.current.dragDistance += Math.hypot(dx, dy);

    const rotScale = 0.0055;
    rotationRef.current.lon += dx * rotScale;
    rotationRef.current.lat += dy * 0.25;
    rotationRef.current.lat = Math.max(-50, Math.min(50, rotationRef.current.lat));

    rotationRef.current.recentMoves.push({ dx, dy, dt });
    if (rotationRef.current.recentMoves.length > 5) {
      rotationRef.current.recentMoves.shift();
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // Ignored if capture already lost
    }
    if (!rotationRef.current.isDragging) return;
    const state = rotationRef.current;
    const now = performance.now();

    // Tap or hold without significant motion (< 4px): toggle stop or gentle spin
    if (state.dragDistance < 4) {
      if (Math.abs(state.velLon) > 0.0003) {
        state.velLon = 0; // Stop!
      } else {
        state.velLon = 0.0035; // Resume default smooth spin
      }
      state.velLat = 0;
    } else {
      // Released after a drag/flick:
      const timeSinceLastMove = now - state.lastMoveTime;
      if (timeSinceLastMove > 130) {
        // Held still before letting go -> stop
        state.velLon = 0;
        state.velLat = 0;
      } else {
        let totalDx = 0;
        let totalDt = 0;
        for (const m of state.recentMoves) {
          totalDx += m.dx;
          totalDt += m.dt;
        }
        if (totalDt > 0) {
          const pxPerMs = totalDx / totalDt;
          const rotScale = 0.0055;
          let releaseVel = pxPerMs * 16.6 * rotScale;
          // Clamp to smooth and enjoyable speed range [-0.035, 0.035]
          releaseVel = Math.max(-0.035, Math.min(0.035, releaseVel));
          state.velLon = releaseVel;
        }
      }
    }

    state.isDragging = false;
    setIsInteracting(false);
  };
  const handlePointerCancel = () => {
    rotationRef.current.isDragging = false;
    setIsInteracting(false);
  };

  const toggleRotation = () => {
    const state = rotationRef.current;
    const isStopped = Math.abs(state.velLon) < 0.0002;
    state.velLon = isStopped ? 0.0035 : 0;
    state.velLat = 0;
    setHudCoords((coords) => ({ ...coords, isStopped: !isStopped }));
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
      className={`relative mx-auto flex w-full min-w-0 flex-col items-center select-none ${className}`}
    >
      <div className="relative aspect-[10/9] w-full cursor-grab active:cursor-grabbing" style={{ maxWidth: size }}>

        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          className="absolute inset-0 block h-full w-full touch-pan-y"
          aria-label={'Interactive animated globe. Drag sideways to rotate; tap to pause or resume.'}
          role="img"
        />

      </div>

      <figcaption className="mt-2 flex w-full items-center justify-between gap-2 border-t border-app-border/40 pt-1 text-xs text-app-text-secondary" style={{ maxWidth: size }}>
        <span className="min-w-0">
          {isInteracting
            ? ('Rotating by hand')
            : hudCoords.isStopped
              ? ('Rotation paused')
              : ('Drag to explore')}
        </span>
        <button
          type="button"
          onClick={toggleRotation}
          aria-label={hudCoords.isStopped
            ? ('Resume globe rotation')
            : ('Pause globe rotation')}
          title={hudCoords.isStopped
            ? ('Resume globe rotation')
            : ('Pause globe rotation')}
          aria-pressed={hudCoords.isStopped}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm text-app-accent hover:bg-app-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
        >
          {hudCoords.isStopped ? <Play size={18} aria-hidden="true" /> : <Pause size={18} aria-hidden="true" />}
        </button>
      </figcaption>
    </figure>
  );
};

export default SpinningGlobe;
