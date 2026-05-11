import { useEffect, useState } from 'react';
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
    if (!question.trim() || isLoading) return;
    
    await onAsk(question);
    setQuestion('');
  };

  const defaultPlaceholder = `Ask a yes/no question (e.g., "Is it in Europe?") - ${remainingQuestions} left`;

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="relative">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder || defaultPlaceholder}
          maxLength={100}
          className="w-full bg-zinc-800 border-2 border-zinc-700 rounded-xl px-3 py-2 md:px-4 md:py-3 pr-10 md:pr-12 text-sm md:text-base focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
          disabled={isLoading || remainingQuestions <= 0}
        />
        <button
          type="submit"
          disabled={!question.trim() || isLoading || remainingQuestions <= 0}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
        >

          {isLoading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}

        </button>
      </div>
      {showSlowMessage && (
        <div className="mt-2 flex items-center justify-center gap-2 text-xs text-amber-300/90">
          <Loader2 size={13} className="animate-spin" />
          <span>{t('inputs.slowQuestionMessage')}</span>
        </div>
      )}
    </form>
  );
}
