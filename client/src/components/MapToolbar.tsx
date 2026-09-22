import { RotateCcw } from 'lucide-react';

interface MapToolbarProps {
  mode: 'candidate' | 'eliminate';
  onModeChange: (mode: 'candidate' | 'eliminate') => void;
  onClear: () => void;
  className?: string;
}

export default function MapToolbar({
  mode,
  onModeChange,
  onClear,
  className = '',
}: MapToolbarProps) {
  return (
    <div
      className={`absolute top-2 left-12 z-[1000] flex items-center gap-1 rounded-sm border border-white/10 bg-obsidian-950/90 p-1 shadow-md backdrop-blur-sm ${className}`}
      role="toolbar"
      aria-label="Map marking tools"
    >
      <button
        type="button"
        onClick={() => onModeChange('candidate')}
        className={`flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
          mode === 'candidate'
            ? 'border border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
            : 'border border-transparent text-zinc-400 hover:bg-white/5 hover:text-sand-100'
        }`}
        title="Mark as potential candidate (left-click / tap)"
      >
        <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
        <span>Candidate</span>
      </button>

      <button
        type="button"
        onClick={() => onModeChange('eliminate')}
        className={`flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
          mode === 'eliminate'
            ? 'border border-rose-500/40 bg-rose-500/20 text-rose-300'
            : 'border border-transparent text-zinc-400 hover:bg-white/5 hover:text-sand-100'
        }`}
        title="Mark as eliminated (left-click / tap; or right-click anytime)"
      >
        <span className="h-2 w-2 rounded-full bg-rose-400" aria-hidden="true" />
        <span>Eliminate</span>
      </button>

      <div className="mx-0.5 h-4 w-px bg-white/10" aria-hidden="true" />

      <button
        type="button"
        onClick={onClear}
        className="flex h-6 w-6 items-center justify-center rounded-sm text-zinc-400 transition-colors hover:bg-white/10 hover:text-sand-100 cursor-pointer"
        title="Clear all map markings"
        aria-label="Reset map markings"
      >
        <RotateCcw size={13} />
      </button>
    </div>
  );
}
