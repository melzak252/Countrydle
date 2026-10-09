import { useTranslation } from 'react-i18next';
import { Eraser, RotateCcw } from 'lucide-react';
import type { MapMarkerColor } from '../stores/gameStore';

interface MapToolbarProps {
  activeColor: MapMarkerColor;
  onColorChange: (color: MapMarkerColor) => void;
  onClear: () => void;
  onReset?: () => void;
  className?: string;
}

const COLOR_CONFIGS: { color: MapMarkerColor; label: { en: string; pl: string }; dotClass: string }[] = [
  { color: 'green', label: { en: 'Green marker', pl: 'Zielony znacznik' }, dotClass: 'bg-emerald-400 hover:bg-emerald-300' },
  { color: 'red', label: { en: 'Red marker', pl: 'Czerwony znacznik' }, dotClass: 'bg-rose-500 hover:bg-rose-400' },
  { color: 'blue', label: { en: 'Blue marker', pl: 'Niebieski znacznik' }, dotClass: 'bg-blue-400 hover:bg-blue-300' },
  { color: 'orange', label: { en: 'Orange marker', pl: 'Pomarańczowy znacznik' }, dotClass: 'bg-orange-400 hover:bg-orange-300' },
];

export default function MapToolbar({
  activeColor,
  onColorChange,
  onClear,
  onReset,
  className = '',
}: MapToolbarProps) {
  const { i18n } = useTranslation();
  const isPl = i18n?.language?.startsWith('pl');

  return (
    <div
      className={`absolute left-[12px] top-[13.25rem] md:top-2 md:left-14 z-[1050] flex flex-col items-center gap-1 rounded-sm border border-white/10 bg-obsidian-950/90 px-0 py-0 max-md:border-0 max-md:bg-transparent md:flex-row md:px-1.5 md:py-1 shadow-md backdrop-blur-sm ${className}`}
      role="toolbar"
      aria-label={isPl ? 'Oznaczenia mapy' : 'Map markings'}
    >
      <div className="hidden md:contents">
        {COLOR_CONFIGS.map(({ color, label, dotClass }) => {
          const isActive = activeColor === color;
          const accessibleLabel = isPl ? label.pl : label.en;
          return (
            <button
              key={color}
              type="button"
              onClick={() => onColorChange(color)}
              className={`flex h-8 w-8 items-center justify-center rounded-sm transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 ${
                isActive ? 'bg-white/10' : 'hover:bg-white/5'
              }`}
              title={accessibleLabel}
              aria-label={accessibleLabel}
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

        <div className="mx-0.5 h-5 w-px bg-white/15" aria-hidden="true" />
      </div>

      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="flex h-11 w-11 md:h-8 md:w-8 items-center justify-center rounded-sm max-md:border max-md:border-zinc-700 max-md:bg-zinc-800 text-zinc-200 hover:bg-white/10 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
          title={isPl ? 'Resetuj widok' : 'Reset view'}
          aria-label={isPl ? 'Resetuj widok' : 'Reset view'}
        >
          <RotateCcw size={16} />
        </button>
      )}
      <button
        type="button"
        onClick={onClear}
        className="flex h-11 w-11 md:h-8 md:w-8 items-center justify-center rounded-sm max-md:border max-md:border-zinc-700 max-md:bg-zinc-800 text-zinc-400 transition-colors hover:bg-white/10 hover:text-sand-100 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
        title={isPl ? 'Wyczyść wszystkie oznaczenia mapy' : 'Clear all map markings'}
        aria-label={isPl ? 'Wyczyść wszystkie oznaczenia mapy' : 'Clear all map markings'}
      >
        <Eraser size={16} />
      </button>
    </div>
  );
}
