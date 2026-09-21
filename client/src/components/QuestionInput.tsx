import { useEffect, useId, useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface QuestionInputProps {
  onAsk: (question: string) => Promise<void>;
  isLoading: boolean;
  remainingQuestions: number;
  placeholder?: string;
}

export default function QuestionInput({ onAsk, isLoading, remainingQuestions, placeholder }: QuestionInputProps) {
  const { t } = useTranslation();
  const inputId = useId();
  
  const [question, setQuestion] = useState('');
  const [showSlowMessage, setShowSlowMessage] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      setShowSlowMessage(false);
      return;
    }

    const timeout = window.setTimeout(() => {
      setShowSlowMessage(true);
    }, 1500);

    return () => window.clearTimeout(timeout);
  }, [isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading || remainingQuestions <= 0) return;
    
    await onAsk(question);
    setQuestion('');
  };

  const defaultPlaceholder = t('inputs.questionPlaceholder', { count: remainingQuestions });

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <label htmlFor={inputId} className="sr-only">{'Yes-or-no question'}</label>
      <div className="relative">
        <input
          id={inputId}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder || defaultPlaceholder}
          maxLength={100}
          className="w-full rounded-sm border border-white/15 bg-obsidian-950 py-3 pl-3 pr-14 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-40"
          disabled={isLoading || remainingQuestions <= 0}
        />
        <button
          type="submit"
          aria-label={'Ask question'}
          disabled={!question.trim() || isLoading || remainingQuestions <= 0}
          className="absolute right-1 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-sm text-emerald-400 transition-colors hover:bg-emerald-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 disabled:opacity-40"
        >

          {isLoading ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Send size={16} aria-hidden="true" />
          )}

        </button>
      </div>
      {showSlowMessage && (
        <div role="status" className="mt-2 flex items-center gap-2 text-xs text-zinc-400">
          <Loader2 size={13} className="animate-spin" />
          <span>{t('inputs.slowQuestionMessage')}</span>
        </div>
      )}
    </form>
  );
}
