import { useEffect, useId, useState } from 'react';
import { 
  Share2, 
  Copy, 
  Check, 
  Trophy, 
  BookOpen,
  MessageSquare,
  ArrowRight,
  X
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'react-hot-toast';
import { Link } from 'react-router-dom';
import { useDailyClock } from '../hooks/useDailyClock';
import type { AnswerReportMode, Question } from '../types';
import type { GameplayNotice } from '../lib/gameplayNotices';
import ResultsQuestionHistory from './ResultsQuestionHistory';
import AdSenseUnit from './AdSenseUnit';
import LocationFieldNotes from './LocationFieldNotes';
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
  targetCountryCode?: string;
  onClose?: () => void;
  questions?: Question[];
  mode?: AnswerReportMode;
  notices?: GameplayNotice[];
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
  targetCountryCode,
  onClose,
  questions,
  mode,
  notices,
}: ShareResultCardProps) {
  const { t, i18n } = useTranslation();
  const { today, remainingSeconds } = useDailyClock();
  
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'notes' | 'questions'>('notes');
  const explorerId = useId();
  const showHistory = questionsAsked > 0 && Boolean(questions?.length);
  const selectedTab = showHistory ? activeTab : 'notes';

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const displayDate = date || today;
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

  const resolvedMode: AnswerReportMode = mode || (
    gamePath.includes('us-states')
      ? 'us_statedle'
      : gamePath.includes('powiaty')
      ? 'powiatdle'
      : gamePath.includes('wojewodztwa')
      ? 'wojewodztwodle'
      : gamePath.includes('europe') || gamePath.includes('asia') || gamePath.includes('africa') || gamePath.includes('americas')
      ? 'continental'
      : 'countrydle'
  );

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
      toast.error(t('share.copyFailed', 'Failed to copy to clipboard'));
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
      className="relative w-full max-h-[calc(var(--app-height,100dvh)-2rem)] overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch] space-y-4 rounded-sm border border-white/15 bg-obsidian-950 p-4 sm:p-6 text-left"
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-[10px] sm:text-xs uppercase tracking-wider text-emerald-400 font-semibold">
            {t('share.resultTitle', '{{gameName}} Result', { gameName })}
          </span>
          <time dateTime={displayDate} className="font-mono text-[10px] sm:text-xs text-zinc-400">
            {displayDate}
          </time>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white transition-colors cursor-pointer"
            aria-label={t('share.closeModal', 'Close result modal')}
            title={t('share.closeModal', 'Close result modal')}
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-sm bg-obsidian-900/60 p-3 sm:p-4">
        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
          {targetName && flagCode && /^[a-z]{2}$/.test(flagCode) && (
            <img
              src={`https://flagcdn.com/w320/${flagCode}.png`}
              alt={t('share.flagAlt', 'Flag of {{targetName}}', { targetName })}
              className="h-12 w-18 sm:h-16 sm:w-24 shrink-0 object-contain rounded-xs border border-white/10 shadow-sm"
            />
          )}
          <div className="min-w-0">
            <span className="font-mono text-[10px] uppercase tracking-widest text-emerald-400 font-semibold">
              {t('share.mysteryLocation', 'The Mystery Location')}
            </span>
            <h2 className="mt-0.5 break-words font-serif text-2xl sm:text-3xl text-sand-100">
              {targetName || t('share.mysteryLocation', 'Mystery Location')}
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-zinc-400">
              {won
                ? t('share.solvedSubtitle', 'Outstanding deduction! You uncovered the location.')
                : t('share.gameOverSubtitle', 'Better luck tomorrow! Study the clues and try again.')}
            </p>
          </div>
        </div>

        {/* Outcome & Points */}
        <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0">
          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold font-mono ${
            won ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300' : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
          }`}>
            {won ? <Trophy size={14} aria-hidden="true" /> : <X size={14} aria-hidden="true" />}
            <span>{won ? t('share.solved', 'Solved') : t('share.gameOver', 'Game Over')}</span>
          </div>
          {won && points !== undefined && points > 0 && (
            <div className="font-mono text-xl sm:text-2xl font-bold text-emerald-300">
              +{points.toLocaleString(i18n.language)} {t('share.pointsUnit', 'pts')}
            </div>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-3 divide-x divide-white/10 rounded-sm border border-white/10 bg-obsidian-900/60">
        <div className="min-w-0 px-2 sm:px-4 py-2">
          <dt className="text-[9px] sm:text-[10px] uppercase font-mono tracking-wide text-zinc-400">
            {t('share.questionsUsed', 'Questions Used')}
          </dt>
          <dd className="mt-0.5 font-mono text-sm sm:text-base font-bold text-sand-100">
            {questionsAsked} <span className="text-zinc-400 font-normal">/ {maxQuestions}</span>
          </dd>
        </div>
        <div className="min-w-0 px-2 sm:px-4 py-2">
          <dt className="text-[9px] sm:text-[10px] uppercase font-mono tracking-wide text-zinc-400">
            {t('share.guessesMade', 'Guesses Made')}
          </dt>
          <dd className="mt-0.5 font-mono text-sm sm:text-base font-bold text-sand-100">
            {guessesMade} <span className="text-zinc-400 font-normal">/ {maxGuesses}</span>
          </dd>
        </div>
        <div className="min-w-0 px-2 sm:px-4 py-2">
          <dt className="text-[9px] sm:text-[10px] uppercase font-mono tracking-wide text-zinc-400">
            {t('share.nextPuzzle', 'Next Puzzle')}
          </dt>
          <dd className="mt-0.5 font-mono text-sm sm:text-base font-semibold text-emerald-400">
            {countdown !== null ? countdown : '00:00 UTC'}
          </dd>
        </div>
      </dl>

      <div className="space-y-3">
        <div className="grid grid-cols-[1fr_auto_auto] sm:grid-cols-[1fr_auto_auto_auto] gap-2">
          <button
            type="button"
            onClick={handleNativeShare}
            className="col-span-3 sm:col-span-1 flex min-h-11 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-4 py-2.5 text-sm font-bold text-obsidian-950 transition-colors hover:bg-emerald-300 cursor-pointer"
          >
            {copied ? <Check size={16} aria-hidden="true" /> : <Share2 size={16} aria-hidden="true" />}
            <span>{copied ? t('share.copiedBtn', 'Copied to Clipboard!') : t('share.shareBtn', 'Share Result')}</span>
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="flex min-h-11 items-center justify-center gap-2 rounded-sm border border-white/15 px-3 py-2.5 text-xs font-semibold text-zinc-200 transition-colors hover:bg-white/10 cursor-pointer"
          >
            <Copy size={15} />
            <span>{t('share.copyBtn', 'Copy Card')}</span>
          </button>

          <button
            type="button"
            onClick={handleShareX}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm border border-white/15 text-zinc-300 transition-colors hover:bg-white/10 hover:text-white cursor-pointer"
            aria-label={t('share.shareX', 'Share on X / Twitter')}
            title={t('share.shareX', 'Share on X / Twitter')}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true" focusable="false">
              <path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z" />
            </svg>
          </button>

          <button
            type="button"
            onClick={handleShareWhatsApp}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-sm border border-white/15 text-zinc-300 transition-colors hover:bg-white/10 hover:text-emerald-400 cursor-pointer"
            aria-label={t('share.shareWhatsApp', 'Share on WhatsApp')}
            title={t('share.shareWhatsApp', 'Share on WhatsApp')}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true" focusable="false">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
            </svg>
          </button>
        </div>

        {/* 1v1 Challenge Invite */}
        <Link
          to={`/friends?mode=${gamePath === '/powiaty' ? 'powiatdle' : gamePath === '/wojewodztwa' ? 'wojewodztwodle' : gamePath === '/us-states' ? 'us_statedle' : 'countrydle'}`}
          className="flex min-h-11 items-center justify-between gap-2 rounded-sm border border-amber-400/25 bg-amber-400/5 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-400/10 transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-amber-400/20 px-2 py-0.5 font-mono text-[10px] uppercase font-bold text-amber-300">
              {t('share.duel', '1v1 Duel')}
            </span>
            <span>{t('share.challengeFriend', 'Challenge a friend in real-time')}</span>
          </div>
          <ArrowRight size={15} />
        </Link>
      </div>
      <div className="space-y-4">
        {showHistory && (
          <div
            role="tablist"
            aria-label={t('share.explorerLabel', 'Explore the result')}
            className="grid grid-cols-2 gap-1 rounded-sm border border-white/10 bg-obsidian-900/60 p-1"
            onKeyDown={(event) => {
              if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
              event.preventDefault();
              const nextTab = event.key === 'Home' ? 'notes' : event.key === 'End' ? 'questions' : selectedTab === 'notes' ? 'questions' : 'notes';
              setActiveTab(nextTab);
              event.currentTarget.querySelector<HTMLButtonElement>(`[data-result-tab="${nextTab}"]`)?.focus();
            }}
          >
            <button
              type="button"
              id={`${explorerId}-notes-tab`}
              role="tab"
              data-result-tab="notes"
              aria-selected={selectedTab === 'notes'}
              aria-controls={`${explorerId}-notes-panel`}
              tabIndex={selectedTab === 'notes' ? 0 : -1}
              onClick={() => setActiveTab('notes')}
              className={`flex min-h-11 items-center justify-center gap-2 rounded-xs px-2 py-2 text-xs font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 ${selectedTab === 'notes' ? 'bg-white/10 text-sand-100' : 'text-zinc-400 hover:text-sand-100'}`}
            >
              <BookOpen size={16} className="shrink-0" aria-hidden="true" />
              <span>{t('fieldNotes.title', 'Location Field Notes')}</span>
            </button>
            <button
              type="button"
              id={`${explorerId}-questions-tab`}
              role="tab"
              data-result-tab="questions"
              aria-selected={selectedTab === 'questions'}
              aria-controls={`${explorerId}-questions-panel`}
              tabIndex={selectedTab === 'questions' ? 0 : -1}
              onClick={() => setActiveTab('questions')}
              className={`flex min-h-11 items-center justify-center gap-2 rounded-xs px-2 py-2 text-xs font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 ${selectedTab === 'questions' ? 'bg-white/10 text-sand-100' : 'text-zinc-400 hover:text-sand-100'}`}
            >
              <MessageSquare size={16} className="shrink-0" aria-hidden="true" />
              <span>{t('chat.historyTitle', 'Question History')}</span>
              <span className="rounded-full bg-white/10 px-1.5 py-0.5 font-mono text-[10px]">{questions?.length}</span>
            </button>
          </div>
        )}
        <div
          id={`${explorerId}-notes-panel`}
          role={showHistory ? 'tabpanel' : undefined}
          aria-labelledby={showHistory ? `${explorerId}-notes-tab` : undefined}
          tabIndex={showHistory ? 0 : undefined}
          className={selectedTab === 'notes' ? 'block' : 'hidden'}
        >
          <LocationFieldNotes
            targetName={targetName}
            mode={resolvedMode}
          />
        </div>
        {showHistory && questions && (
          <div
            id={`${explorerId}-questions-panel`}
            role="tabpanel"
            aria-labelledby={`${explorerId}-questions-tab`}
            tabIndex={0}
            className={selectedTab === 'questions' ? 'block space-y-3' : 'hidden'}
          >
            <p className="text-xs text-zinc-400">
              {t('chat.reviewHint', 'Select a question to review its explanation or report an issue.')}
            </p>
            <ResultsQuestionHistory
              questions={questions}
              notices={notices}
              mode={resolvedMode}
              isGameOver
            />
          </div>
        )}
      </div>

      <AdSenseUnit slot="game-over-modal-footer" className="max-w-md mx-auto" />

      <footer className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/10 pt-4 pb-[env(safe-area-inset-bottom)] text-xs">
        <Link
          to={otherMode.path}
          className="flex min-h-11 items-center gap-1.5 text-zinc-400 hover:text-sand-100 transition-colors"
        >
          <span>{t('share.tryMode', 'Try {{modeName}}', { modeName: otherMode.name })}</span>
          <ArrowRight size={13} />
        </Link>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 w-full sm:w-auto px-4 py-2 rounded-sm border border-white/15 text-xs font-medium text-zinc-300 hover:bg-white/10 hover:text-white transition-colors cursor-pointer"
          >
            {t('share.closeAndViewMap', 'Close and View Map')}
          </button>
        )}
      </footer>
    </section>
  );
}
