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
        lines.push(`🏆 Score: ${points.toLocaleString()} pts`);
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
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 md:p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-300 max-w-xl mx-auto w-full">
      {/* Header Banner */}
      <div className="flex items-center justify-between gap-3 border-b border-zinc-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-xl ${won ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
            {won ? <Trophy size={20} /> : <Share2 size={20} />}
          </div>
          <div>
            <h3 className="text-base md:text-lg font-black text-white">
              {won ? t('share.solvedTitle', 'Daily Challenge Solved!') : t('share.gameOverTitle', 'Game Over')}
            </h3>
            <p className="text-xs text-zinc-400">
              {displayDate} • {gameName}
            </p>
          </div>
        </div>

        {won && points && points > 0 && (
          <div className="px-3 py-1.5 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 font-mono font-black text-sm md:text-base shrink-0">
            +{points.toLocaleString()} pts
          </div>
        )}
      </div>

      {/* Target Reveal */}
      {targetName && (
        <div className="p-3 bg-zinc-800/40 rounded-xl flex items-center justify-between text-xs md:text-sm">
          <span className="text-zinc-400">{t('gamePage.answer', 'The secret location was:')}</span>
          <span className="font-bold text-white text-base">{targetName}</span>
        </div>
      )}

      {/* Share Actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
        <button
          onClick={handleNativeShare}
          className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition-all shadow-md shadow-blue-500/20"
        >
          {copied ? <Check size={14} className="text-white" /> : <Share2 size={14} />}
          <span>{copied ? t('share.copiedBtn', 'Copied!') : t('share.shareBtn', 'Share')}</span>
        </button>

        <button
          onClick={handleCopy}
          className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-xs transition-colors border border-zinc-700/60"
        >
          {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
          <span>{t('share.copyBtn', 'Copy')}</span>
        </button>

        <button
          onClick={handleShareX}
          className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-xs transition-colors border border-zinc-700/60"
          title="Share on X / Twitter"
        >
          <span className="font-bold">𝕏</span>
          <span>Post</span>
        </button>

        <button
          onClick={handleShareWhatsApp}
          className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl bg-green-950/40 hover:bg-green-900/50 text-green-300 font-medium text-xs transition-colors border border-green-800/50"
          title="Share on WhatsApp"
        >
          <span>WhatsApp</span>
        </button>
      </div>

      {/* Blog Lore CTA (For Countrydle) */}
      {gamePath === '/game' && (
        <div className="pt-2">
          <Link
            to="/blog"
            className="flex items-center justify-between p-3 rounded-xl bg-gradient-to-r from-blue-950/30 to-teal-950/20 border border-blue-500/20 hover:border-blue-500/40 text-xs transition-all group"
          >
            <div className="flex items-center gap-2 text-zinc-300">
              <BookOpen size={14} className="text-teal-400 shrink-0" />
              <span>{t('share.readBlogCta', 'Read Wikipedia trivia & deduction breakdown on our Daily Blog')}</span>
            </div>
            <ArrowRight size={14} className="text-blue-400 group-hover:translate-x-1 transition-transform shrink-0" />
          </Link>
        </div>
      )}
    </div>
  );
}
