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
      <div className="rounded-sm border border-dashed border-app-border/30 bg-app-surface-muted/40 px-4 py-7 text-center">
        <HelpCircle size={22} className="mx-auto mb-3 text-app-text-muted" aria-hidden="true" />
        <p className="text-sm leading-relaxed text-app-text-muted">{t('history.empty')}</p>
      </div>
    );
  }

  return (
    <ol className="space-y-3">
      {sortedQuestions.map(q => {
        // Valid explanations may reveal the answer, so never mount them during play.
        const showExplanation = Boolean(q.explanation) && (!q.valid || isGameOver);
        const answerLabel = !q.valid ? ('Invalid question') : q.answer === true ? ('Yes') : q.answer === false ? ('No') : ('Unknown');
        const answerColor = !q.valid ? 'border-amber-700/20 bg-amber-600/10 text-amber-900' : q.answer === true ? 'border-emerald-700/20 bg-emerald-600/10 text-emerald-800' : q.answer === false ? 'border-rose-700/20 bg-rose-600/10 text-rose-800' : 'border-app-border/20 bg-app-surface-muted text-app-text-secondary';
        const content = (
          <>
            <p className="break-words px-4 py-4 text-base font-medium leading-6 text-app-text">{q.original_question}</p>
            <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t px-4 py-3 ${answerColor}`}>
              <span className={`inline-flex items-center gap-2.5 font-semibold ${q.valid && q.answer !== null ? 'text-base font-semibold' : 'text-sm'}`}>
                {!q.valid ? <AlertTriangle size={20} aria-hidden="true" /> : q.answer === true ? <Check size={22} strokeWidth={2.5} aria-hidden="true" /> : q.answer === false ? <X size={22} strokeWidth={2.5} aria-hidden="true" /> : <HelpCircle size={20} aria-hidden="true" />}
                <span>
                  {answerLabel}
                  {q.clarification ? `, ${q.clarification.replace(/^(?:Yes,?\s*|No,?\s*)/i, '')}` : ''}
                </span>
              </span>
              {showExplanation && (
                <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-app-text-secondary">
                  {'Explanation'}
                  <ChevronDown size={14} className="transition-transform group-open:rotate-180" aria-hidden="true" />
                </span>
              )}
            </div>
          </>
        );

        return (
          <li key={q.id} className="overflow-hidden rounded-sm border border-app-border/20 bg-app-surface">
            {showExplanation ? (
              <details className="group">
                <summary className="cursor-pointer list-none focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-app-focus [&::-webkit-details-marker]:hidden">
                  {content}
                </summary>
                <div className={`border-t border-app-border/15 px-4 py-4 text-sm leading-relaxed ${q.valid ? 'text-app-text-secondary' : 'text-amber-900'}`}>
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
