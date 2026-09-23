import type { SVGProps } from 'react';

interface LogoProps extends SVGProps<SVGSVGElement> {
  size?: number;
}

export default function CountrydleLogo({ size = 32, className = '', ...props }: LogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      className={className}
      aria-hidden="true"
      {...props}
    >
      {/* Outer Full Globe Ring (Edge-to-Edge) */}
      <circle cx="32" cy="32" r="28" fill="none" stroke="#34d399" strokeWidth="5" />

      {/* Equator Line */}
      <line x1="4" y1="32" x2="60" y2="32" stroke="#34d399" strokeWidth="4.5" strokeLinecap="round" />

      {/* Prime Meridian (Ellipse) */}
      <ellipse cx="32" cy="32" rx="12.5" ry="28" fill="none" stroke="#10b981" strokeWidth="4.5" />

      {/* Target Waypoint Beacon */}
      <circle cx="42" cy="21" r="7.5" fill="#10b981" />
      <circle cx="42" cy="21" r="3.5" fill="#f8fafc" />
    </svg>
  );
}
