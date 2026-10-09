import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

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
  const { t, i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');
  const inputId = useId();
  
  const [question, setQuestion] = useState('');
  const unavailable = disabled || isLoading || (remainingQuestions !== undefined && remainingQuestions <= 0);
  const inputRef = useRef<HTMLInputElement>(null);
  const focusFrameRef = useRef<number | null>(null);
  const pointerTypeRef = useRef('mouse');

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


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim().length < minLength || unavailable) return;
    try {
      if (await onAsk(question) !== false) setQuestion('');
    } finally {
      restoreFocus();
    }
  };

  const defaultPlaceholder = t('inputs.questionPlaceholder', { count: remainingQuestions });


  const quickQuestions = getQuickQuestions(mode, t);

  return (
    <form onSubmit={handleSubmit} onPointerDownCapture={event => { pointerTypeRef.current = event.pointerType; }} className="flex min-h-0 w-full flex-col">
      <div className="mb-2 max-md:[@media(max-height:560px)]:hidden">
        <div className="mb-1 flex items-center justify-between gap-2">
          <p className="text-[11px] font-medium text-zinc-500">{t('inputs.quickQuestions')}</p>
          <span className="shrink-0 text-[10px] text-zinc-500" aria-hidden="true">{isPl ? 'Przewiń →' : 'Scroll →'}</span>
        </div>
        <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1" aria-label={t('inputs.quickQuestions')}>
          {quickQuestions.map(({ icon, label, question: suggestedQuestion }) => (
            <button
              key={label}
              type="button"
              disabled={unavailable}
              onClick={() => setQuestion(suggestedQuestion)}
              className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-zinc-300 transition-colors hover:border-emerald-400/30 hover:bg-emerald-400/10 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 disabled:opacity-40"
            >
              <span aria-hidden="true">{icon}</span>{label}
            </button>
          ))}
        </div>
      </div>
      <label htmlFor={inputId} className="sr-only">{isPl ? 'Pytanie tak lub nie' : 'Yes-or-no question'}</label>
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/90 p-1 shadow-lg shadow-black/20 transition-colors focus-within:border-emerald-500/50 focus-within:ring-2 focus-within:ring-emerald-500/20">
        <input
          id={inputId}
          ref={inputRef}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder || defaultPlaceholder}
          minLength={minLength}
          maxLength={maxLength}
          className="w-full rounded-xl border-0 bg-transparent py-3 pl-4 pr-14 text-base text-sand-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 disabled:opacity-40 sm:text-sm"
          disabled={unavailable}
        />
        <button
          type="submit"
          aria-label={isPl ? 'Zadaj pytanie' : 'Ask question'}
          disabled={question.trim().length < minLength || unavailable}
          className="absolute right-1.5 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-xl bg-transparent text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:opacity-40 enabled:bg-emerald-500 enabled:text-white enabled:hover:bg-emerald-400"
        >

          {isLoading ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Send size={16} aria-hidden="true" />
          )}

        </button>
      </div>
    </form>
  );
}
