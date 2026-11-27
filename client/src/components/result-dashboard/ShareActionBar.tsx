import { useState, type ReactNode } from 'react';
import { Share2, Copy, Check, Clock } from 'lucide-react';
import { toast } from 'react-hot-toast';
import CountdownTimer from '../CountdownTimer';
import type { ResultDashboardAction } from './types';

interface ShareActionBarProps {
  shareText: string;
  shareTitle: string;
  isDaily?: boolean;
  primaryAction?: ResultDashboardAction;
  secondaryActions?: ReactNode;
  align?: 'left' | 'right';
}

export default function ShareActionBar({
  shareText,
  shareTitle,
  isDaily = true,
  primaryAction,
  secondaryActions,
  align = 'right',
}: ShareActionBarProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      toast.success('Result copied to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: shareTitle, text: shareText });
      } catch (err: unknown) {
        if (
          !(typeof err === 'object' && err !== null && 'name' in err && err.name === 'AbortError')
        ) {
          await handleCopy();
        }
      }
    } else {
      await handleCopy();
    }
  };

  const handleShareX = () => {
    window.open(
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const handleShareWhatsApp = () => {
    window.open(
      `https://api.whatsapp.com/send?text=${encodeURIComponent(shareText)}`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const alignClass = align === 'right' ? 'lg:items-end' : 'items-start';
  const rowJustifyClass = align === 'right' ? 'lg:justify-end' : 'justify-start';

  return (
    <div aria-label="Share result" className={`flex flex-col gap-2.5 ${alignClass}`}>
      {/* Primary Share button + subtle icon actions */}
      <div className={`flex flex-wrap items-center gap-2 ${rowJustifyClass}`}>
        <button
          type="button"
          onClick={handleNativeShare}
          className="flex-1 sm:flex-initial inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-emerald-400 px-5 py-2 text-sm font-bold text-obsidian-950 transition-colors hover:bg-emerald-300 cursor-pointer"
        >
          {copied ? <Check size={15} aria-hidden="true" /> : <Share2 size={15} aria-hidden="true" />}
          <span>{copied ? 'Copied!' : 'Share Result'}</span>
        </button>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-zinc-300 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            aria-label="Copy result"
            title="Copy result"
          >
            {copied ? <Check size={15} className="text-emerald-400" aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
          </button>

          <button
            type="button"
            onClick={handleShareX}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-zinc-300 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            aria-label="Share on X"
            title="Share on X"
          >
            <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
              <path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z" />
            </svg>
          </button>

          <button
            type="button"
            onClick={handleShareWhatsApp}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-zinc-300 transition-colors hover:bg-white/10 hover:text-emerald-400 cursor-pointer"
            aria-label="Share on WhatsApp"
            title="Share on WhatsApp"
          >
            <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Optional mode primary / secondary actions */}
      {(primaryAction || secondaryActions) && (
        <div className={`flex flex-wrap items-center gap-2 ${rowJustifyClass}`}>
          {primaryAction && (
            <button
              type="button"
              onClick={primaryAction.onClick}
              className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3.5 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-400/20 transition-colors cursor-pointer"
            >
              {primaryAction.icon}
              <span>{primaryAction.label}</span>
            </button>
          )}
          {secondaryActions}
        </div>
      )}

      {/* Compact UTC countdown */}
      {isDaily && (
        <div className="inline-flex items-center gap-2 text-xs text-zinc-400">
          <Clock size={12} className="text-zinc-500 shrink-0" aria-hidden="true" />
          <span className="font-mono text-[11px]">Next puzzle in</span>
          <CountdownTimer variant="minimal" className="text-xs font-semibold text-zinc-200" />
        </div>
      )}
    </div>
  );
}
