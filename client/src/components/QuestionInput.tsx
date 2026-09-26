import { useEffect, useId, useState } from 'react';
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
}

function SlowQuestionNotice({ message }: { message: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 1500);
    return () => window.clearTimeout(timer);
  }, []);
  return visible ? <div role="status" className="mt-2 flex items-center gap-2 text-xs text-zinc-400">
    <Loader2 size={13} className="animate-spin" /><span>{message}</span>
  </div> : null;
}

export default function QuestionInput({ onAsk, isLoading, remainingQuestions, placeholder, disabled = false, minLength = 1, maxLength = 100 }: QuestionInputProps) {
  const { t } = useTranslation();
  const inputId = useId();
  
  const [question, setQuestion] = useState('');
  const unavailable = disabled || isLoading || (remainingQuestions !== undefined && remainingQuestions <= 0);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim().length < minLength || unavailable) return;
    if (await onAsk(question) !== false) setQuestion('');
  };

  const defaultPlaceholder = t('inputs.questionPlaceholder', { count: remainingQuestions });

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <label htmlFor={inputId} className="sr-only">{'Yes-or-no question'}</label>
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/90 p-1 shadow-lg shadow-black/20 transition-colors focus-within:border-emerald-500/50 focus-within:ring-2 focus-within:ring-emerald-500/20">
        <input
          id={inputId}
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
          aria-label={'Ask question'}
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
      {isLoading && <SlowQuestionNotice message={t('inputs.slowQuestionMessage')} />}
    </form>
  );
}
