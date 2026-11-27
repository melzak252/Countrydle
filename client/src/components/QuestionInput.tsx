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


export default function QuestionInput({ onAsk, isLoading, remainingQuestions, placeholder, disabled = false, minLength = 1, maxLength = 100, mode = 'country' }: QuestionInputProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const isMobile = useIsMobile();
  
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


  const defaultPlaceholder = useMemo(() => {
    const norm = (mode || '').toLowerCase();
    if (isMobile) {
      if (norm.includes('countydle') || norm === 'english_counties') {
        return t('inputs.questionPlaceholderCountyMobile', {
          defaultValue: 'Ask about county…',
        });
      }
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
        defaultValue: `Ask a yes/no question - ${remainingQuestions} left`,
      });
    }
    return t('inputs.questionPlaceholderNoCount', {
      defaultValue: 'Ask a yes/no question',
    });
  }, [isMobile, mode, remainingQuestions, t]);

  const resolvedPlaceholder = isMobile
    ? defaultPlaceholder
    : (placeholder || defaultPlaceholder);


  return (
    <form onSubmit={handleSubmit} onPointerDownCapture={event => { pointerTypeRef.current = event.pointerType; }} className="flex min-h-0 w-full flex-col">
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
          className="w-full rounded-sm border border-app-border/35 bg-app-surface-raised py-3 pl-10 pr-28 text-base text-app-text placeholder:text-app-text-secondary focus:border-app-focus focus:outline-none focus:ring-1 focus:ring-app-focus/20 disabled:bg-app-surface-muted disabled:text-app-text-muted disabled:opacity-100 sm:text-sm"
          disabled={unavailable}
        />
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-text-secondary" aria-hidden="true" />
        <button
          type="submit"
          aria-label={'Ask question'}
          disabled={question.trim().length < minLength || unavailable}
          className="absolute right-0 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center gap-2 rounded-sm border border-app-accent bg-app-accent px-3 text-sm font-semibold text-white transition-colors hover:bg-app-accent-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus disabled:border-app-border/35 disabled:bg-app-surface-muted disabled:text-app-text-secondary disabled:opacity-100"
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
