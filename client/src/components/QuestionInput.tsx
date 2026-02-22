import { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface QuestionInputProps {
  onAsk: (question: string) => Promise<void>;
  isLoading: boolean;
  remainingQuestions: number;
  placeholder?: string;
}

export default function QuestionInput({ onAsk, isLoading, remainingQuestions, placeholder }: QuestionInputProps) {
  const [question, setQuestion] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    
    await onAsk(question);
    setQuestion('');
  };

  const defaultPlaceholder = `Ask a yes/no question (e.g., "Is it in Europe?") - ${remainingQuestions} left`;

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto mb-8">
      <div className="relative">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={placeholder || defaultPlaceholder}
          maxLength={100}
          className="w-full bg-zinc-800 border-2 border-zinc-700 rounded-xl px-6 py-4 pr-14 text-lg focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
          disabled={isLoading || remainingQuestions <= 0}
        />
        <button
          type="submit"
          disabled={!question.trim() || isLoading || remainingQuestions <= 0}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
        >
          {isLoading ? (
            <Loader2 size={20} className="animate-spin" />
          ) : (
            <Send size={20} />
          )}
        </button>
      </div>
    </form>
  );
}
