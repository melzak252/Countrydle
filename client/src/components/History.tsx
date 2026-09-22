import type { AnswerReportMode, Question } from '../types';
import { Check, X, HelpCircle, ChevronDown, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import AnswerReportForm from './AnswerReportForm';

interface HistoryProps {
  questions: Question[];
  mode: AnswerReportMode;
  isGameOver?: boolean;
}

export default function History({ questions, mode, isGameOver = false }: HistoryProps) {
  const { t } = useTranslation();
  
  const sortedQuestions = [...questions].reverse();

  if (sortedQuestions.length === 0) {
    return (
      <div className="border border-dashed border-white/10 px-4 py-7 text-center">
        <HelpCircle size={22} className="mx-auto mb-3 text-zinc-600" aria-hidden="true" />
        <p className="text-sm leading-relaxed text-zinc-500">{t('history.empty')}</p>
      </div>
    );
  }

  return (
    <ol className="space-y-3">
      {sortedQuestions.map(q => {
        // Valid explanations may reveal the answer, so never mount them during play.
        const showExplanation = Boolean(q.explanation) && (!q.valid || isGameOver);
        const answerLabel = !q.valid ? ('Invalid question') : q.answer === true ? ('Yes') : q.answer === false ? ('No') : ('Unknown');
        const answerColor = !q.valid ? 'border-amber-300/15 bg-amber-300/[0.08] text-amber-200' : q.answer === true ? 'border-emerald-300/15 bg-emerald-300/[0.10] text-emerald-300' : q.answer === false ? 'border-rose-300/15 bg-rose-300/[0.10] text-rose-300' : 'border-white/10 bg-white/5 text-zinc-300';
        const content = (
          <>
            <p className="break-words px-4 py-4 text-base font-medium leading-6 text-sand-100">{q.original_question}</p>
            <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t px-4 py-3 ${answerColor}`}>
              <span className={`inline-flex items-center gap-2.5 font-semibold ${q.valid && q.answer !== null ? 'text-lg uppercase tracking-wide' : 'text-sm'}`}>
                {!q.valid ? <AlertTriangle size={20} aria-hidden="true" /> : q.answer === true ? <Check size={23} strokeWidth={2.5} aria-hidden="true" /> : q.answer === false ? <X size={23} strokeWidth={2.5} aria-hidden="true" /> : <HelpCircle size={20} aria-hidden="true" />}
                {answerLabel}
              </span>
              {showExplanation && (
                <span className="inline-flex items-center gap-1.5 text-xs text-zinc-300">
                  {'Explanation'}
                  <ChevronDown size={14} className="transition-transform group-open:rotate-180" aria-hidden="true" />
                </span>
              )}
            </div>
          </>
        );

        return (
          <li key={q.id} className="overflow-hidden rounded-md border border-white/15 bg-obsidian-950">
            {showExplanation ? (
              <details className="group">
                <summary className="cursor-pointer list-none focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-300 [&::-webkit-details-marker]:hidden">
                  {content}
                </summary>
                <div className={`border-t border-white/10 px-4 py-4 text-sm leading-relaxed ${q.valid ? 'text-zinc-300' : 'text-amber-200'}`}>
                  {!q.valid && <p className="mb-1 font-medium">{t('history.invalidReason')}</p>}
                  <p>{q.explanation}</p>
                </div>
              </details>
            ) : content}
            {isGameOver && q.id > 0 && <AnswerReportForm key={`${mode}-${q.id}`} mode={mode} questionId={q.id} reportToken={q.report_token} />}
          </li>
        );
      })}
    </ol>
  );
}
