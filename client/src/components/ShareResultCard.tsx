import { useState } from 'react';
import { 
  Share2, 
  Copy, 
  Check, 
  Trophy, 
  BookOpen, 
  ArrowRight
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
  isGuest = false,
  targetCountryCode,
  discovery,
}: ShareResultCardProps) {
  const { t } = useTranslation();
  const { today, remainingSeconds } = useDailyClock();
  
  const [copied, setCopied] = useState(false);

  const displayDate = date || today;
  const newPuzzleReady = today > displayDate;
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

  // Generate Wordle-style spoiler-free emoji grid
  const generateShareText = () => {
    let emojiIcon = '🌍';
    if (gamePath.includes('us-states')) emojiIcon = '🇺🇸';
    else if (gamePath.includes('powiaty')) emojiIcon = '📍';
    else if (gamePath.includes('wojewodztwa')) emojiIcon = '🗺️';

    const lines = [];
    lines.push(`${gameName} ${displayDate} ${emojiIcon}`);

    if (won) {
      if (points && points > 0) {
        lines.push(`🏆 Score: ${points.toLocaleString('en-US')} pts`);
      }
      lines.push(`❓ Questions: ${questionsAsked}/${maxQuestions}`);
      lines.push(`🎯 Guesses: ${guessesMade}/${maxGuesses} (Solved!)`);

      // Emoji squares: Green for questions used, White for unused lifelines
      const greenSquares = '🟩'.repeat(Math.min(questionsAsked, maxQuestions));
      const whiteSquares = '⬜'.repeat(Math.max(0, maxQuestions - questionsAsked));
      lines.push(`${greenSquares}${whiteSquares}`);
      lines.push('');
      lines.push('Can you beat my deduction score?');
    } else {
      lines.push(`❌ Didn't deduce today's secret location`);
      lines.push(`❓ Questions: ${questionsAsked}/${maxQuestions}`);
      lines.push(`🎯 Guesses: ${guessesMade}/${maxGuesses}`);
      lines.push('🟥'.repeat(maxGuesses));
      lines.push('');
      lines.push('Can you solve it?');
    }

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
    <section aria-label={`${gameName} result`} className="w-full space-y-5 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <div className={`p-2 ${won ? 'text-emerald-400' : 'text-zinc-400'}`} aria-hidden="true">
            {won ? <Trophy size={20} /> : <Check size={20} />}
          </div>
          <div>
            <h2 className="font-serif text-2xl text-sand-100">
              {won ? 'You found it. Nicely done!' : 'Every guess builds your map.'}
            </h2>
            <p className="mt-1 text-xs text-zinc-400">
              {displayDate} · {gameName}
            </p>
          </div>
        </div>

        {won && points !== undefined && points > 0 && (
          <div className="shrink-0 border border-emerald-500/20 px-3 py-2 font-mono text-sm text-emerald-400">
            +{points.toLocaleString('en-US')} pts
          </div>
        )}
      </div>

      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-zinc-300">
          {won
            ? 'Your questions and deductions led you to the answer.'
            : 'Not this time. Take a look at the answer, and bring what you learned to the next puzzle.'}
        </p>
        {targetName && (
          <div className="flex items-center gap-4 border-l-2 border-emerald-400/60 pl-4">
            {flagCode && /^[a-z]{2}$/.test(flagCode) && (
              <img
                src={`https://flagcdn.com/w320/${flagCode}.png`}
                alt={`Flag of ${targetName}`}
                className="h-10 w-16 shrink-0 object-contain sm:h-12 sm:w-20"
              />
            )}
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-widest text-zinc-400">The revealed location</p>
              <h3 className="mt-1 break-words font-serif text-3xl text-sand-100 sm:text-4xl">{targetName}</h3>
            </div>
          </div>
        )}
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div className="border border-white/10 p-3">
            <dt className="text-zinc-400">Questions asked</dt>
            <dd className="mt-1 font-mono text-lg text-sand-100">{questionsAsked} <span className="text-sm text-zinc-400">/ {maxQuestions}</span></dd>
          </div>
          <div className="border border-white/10 p-3">
            <dt className="text-zinc-400">Guesses made</dt>
            <dd className="mt-1 font-mono text-lg text-sand-100">{guessesMade} <span className="text-sm text-zinc-400">/ {maxGuesses}</span></dd>
          </div>
        </dl>
        {discovery?.trim() && (
          <div className="border-t border-white/10 pt-4">
            <h3 className="text-sm font-medium text-sand-100">From your questions</h3>
            <p className="mt-2 whitespace-pre-line break-words text-sm leading-relaxed text-zinc-300">{discovery}</p>
          </div>
        )}
      </div>

      <p className="text-xs text-zinc-400">Share your result without revealing the answer.</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
        <button
          type="button"
          onClick={handleNativeShare}
          className="flex min-h-11 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-3 py-2.5 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300"
        >
          {copied ? <Check size={14} aria-hidden="true" /> : <Share2 size={14} aria-hidden="true" />}
          <span>{copied ? t('share.copiedBtn', 'Copied!') : t('share.shareBtn', 'Share')}</span>
        </button>

        <button
          type="button"
          onClick={handleCopy}
          className="flex min-h-11 items-center justify-center gap-2 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
        >
          {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          <span>{t('share.copyBtn', 'Copy')}</span>
        </button>

        <button
          type="button"
          onClick={handleShareX}
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
          aria-label={'Share on X / Twitter'}
        >
          <span className="font-bold">𝕏</span>
          <span>{'Post'}</span>
        </button>

        <button
          type="button"
          onClick={handleShareWhatsApp}
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
          aria-label={'Share on WhatsApp'}
        >
          <span>WhatsApp</span>
        </button>
      </div>

      <div className="space-y-3 border-t border-white/10 pt-4">
        {newPuzzleReady ? (
          <>
            <h3 className="font-serif text-xl text-sand-100">A new puzzle is ready.</h3>
            <Link
              to={gamePath}
              reloadDocument
              className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-sm font-semibold text-obsidian-950 hover:bg-emerald-300"
            >
              Play the new puzzle <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </>
        ) : (
          <>
            <h3 className="font-serif text-xl text-sand-100">A fresh start tomorrow.</h3>
            <p className="text-sm text-zinc-300">
              Next puzzle{countdown !== null ? <> in <span className="font-mono tabular-nums text-sand-100">{countdown}</span></> : ' at 00:00 UTC'}.
            </p>
            <p className="text-xs text-zinc-400">A new location every day at 00:00 UTC.</p>
          </>
        )}
        <Link
          to={otherMode.path}
          className="inline-flex min-h-11 items-center gap-2 text-sm text-zinc-300 underline decoration-white/20 underline-offset-4 hover:text-sand-100"
        >
          Try {otherMode.name} <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>

      {isGuest && (
        <div className="border-t border-white/10 pt-4">
          <h3 className="text-sm font-medium text-sand-100">Keep your next discoveries with you.</h3>
          <p className="mt-2 text-sm leading-relaxed text-zinc-300">
            Create a free account to save future games and play across devices.
          </p>
          <p className="mt-1 text-xs leading-relaxed text-zinc-400">Your older guest history stays on this device.</p>
          <Link
            to="/register"
            className="mt-2 inline-flex min-h-11 items-center gap-2 text-sm text-emerald-300 underline decoration-emerald-400/30 underline-offset-4 hover:text-emerald-200"
          >
            Create an account <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
      )}

      {/* Published articles are available independently of today's puzzle. */}
      {gamePath === '/game' && (
        <div className="pt-2">
          <Link
            to="/blog"
            className="group flex items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs transition-colors hover:text-sand-100"
          >
            <div className="flex items-center gap-2 text-zinc-300">
              <BookOpen size={14} className="shrink-0 text-emerald-400" aria-hidden="true" />
              <span>Explore geography stories in the Daily Blog</span>
            </div>
            <ArrowRight size={14} className="shrink-0 text-emerald-400 transition-transform group-hover:translate-x-1" aria-hidden="true" />
          </Link>
        </div>
      )}
    </section>
  );
}
