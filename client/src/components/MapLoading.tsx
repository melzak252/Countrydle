import type { CSSProperties } from 'react';
import { Globe2, RotateCcw } from 'lucide-react';
import { MAP_THEME, MAP_THEME_CSS_VARIABLES } from '../lib/mapTheme';


export default function MapLoading({ className, error, onRetry }: {
  className: string;
  error: boolean;
  onRetry: () => void;
}) {
  
  
  return (
    <div className={`relative w-full overflow-hidden bg-[var(--map-ocean)] ${className}`} aria-busy={!error} style={MAP_THEME_CSS_VARIABLES as CSSProperties}>
      <div className="absolute inset-0 opacity-15 bg-[size:64px_64px]" style={{ backgroundImage: `linear-gradient(${MAP_THEME.graticule.color} 1px, transparent 1px), linear-gradient(90deg, ${MAP_THEME.graticule.color} 1px, transparent 1px)` }} aria-hidden="true" />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center" role={error ? 'alert' : 'status'}>
        <Globe2 className={`h-10 w-10 text-[var(--map-control-ink)] ${error ? '' : 'motion-safe:animate-pulse'}`} aria-hidden="true" />
        <p className="text-sm font-medium text-[var(--map-control-ink)]">
          {error ? ('Could not load the map') : ('Loading map…')}
        </p>
        <p className="text-xs text-[var(--map-control-muted-ink)]">
          {error ? ('Check your connection and try again.') : ('Preparing borders and markings.')}
        </p>
        {error && (
          <button type="button" onClick={onRetry} className="flex min-h-11 items-center gap-2 rounded border border-[var(--map-control-border)] bg-[var(--map-control-bg)] px-4 text-sm text-[var(--map-control-ink)] hover:bg-[var(--map-control-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)]">
            <RotateCcw size={16} aria-hidden="true" />
            {'Retry map'}
          </button>
        )}
      </div>
    </div>
  );
}
