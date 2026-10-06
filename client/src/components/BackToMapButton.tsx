import { ChevronDown, Map } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface BackToMapButtonProps {
  onClick: () => void;
  className?: string;
}

export default function BackToMapButton({ onClick, className = '' }: BackToMapButtonProps) {
  const { t } = useTranslation();
  const label = t('game.backToMap', 'Back to map');

  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={`flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-sm border border-emerald-400/40 bg-emerald-400 px-2.5 text-xs font-bold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 md:min-h-0 md:min-w-0 md:border-transparent md:bg-transparent md:px-2 md:text-zinc-400 md:hover:bg-white/10 md:hover:text-sand-100 ${className}`}
    >
      <Map size={16} className="shrink-0 md:hidden" aria-hidden="true" />
      <span className="md:hidden">{label}</span>
      <ChevronDown size={16} className="hidden md:block" aria-hidden="true" />
    </button>
  );
}
