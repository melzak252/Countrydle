import { useState } from 'react';
import { 
  Share2, 
  Copy, 
  Check, 
  Trophy, 
  // BookOpen removed
  ArrowRight,
  X
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-hot-toast';
import { Link } from 'react-router-dom';
import { useDailyClock } from '../hooks/useDailyClock';

interface ShareResultCardProps {
  gameName: string;
  gamePath: string;
  date?: string | null;
  won: boolean;
  points?: number;
  questionsAsked: number;
  maxQuestions: number;
  guessesMade: number;
  maxGuesses: number;
  targetName?: string;
  isGuest?: boolean;
  targetCountryCode?: string;
  discovery?: string;
  onClose?: () => void;
}
export default function ShareResultCard({
  gameName,
  gamePath,
  date,
  won,
  points,
  questionsAsked,
  maxQuestions,
  guessesMade,
  maxGuesses,
  targetName,
  isGuest: _isGuest = false,
  targetCountryCode,
  discovery,
  onClose,
}: ShareResultCardProps) {
  const { t, i18n } = useTranslation();
  const { today, remainingSeconds } = useDailyClock();
  
  const [copied, setCopied] = useState(false);

  const displayDate = date || today;
  // newPuzzleReady removed
  const countdown = remainingSeconds === null ? null : [
    Math.floor(remainingSeconds / 3600),
    Math.floor((remainingSeconds % 3600) / 60),
    remainingSeconds % 60,
  ].map(value => String(value).padStart(2, '0')).join(':');
  const flagCode = targetCountryCode?.toLowerCase();
  const otherMode = gamePath === '/game'
    ? { path: '/us-states', name: 'US States' }
    : { path: '/game', name: 'Countrydle' };
  const fullUrl = `https://countrydle.online${gamePath === '/game' ? '' : gamePath}`;

  // Generate authentic, spoiler-free share text
  const generateShareText = () => {
    let emojiIcon = '🌍';
    if (gamePath.includes('us-states')) emojiIcon = '🇺🇸';
    else if (gamePath.includes('powiaty')) emojiIcon = '📍';
    else if (gamePath.includes('wojewodztwa')) emojiIcon = '🗺️';
    else if (gamePath.includes('europe')) emojiIcon = '🧭';
    else if (gamePath.includes('asia')) emojiIcon = '🌏';
    else if (gamePath.includes('africa')) emojiIcon = '🌍';
    else if (gamePath.includes('americas')) emojiIcon = '🌎';

    const lines: string[] = [];
    lines.push(`${gameName} · ${displayDate}`);

    if (won) {
      if (questionsAsked === 0) {
        lines.push(`Solved on 1st try (0 questions) ${emojiIcon}`);
      } else {
        const qWord = questionsAsked === 1 ? 'question' : 'questions';
        const gWord = guessesMade === 1 ? 'guess' : 'guesses';
        lines.push(`Solved in ${questionsAsked} ${qWord}, ${guessesMade} ${gWord} ${emojiIcon}`);
      }

      if (points && points > 0) {
        lines.push(`Score: ${points.toLocaleString('en-US')} pts`);
      }

      lines.push('');
      const greenSquares = '🟩'.repeat(Math.min(questionsAsked, maxQuestions));
      const whiteSquares = '⬜'.repeat(Math.max(0, maxQuestions - questionsAsked));
      lines.push(`${greenSquares}${whiteSquares} 🎯`);
    } else {
      lines.push(`X/${maxGuesses} guesses (${questionsAsked}/${maxQuestions} questions) ${emojiIcon}`);
      lines.push('');
      lines.push('🟥'.repeat(maxGuesses));
    }

    lines.push('');
    lines.push(fullUrl);
    return lines.join('\n');
  };

  const handleCopy = async () => {
    const text = generateShareText();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(t('share.copied', 'Result copied to clipboard!'));
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy', err);
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleNativeShare = async () => {
    const text = generateShareText();
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${gameName} Daily Result`,
          text: text,
        });
      } catch (err: unknown) {
        if (!(typeof err === 'object' && err !== null && 'name' in err && err.name === 'AbortError')) {
          await handleCopy();
        }
      }
    } else {
      await handleCopy();
    }
  };

  const handleShareX = () => {
    const text = encodeURIComponent(generateShareText());
    window.open(`https://twitter.com/intent/tweet?text=${text}`, '_blank', 'noopener,noreferrer');
  };

  const handleShareWhatsApp = () => {
    const text = encodeURIComponent(generateShareText());
    window.open(`https://api.whatsapp.com/send?text=${text}`, '_blank', 'noopener,noreferrer');
  };

  return (
    <section
      aria-label={`${gameName} result`}
      className="w-full space-y-6 rounded-sm border border-white/15 bg-obsidian-950 p-5 sm:p-7 md:p-8 relative text-left"
    >
      {/* 1. Header Bar: Game Name & Date + Close Button */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3.5 -mt-1 text-left">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-emerald-400 font-semibold">
            {gameName} Result
          </span>
          <span className="text-zinc-600">·</span>
          <span className="font-mono text-xs text-zinc-400">
            {displayDate}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
            aria-label="Close result modal"
            title="Close"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* 2. Hero Reveal Banner: Outcome & Mystery Location */}
      <div className="rounded-sm border border-white/10 bg-obsidian-900/70 p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
        <div className="flex items-center gap-4 sm:gap-5 min-w-0">
          {targetName && flagCode && /^[a-z]{2}$/.test(flagCode) && (
            <div className="shrink-0 overflow-hidden rounded-sm border border-white/15 bg-obsidian-950 p-1 shadow-md">
              <img
                src={`https://flagcdn.com/w320/${flagCode}.png`}
                alt={`Flag of ${targetName}`}
                className="h-14 w-22 sm:h-16 sm:w-24 object-contain"
              />
            </div>
          )}
          <div className="min-w-0">
            <span className="font-mono text-[10px] sm:text-xs uppercase tracking-widest text-emerald-400 font-semibold">
              The Mystery Location
            </span>
            <h2 className="mt-0.5 break-words font-serif text-3xl sm:text-4xl text-sand-100">
              {targetName || 'Mystery Location'}
            </h2>
            <p className="mt-1 text-xs text-zinc-400">
              {won
                ? (i18n.language.startsWith('pl') ? 'Świetna dedukcja! Odgadłeś dzisiejszą lokalizację.' : 'Outstanding deduction! You uncovered the location.')
                : (i18n.language.startsWith('pl') ? 'Koniec prób. Sprawdź rozwiązanie i spróbuj jutro!' : 'Better luck tomorrow! Study the clues and try again.')}
            </p>
          </div>
        </div>

        {/* Outcome & Points */}
        <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0 border-t sm:border-t-0 border-white/10 pt-3 sm:pt-0">
          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold font-mono ${
            won ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300' : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
          }`}>
            {won ? <Trophy size={14} /> : <Check size={14} />}
            <span>{won ? (i18n.language.startsWith('pl') ? 'Zwycięstwo' : 'Solved') : (i18n.language.startsWith('pl') ? 'Koniec gry' : 'Game Over')}</span>
          </div>
          {won && points !== undefined && points > 0 && (
            <div className="font-mono text-xl sm:text-2xl font-bold text-emerald-300">
              +{points.toLocaleString('en-US')} pts
            </div>
          )}
        </div>
      </div>

      {/* 3. Performance Metrics Grid (Spacious 3 columns) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
        <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-4">
          <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
            Questions Used
          </span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="font-mono text-2xl sm:text-3xl font-bold text-sand-100">{questionsAsked}</span>
            <span className="text-xs text-zinc-500 font-mono">/ {maxQuestions}</span>
          </div>
        </div>

        <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-4">
          <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
            Guesses Made
          </span>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="font-mono text-2xl sm:text-3xl font-bold text-sand-100">{guessesMade}</span>
            <span className="text-xs text-zinc-500 font-mono">/ {maxGuesses}</span>
          </div>
        </div>

        <div className="col-span-2 sm:col-span-1 rounded-sm border border-white/10 bg-obsidian-900/40 p-4 flex flex-col justify-between">
          <span className="text-[11px] uppercase font-mono tracking-wider text-zinc-400 block">
            Next Puzzle
          </span>
          <div className="mt-1 font-mono text-lg sm:text-xl font-semibold text-emerald-400">
            {countdown !== null ? countdown : '00:00 UTC'}
          </div>
        </div>
      </div>

      {/* 4. Deduction Clue (if present) */}
      {discovery?.trim() && (
        <div className="rounded-sm border border-white/10 bg-obsidian-900/40 p-4 text-xs sm:text-sm text-zinc-300 space-y-1">
          <span className="font-mono text-[10px] uppercase tracking-wider text-sand-400 font-semibold block">
            From Your Deductions
          </span>
          <p className="italic text-zinc-300 leading-relaxed whitespace-pre-line">
            "{discovery}"
          </p>
        </div>
      )}

      {/* 5. Primary Actions: Share & 1v1 Challenge */}
      <div className="space-y-3 pt-1">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          <button
            type="button"
            onClick={handleNativeShare}
            className="flex-1 flex min-h-12 items-center justify-center gap-2.5 rounded-sm bg-emerald-400 px-5 py-3 text-sm font-bold text-obsidian-950 transition-colors hover:bg-emerald-300 shadow-md cursor-pointer"
          >
            {copied ? <Check size={16} aria-hidden="true" /> : <Share2 size={16} aria-hidden="true" />}
            <span>{copied ? t('share.copiedBtn', 'Copied to Clipboard!') : t('share.shareBtn', 'Share Result')}</span>
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="flex min-h-12 items-center justify-center gap-2 rounded-sm border border-white/15 px-4 py-3 text-xs font-semibold text-zinc-200 transition-colors hover:bg-white/10 cursor-pointer"
            title="Copy emoji grid"
          >
            <Copy size={15} />
            <span>{t('share.copyBtn', 'Copy')}</span>
          </button>

          <button
            type="button"
            onClick={handleShareX}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-sm border border-white/15 text-zinc-300 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            aria-label="Share on X / Twitter"
            title="Share on X"
          >
            <span className="font-bold text-sm">𝕏</span>
          </button>

          <button
            type="button"
            onClick={handleShareWhatsApp}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-sm border border-white/15 text-zinc-300 transition-colors hover:bg-white/10 hover:text-emerald-400 cursor-pointer"
            aria-label="Share on WhatsApp"
            title="Share on WhatsApp"
          >
            <span className="text-xs font-bold font-mono">WA</span>
          </button>
        </div>

        {/* 1v1 Challenge Invite */}
        <Link
          to={`/friends?mode=${gamePath === '/powiaty' ? 'powiatdle' : gamePath === '/wojewodztwa' ? 'wojewodztwodle' : gamePath === '/us-states' ? 'us_statedle' : 'countrydle'}`}
          className="flex min-h-11 items-center justify-between gap-3 rounded-sm border border-amber-400/30 bg-amber-400/5 px-4 py-2.5 text-xs sm:text-sm font-semibold text-amber-300 hover:bg-amber-400/10 transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-amber-400/20 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-amber-300">
              1v1 Duel
            </span>
            <span>{i18n.language.startsWith('pl') ? 'Wyzwij znajomego na pojedynek' : 'Challenge a friend in real-time'}</span>
          </div>
          <ArrowRight size={15} />
        </Link>
      </div>

      {/* 6. Footer Dismiss / Switch Mode */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs">
        <Link
          to={otherMode.path}
          className="text-zinc-400 hover:text-sand-100 flex items-center gap-1.5 transition-colors"
        >
          <span>Try {otherMode.name}</span>
          <ArrowRight size={13} />
        </Link>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-sm border border-white/15 text-xs font-medium text-zinc-300 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
          >
            {i18n.language.startsWith('pl') ? 'Zamknij i przeglądaj mapę' : 'Close and View Map'}
          </button>
        )}
      </div>
    </section>
  );
}
