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
}: ShareResultCardProps) {
  const { t } = useTranslation();
  
  const [copied, setCopied] = useState(false);

  const displayDate = date || new Date().toISOString().split('T')[0];
  const fullUrl = `https://countrydle.online${gamePath === '/game' ? '' : gamePath}`;

  // Generate Wordle-style spoiler-free emoji grid
  const generateShareText = () => {
    let emojiIcon = '🌍';
    if (gamePath.includes('us-states')) emojiIcon = '🇺🇸';
    else if (gamePath.includes('powiaty')) emojiIcon = '📍';
    else if (gamePath.includes('wojewodztwa')) emojiIcon = '🗺️';

    let lines = [];
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
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          handleCopy();
        }
      }
    } else {
      handleCopy();
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
    <div className="w-full space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-5">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <div className={`p-2 ${won ? 'text-emerald-400' : 'text-zinc-400'}`}>
            {won ? <Trophy size={20} /> : <Share2 size={20} />}
          </div>
          <div>
            <h3 className="font-serif text-xl text-sand-100">
              {won ? t('share.solvedTitle', 'Daily Challenge Solved!') : t('share.gameOverTitle', 'Game Over')}
            </h3>
            <p className="text-xs text-zinc-400">
              {displayDate} • {gameName}
            </p>
          </div>
        </div>

        {won && points !== undefined && points > 0 && (
          <div className="shrink-0 border border-emerald-500/20 px-3 py-2 font-mono text-sm text-emerald-400">
            +{points.toLocaleString('en-US')} pts
          </div>
        )}
      </div>

      {/* Target Reveal */}
      {targetName && (
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-white/10 pb-4 text-sm">
          <span className="text-zinc-400">{"Today's location:"}</span>
          <span className="break-words font-medium text-sand-100">{targetName}</span>
        </div>
      )}

      {/* Share Actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
        <button
          onClick={handleNativeShare}
          className="flex min-h-11 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-3 py-2.5 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300"
        >
          {copied ? <Check size={14} aria-hidden="true" /> : <Share2 size={14} aria-hidden="true" />}
          <span>{copied ? t('share.copiedBtn', 'Copied!') : t('share.shareBtn', 'Share')}</span>
        </button>

        <button
          onClick={handleCopy}
          className="flex min-h-11 items-center justify-center gap-2 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
        >
          {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          <span>{t('share.copyBtn', 'Copy')}</span>
        </button>

        <button
          onClick={handleShareX}
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
          aria-label={'Share on X / Twitter'}
        >
          <span className="font-bold">𝕏</span>
          <span>{'Post'}</span>
        </button>

        <button
          onClick={handleShareWhatsApp}
          className="flex min-h-11 items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/5"
          aria-label={'Share on WhatsApp'}
        >
          <span>WhatsApp</span>
        </button>
      </div>

      {/* Blog Lore CTA (For Countrydle) */}
      {gamePath === '/game' && (
        <div className="pt-2">
          <Link
            to="/blog"
            className="group flex items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs transition-colors hover:text-sand-100"
          >
            <div className="flex items-center gap-2 text-zinc-300">
              <BookOpen size={14} className="shrink-0 text-emerald-400" aria-hidden="true" />
              <span>{t('share.readBlogCta', 'Read Wikipedia trivia & deduction breakdown on our Daily Blog')}</span>
            </div>
            <ArrowRight size={14} className="shrink-0 text-emerald-400 transition-transform group-hover:translate-x-1" aria-hidden="true" />
          </Link>
        </div>
      )}
    </div>
  );
}
