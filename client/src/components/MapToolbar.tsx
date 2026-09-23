import { RotateCcw } from 'lucide-react';
import type { MapMarkerColor } from '../stores/gameStore';

interface MapToolbarProps {
  activeColor: MapMarkerColor;
  onColorChange: (color: MapMarkerColor) => void;
  onClear: () => void;
  className?: string;
}

const COLOR_CONFIGS: { color: MapMarkerColor; label: string; dotClass: string }[] = [
  { color: 'green', label: 'Green marker', dotClass: 'bg-emerald-400 hover:bg-emerald-300' },
  { color: 'red', label: 'Red marker', dotClass: 'bg-rose-500 hover:bg-rose-400' },
  { color: 'blue', label: 'Blue marker', dotClass: 'bg-blue-400 hover:bg-blue-300' },
  { color: 'orange', label: 'Orange marker', dotClass: 'bg-orange-400 hover:bg-orange-300' },
];

export default function MapToolbar({
  activeColor,
  onColorChange,
  onClear,
  className = '',
}: MapToolbarProps) {
  return (
    <div
      className={`absolute left-2.5 top-[10.5rem] md:top-2 md:left-14 z-[1050] flex flex-col md:flex-row items-center gap-1 rounded-sm border border-white/10 bg-obsidian-950/90 px-1 py-1.5 md:px-1.5 md:py-1 shadow-md backdrop-blur-sm ${className}`}
      role="toolbar"
      aria-label="Map marker colors"
    >
      {COLOR_CONFIGS.map(({ color, label, dotClass }) => {
        const isActive = activeColor === color;
        return (
          <button
            key={color}
            type="button"
            onClick={() => onColorChange(color)}
            className={`flex h-6 w-6 items-center justify-center rounded-sm transition-all cursor-pointer ${
              isActive ? 'bg-white/10' : 'hover:bg-white/5'
            }`}
            title={label}
            aria-label={label}
            aria-pressed={isActive}
          >
            <span
              className={`h-3 w-3 rounded-full transition-transform ${dotClass} ${
                isActive
                  ? 'ring-2 ring-white ring-offset-1 ring-offset-obsidian-950 scale-125'
                  : 'opacity-70 hover:opacity-100 hover:scale-110'
              }`}
              aria-hidden="true"
            />
          </button>
        );
      })}

      <div className="mx-0.5 h-3.5 w-px bg-white/15" aria-hidden="true" />

      <button
        type="button"
        onClick={onClear}
        className="flex h-6 w-6 items-center justify-center rounded-sm text-zinc-400 transition-colors hover:bg-white/10 hover:text-sand-100 cursor-pointer"
        title="Clear all map markings"
        aria-label="Clear all map markings"
      >
        <RotateCcw size={13} />
      </button>
    </div>
  );
}
