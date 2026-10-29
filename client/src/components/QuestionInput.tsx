import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { ArrowRight, Loader2, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useIsMobile } from '../hooks/useMediaQuery';

interface QuestionInputProps {
  onAsk: (question: string) => Promise<void | boolean>;
  isLoading: boolean;
  remainingQuestions?: number;
  placeholder?: string;
  disabled?: boolean;
  minLength?: number;
  maxLength?: number;
  mode?: string;
}


export function getQuickQuestions(currentMode: string, t: (key: string) => string) {
    const norm = currentMode.toLowerCase();
    if (norm.includes('wojewodztw')) {
      return [
        { icon: '🌊', label: t('inputs.quickWojCoastline'), question: t('inputs.questionWojCoastline') },
        { icon: '⛰️', label: t('inputs.quickWojMountains'), question: t('inputs.questionWojMountains') },
        { icon: '🌐', label: t('inputs.quickWojBorderCountry'), question: t('inputs.questionWojBorderCountry') },
        { icon: '🧭', label: t('inputs.quickWojEast'), question: t('inputs.questionWojEast') },
        { icon: '🧭', label: t('inputs.quickWojWest'), question: t('inputs.questionWojWest') },
        { icon: '🏙️', label: t('inputs.quickWojPopulation1M'), question: t('inputs.questionWojPopulation1M') },
      ];
    }
    if (norm.includes('powiat')) {
      return [
        { icon: '🏙️', label: t('inputs.quickPowCityCounty'), question: t('inputs.questionPowCityCounty') },
        { icon: '🌳', label: t('inputs.quickPowLandCounty'), question: t('inputs.questionPowLandCounty') },
        { icon: '🌊', label: t('inputs.quickPowCoastline'), question: t('inputs.questionPowCoastline') },
        { icon: '⛰️', label: t('inputs.quickPowMountains'), question: t('inputs.questionPowMountains') },
        { icon: '🧭', label: t('inputs.quickPowSouth'), question: t('inputs.questionPowSouth') },
        { icon: '🌐', label: t('inputs.quickPowBorderCountry'), question: t('inputs.questionPowBorderCountry') },
      ];
    }
    if (norm.includes('us_state') || norm.includes('usstate') || norm.includes('us-state')) {
      return [
        { icon: '🌊', label: t('inputs.quickUsCoastal'), question: t('inputs.questionUsCoastal') },
        { icon: '🌽', label: t('inputs.quickUsMidwest'), question: t('inputs.questionUsMidwest') },
        { icon: '🦞', label: t('inputs.quickUsNewEngland'), question: t('inputs.questionUsNewEngland') },
        { icon: '🌵', label: t('inputs.quickUsSouth'), question: t('inputs.questionUsSouth') },
        { icon: '🏔️', label: t('inputs.quickUsWest'), question: t('inputs.questionUsWest') },
        { icon: '⚔️', label: t('inputs.quickUsConfederacy'), question: t('inputs.questionUsConfederacy') },
      ];
    }
    if (norm === 'europe') {
      return [
        { icon: '🇪🇺', label: t('inputs.quickEu'), question: t('inputs.questionEu') },
        { icon: '🌊', label: t('inputs.quickCoastline'), question: t('inputs.questionCoastline') },
        { icon: '👑', label: t('inputs.quickMonarchy'), question: t('inputs.questionMonarchy') },
        { icon: '💶', label: t('inputs.quickContEuro'), question: t('inputs.questionContEuro') },
        { icon: '🛡️', label: t('inputs.quickContNato'), question: t('inputs.questionContNato') },
        { icon: '🏝️', label: t('inputs.quickIsland'), question: t('inputs.questionIsland') },
      ];
    }
    if (norm === 'asia') {
      return [
        { icon: '🏝️', label: t('inputs.quickIsland'), question: t('inputs.questionIsland') },
        { icon: '🌊', label: t('inputs.quickCoastline'), question: t('inputs.questionCoastline') },
        { icon: '🚗', label: t('inputs.quickLeftHandDrive'), question: t('inputs.questionLeftHandDrive') },
        { icon: '👑', label: t('inputs.quickMonarchy'), question: t('inputs.questionMonarchy') },
        { icon: '🕌', label: t('inputs.quickAsiaIslam'), question: t('inputs.questionAsiaIslam') },
        { icon: '🌏', label: t('inputs.quickAsiaSoutheast'), question: t('inputs.questionAsiaSoutheast') },
      ];
    }
    if (norm === 'africa') {
      return [
        { icon: '🌊', label: t('inputs.quickCoastline'), question: t('inputs.questionCoastline') },
        { icon: '🏜️', label: t('inputs.quickAfricaNorth'), question: t('inputs.questionAfricaNorth') },
        { icon: '🏝️', label: t('inputs.quickIsland'), question: t('inputs.questionIsland') },
        { icon: '🧭', label: t('inputs.quickAfricaSouthEquator'), question: t('inputs.questionAfricaSouthEquator') },
        { icon: '🗣️', label: t('inputs.quickAfricaFrench'), question: t('inputs.questionAfricaFrench') },
        { icon: '🗣️', label: t('inputs.quickAfricaEnglish'), question: t('inputs.questionAfricaEnglish') },
      ];
    }
    if (norm === 'americas') {
      return [
        { icon: '🌎', label: t('inputs.quickAmericasSouth'), question: t('inputs.questionAmericasSouth') },
        { icon: '🏝️', label: t('inputs.quickAmericasCaribbean'), question: t('inputs.questionAmericasCaribbean') },
        { icon: '🌊', label: t('inputs.quickAmericasPacific'), question: t('inputs.questionAmericasPacific') },
        { icon: '🗣️', label: t('inputs.quickAmericasSpanish'), question: t('inputs.questionAmericasSpanish') },
        { icon: '🧭', label: t('inputs.quickAmericasSouthEquator'), question: t('inputs.questionAmericasSouthEquator') },
        { icon: '🚗', label: t('inputs.quickLeftHandDrive'), question: t('inputs.questionLeftHandDrive') },
      ];
    }
    return [
      { icon: '🌍', label: t('inputs.quickEurope'), question: t('inputs.questionEurope') },
      { icon: '🌊', label: t('inputs.quickCoastline'), question: t('inputs.questionCoastline') },
      { icon: '👑', label: t('inputs.quickMonarchy'), question: t('inputs.questionMonarchy') },
      { icon: '🚗', label: t('inputs.quickLeftHandDrive'), question: t('inputs.questionLeftHandDrive') },
      { icon: '🇪🇺', label: t('inputs.quickEu'), question: t('inputs.questionEu') },
      { icon: '🏝️', label: t('inputs.quickIsland'), question: t('inputs.questionIsland') },
    ];
  };
