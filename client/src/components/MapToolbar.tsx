
import { Bot, Eraser, RotateCcw } from 'lucide-react';
import type { MapMarkerColor } from '../stores/gameStore';
import { MAP_THEME } from '../lib/mapTheme';

interface MapToolbarProps {
  activeColor: MapMarkerColor;
  onColorChange: (color: MapMarkerColor) => void;
  onClear: () => void;
  onReset?: () => void;
  showAutoMarkings?: boolean;
  onToggleAutoMarkings?: () => void;
  className?: string;
}

const COLOR_CONFIGS: { color: MapMarkerColor; label: string }[] = [
  { color: 'green', label: 'Green marker' },
  { color: 'red', label: 'Red marker' },
  { color: 'blue', label: 'Blue marker' },
  { color: 'orange', label: 'Orange marker' },
];

export default function MapToolbar({
  activeColor,
  onColorChange,
  onClear,
  onReset,
  showAutoMarkings,
  onToggleAutoMarkings,
  className = '',
}: MapToolbarProps) {
  
  

  return (
    <div
      className={`absolute left-[12px] top-[5.75rem] md:top-2 md:left-14 z-[1050] flex flex-col items-center gap-1 rounded-sm border border-[var(--map-control-border)] bg-[var(--map-control-bg)] px-0 py-0 max-md:border-0 max-md:bg-transparent md:flex-row md:px-1.5 md:py-1 shadow-sm ${className}`}
      role="toolbar"
      aria-label={'Map markings'}
    >
      <div className="hidden md:contents">
        {COLOR_CONFIGS.map(({ color, label }) => {
          const isActive = activeColor === color;
          const accessibleLabel = label;
          return (
            <button
              key={color}
              type="button"
              onClick={() => onColorChange(color)}
              className={`flex h-8 w-8 items-center justify-center rounded-sm transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)] ${
                isActive ? 'bg-[var(--map-control-active)]' : 'hover:bg-[var(--map-control-hover)]'
              }`}
              title={accessibleLabel}
              aria-label={accessibleLabel}
              aria-pressed={isActive}
            >
              <span
                className={`h-3 w-3 rounded-full transition-opacity ${
                  isActive ? 'opacity-100' : 'opacity-75 hover:opacity-100'
                }`}
                style={{
                  backgroundColor: MAP_THEME.countries.markers[color].fillColor,
                  boxShadow: isActive
                    ? `0 0 0 2px ${MAP_THEME.controls.surface}, 0 0 0 3px ${MAP_THEME.controls.strongBorder}`
                    : undefined,
                }}
                aria-hidden="true"
              />
            </button>
          );
        })}

        <div className="mx-0.5 h-5 w-px bg-[var(--map-control-border)]" aria-hidden="true" />
      </div>

      {onToggleAutoMarkings && (
        <button
          type="button"
          onClick={onToggleAutoMarkings}
          className={`flex h-9 w-9 md:h-8 md:w-8 items-center justify-center rounded-sm max-md:border transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)] ${
            showAutoMarkings !== false
              ? 'bg-[var(--map-control-active)] text-[var(--map-control-strong-ink)] max-md:border-[var(--map-control-strong-border)] hover:bg-[var(--map-control-hover)]'
              : 'max-md:border-[var(--map-control-border)] max-md:bg-[var(--map-control-bg)] text-[var(--map-control-muted-ink)] hover:bg-[var(--map-control-hover)] hover:text-[var(--map-control-ink)]'
          }`}
          title={showAutoMarkings !== false ? 'Hide bot coloring' : 'Show bot coloring'}
          aria-label={showAutoMarkings !== false ? 'Hide bot coloring' : 'Show bot coloring'}
          aria-pressed={showAutoMarkings !== false}
        >
          <Bot size={16} />
        </button>
      )}
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="flex h-9 w-9 md:h-8 md:w-8 items-center justify-center rounded-sm max-md:border max-md:border-[var(--map-control-border)] max-md:bg-[var(--map-control-bg)] text-[var(--map-control-ink)] hover:bg-[var(--map-control-hover)] cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)]"
          title={'Reset view'}
          aria-label={'Reset view'}
        >
          <RotateCcw size={16} />
        </button>
      )}
      <button
        type="button"
        onClick={onClear}
        className="flex h-9 w-9 md:h-8 md:w-8 items-center justify-center rounded-sm max-md:border max-md:border-[var(--map-control-border)] max-md:bg-[var(--map-control-bg)] text-[var(--map-control-muted-ink)] transition-colors hover:bg-[var(--map-control-hover)] hover:text-[var(--map-control-strong-ink)] cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--map-control-focus)]"
        title={'Clear all map markings'}
        aria-label={'Clear all map markings'}
      >
        <Eraser size={16} />
      </button>
    </div>
  );
}