export default function QuestionInput({ onAsk, isLoading, remainingQuestions, placeholder, disabled = false, minLength = 1, maxLength = 100, mode = 'country' }: QuestionInputProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const isMobile = useIsMobile();
  
  const [question, setQuestion] = useState('');
  const unavailable = disabled || isLoading || (remainingQuestions !== undefined && remainingQuestions <= 0);
  const inputRef = useRef<HTMLInputElement>(null);
  const quickQuestionsRef = useRef<HTMLDivElement>(null);
  const focusFrameRef = useRef<number | null>(null);
  const pointerTypeRef = useRef('mouse');
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const restoreFocus = useCallback(() => {
    // Keep the phone/touch keyboard closed while the player works with the map.
    if (!window.matchMedia('(min-width: 768px)').matches || pointerTypeRef.current !== 'mouse') return;
    if (focusFrameRef.current !== null) cancelAnimationFrame(focusFrameRef.current);
    focusFrameRef.current = requestAnimationFrame(() => {
      focusFrameRef.current = null;
      const input = inputRef.current;
      if (!input || input.disabled || !input.getClientRects().length) return;
      const active = document.activeElement;
      const mapFocused = active?.closest('.game-map-layer')
        && !active.closest('.leaflet-control, button, a, input, select, textarea, [role="button"]');
      if (active !== document.body && active !== input
        && active !== input.form?.querySelector('button[type="submit"]') && !mapFocused) return;
      input.focus({ preventScroll: true });
    });
  }, []);

  useEffect(() => {
    const handleMapInteraction = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element) || !target.closest('.game-map-layer')
        || target.closest('.leaflet-control, button, a, input, select, textarea, [role="button"]')) return;
      if (event.type === 'click' ? event.detail === 0 : event.button !== 2) return;
      if (event instanceof PointerEvent && event.pointerType !== 'mouse') return;
      pointerTypeRef.current = 'mouse';
      restoreFocus();
    };
    // Capture before Leaflet stops propagation; restore after its click handlers.
    document.addEventListener('click', handleMapInteraction, true);
    document.addEventListener('contextmenu', handleMapInteraction, true);
    return () => {
      document.removeEventListener('click', handleMapInteraction, true);
      document.removeEventListener('contextmenu', handleMapInteraction, true);
      if (focusFrameRef.current !== null) cancelAnimationFrame(focusFrameRef.current);
    };
  }, [restoreFocus]);
  const updateScrollState = useCallback(() => {
    const el = quickQuestionsRef.current;
    if (!el) return;
    const { scrollLeft, scrollWidth, clientWidth } = el;
    setCanScrollLeft(scrollLeft > 4);
    setCanScrollRight(scrollWidth - (scrollLeft + clientWidth) > 4);
  }, []);

  useEffect(() => {
    updateScrollState();
    const el = quickQuestionsRef.current;
    if (!el) return;
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => {
        updateScrollState();
      });
      observer.observe(el);
      return () => observer.disconnect();
    }
  }, [updateScrollState]);

  useEffect(() => {
    if (quickQuestionsRef.current) {
      quickQuestionsRef.current.scrollLeft = 0;
    }
    updateScrollState();
  }, [mode, updateScrollState]);

  const handleWheel = useCallback((e: React.WheelEvent<HTMLDivElement>) => {
    const el = quickQuestionsRef.current;
    if (!el || el.scrollWidth <= el.clientWidth) return;
    if (e.deltaX === 0 && e.deltaY !== 0) {
      el.scrollLeft += e.deltaY;
    }
  }, []);

  const handleScrollPromptClick = useCallback(() => {
    const el = quickQuestionsRef.current;
    if (!el) return;
    if (canScrollRight) {
      el.scrollBy({ left: 160, behavior: 'smooth' });
    } else if (canScrollLeft) {
      el.scrollBy({ left: -160, behavior: 'smooth' });
    }
  }, [canScrollLeft, canScrollRight]);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim().length < minLength || unavailable) return;
    try {
      if (await onAsk(question) !== false) setQuestion('');
    } finally {
      restoreFocus();
    }
  };

  const quickQuestions = useMemo(() => getQuickQuestions(mode, t), [mode, t]);

  const defaultPlaceholder = useMemo(() => {
    const norm = (mode || '').toLowerCase();
    if (isMobile) {
      if (norm.includes('wojewodztw')) {
        return t('inputs.questionPlaceholderWojMobile', {
          defaultValue: 'Ask about voivodeship…',
        });
      }
      if (norm.includes('powiat')) {
        return t('inputs.questionPlaceholderPowiatMobile', {
          defaultValue: 'Ask about the county…',
        });
      }
      if (norm.includes('us_state') || norm.includes('usstate') || norm.includes('us-state')) {
        return t('inputs.questionPlaceholderUsStateMobile', {
          defaultValue: 'Ask about the state…',
        });
      }
      if (norm === 'europe' || norm === 'asia' || norm === 'africa' || norm === 'americas' || norm === 'country') {
        return t('inputs.questionPlaceholderCountryMobile', {
          defaultValue: 'Ask about the country…',
        });
      }
      return t('inputs.questionPlaceholderMobile', {
        defaultValue: 'Ask a yes/no question…',
      });
    }

    if (remainingQuestions !== undefined) {
      return t('inputs.questionPlaceholder', {
        count: remainingQuestions,
        defaultValue: `Ask a yes/no question (e.g., "Is it in Europe?") - ${remainingQuestions} left`,
      });
    }
    return t('inputs.questionPlaceholderNoCount', {
      defaultValue: 'Ask a yes/no question (e.g., "Is it in Europe?")',
    });
  }, [isMobile, mode, remainingQuestions, t]);

  const resolvedPlaceholder = isMobile
    ? defaultPlaceholder
    : (placeholder || defaultPlaceholder);

  const scrollPrompt = useMemo(() => {
    if (!canScrollLeft && canScrollRight) {
      return t('inputs.scrollRightPrompt', 'Scroll →');
    }
    if (canScrollLeft && canScrollRight) {
      return t('inputs.scrollBothPrompt', '← Scroll →');
    }
    if (canScrollLeft && !canScrollRight) {
      return t('inputs.scrollLeftPrompt', '← Scroll');
    }
    return null;
  }, [canScrollLeft, canScrollRight, t]);

  const maskStyle = useMemo<React.CSSProperties | undefined>(() => {
    if (canScrollLeft && canScrollRight) {
      const gradient = 'linear-gradient(to right, transparent 0, black 16px, black calc(100% - 24px), transparent 100%)';
      return { WebkitMaskImage: gradient, maskImage: gradient };
    }
    if (canScrollRight) {
      const gradient = 'linear-gradient(to right, black calc(100% - 24px), transparent 100%)';
      return { WebkitMaskImage: gradient, maskImage: gradient };
    }
    if (canScrollLeft) {
      const gradient = 'linear-gradient(to right, transparent 0, black 16px, black 100%)';
      return { WebkitMaskImage: gradient, maskImage: gradient };
    }
    return undefined;
  }, [canScrollLeft, canScrollRight]);

  return (
    <form onSubmit={handleSubmit} onPointerDownCapture={event => { pointerTypeRef.current = event.pointerType; }} className="flex min-h-0 w-full flex-col">
      <div className="mb-1.5 max-md:[@media(max-height:560px)]:hidden">
        <div className="mb-0.5 flex items-center justify-between gap-2">
          <p className="text-[10px] font-medium text-zinc-500">{t('inputs.quickQuestions')}</p>
          {scrollPrompt && (
            <button
              type="button"
              onClick={handleScrollPromptClick}
              className="inline-flex shrink-0 items-center gap-0.5 text-[9px] font-medium text-emerald-400/90 transition-colors hover:text-emerald-300 focus-visible:outline focus-visible:outline-1 focus-visible:outline-emerald-400 cursor-pointer"
              aria-label={t('inputs.scrollQuickQuestions')}
            >
              <span aria-hidden="true">{scrollPrompt}</span>
            </button>
          )}
        </div>
        <div className="relative">
          <div
            ref={quickQuestionsRef}
            onScroll={updateScrollState}
            onWheel={handleWheel}
            style={maskStyle}
            className="no-scrollbar flex gap-1.5 overflow-x-auto pb-0.5 touch-pan-x overscroll-x-contain scroll-smooth"
            aria-label={t('inputs.quickQuestions')}
          >
            {quickQuestions.map(({ icon, label, question: suggestedQuestion }) => (
              <button
                key={label}
                type="button"
                disabled={unavailable}
                onClick={() => setQuestion(suggestedQuestion)}
                className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-zinc-300 transition-colors hover:border-emerald-400/30 hover:bg-emerald-400/10 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 disabled:opacity-40"
              >
                <span aria-hidden="true">{icon}</span>{label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <label htmlFor={inputId} className="sr-only">{'Yes-or-no question'}</label>
      <div className="relative flex items-center">
        <input
          id={inputId}
          ref={inputRef}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={resolvedPlaceholder}
          minLength={minLength}
          maxLength={maxLength}
          className="w-full rounded-sm border border-white/15 bg-obsidian-950 py-3 pl-10 pr-28 text-base text-sand-100 placeholder:text-zinc-500 focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-40 sm:text-sm"
          disabled={unavailable}
        />
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
        <button
          type="submit"
          aria-label={'Ask question'}
          disabled={question.trim().length < minLength || unavailable}
          className="absolute right-1 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center gap-2 rounded-sm bg-emerald-400 px-3 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:opacity-40"
        >
          <span>{'Ask'}</span>
          {isLoading ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight size={14} aria-hidden="true" />
          )}

        </button>
      </div>
    </form>
  );
}
