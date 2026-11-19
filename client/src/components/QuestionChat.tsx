import { AlertTriangle, Check, Compass, Copy, HelpCircle, MessageCircle, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import type { AnswerReportMode, Question } from '../types';
import AnswerReportForm from './AnswerReportForm';
import FactProvenance from './FactProvenance';
import type { GameplayNotice } from '../lib/gameplayNotices';
import { getConversationMessages } from '../lib/chatMessages';

interface QuestionChatProps {
  questions: Question[];
  mode: AnswerReportMode;
  isGameOver: boolean;
  notices?: GameplayNotice[];
  isLoading?: boolean;
  pendingQuestion?: string | null;
}

interface PlayerQuestionBubbleProps {
  question: string;
  copyLabel: string;
  onCopy: (question: string) => Promise<void>;
}

function PlayerQuestionBubble({ question, copyLabel, onCopy }: PlayerQuestionBubbleProps) {
  return (
    <div className="inline-flex max-w-full items-start gap-2 rounded-sm border border-app-accent/20 bg-app-accent/10 px-3.5 py-2 text-sm leading-relaxed text-app-text [overflow-wrap:anywhere]">
      <span className="min-w-0 flex-1 select-text">{question}</span>
      <button
        type="button"
        aria-label={copyLabel}
        title={copyLabel}
        onClick={() => void onCopy(question)}
        className="my-[-0.5rem] mr-[-0.5rem] flex h-11 w-11 shrink-0 items-center justify-center rounded-sm p-1 text-app-text-secondary transition-colors hover:bg-app-surface-muted hover:text-app-text"
      >
        <Copy size={14} aria-hidden="true" />
      </button>
    </div>
  );
}


export default function QuestionChat({
  questions,
  mode,
  isGameOver,
  notices = [],
  isLoading = false,
  pendingQuestion = null,
}: QuestionChatProps) {
  const { t } = useTranslation();
  const [isSlowThinking, setIsSlowThinking] = useState(false);
  useEffect(() => {
    if (!isLoading || !pendingQuestion) {
      setIsSlowThinking(false);
      return;
    }
    const timer = window.setTimeout(() => setIsSlowThinking(true), 1200);
    return () => window.clearTimeout(timer);
  }, [isLoading, pendingQuestion]);
  
  const copyLabel = t('chat.copyQuestion', { defaultValue: 'Copy question' });
  const copyQuestion = async (question: string) => {
    try {
      await navigator.clipboard.writeText(question);
      toast.success(t('chat.questionCopied', { defaultValue: 'Question copied to clipboard.' }));
    } catch {
      toast.error(t('chat.copyFailed', { defaultValue: 'Could not copy the question. Select its text and copy it manually.' }));
    }
  };

  if (questions.length === 0 && notices.length === 0 && !pendingQuestion) {
    return (
      <div className="flex min-h-20 flex-col items-center justify-center px-5 py-2 text-center select-text md:min-h-52 md:py-8">
        <div className="mb-4 hidden h-12 w-12 items-center justify-center rounded-sm border border-app-accent/20 bg-app-accent/10 text-app-accent md:flex">
          <MessageCircle size={23} aria-hidden="true" />
        </div>
        <p className="text-sm font-semibold text-app-text">{'Every question is a clue'}</p>
        <p className="mt-1 max-w-60 text-sm leading-relaxed text-app-text-secondary md:mt-2">{'Ask a yes-or-no question below to start narrowing it down.'}</p>
      </div>
    );
  }

  const messages = getConversationMessages(questions, notices);

  return (
    <ol aria-label="Question conversation" className="space-y-4 py-1 select-text">
      {messages.map(message => {
        if (message.kind === 'notice') {
          const { notice } = message;
          return (
            <li key={notice.id} className="space-y-2 animate-message">
              <div className="flex flex-col items-end pl-6">
                <span className="mb-1 px-1 text-xs font-medium text-app-text-secondary">You · {notice.action}</span>
                <PlayerQuestionBubble question={notice.input} copyLabel={copyLabel} onCopy={copyQuestion} />
              </div>
              <div role="alert" className="flex flex-col items-start pr-6">
                <div className="flex items-center gap-1.5 mb-1 px-1 text-xs font-medium text-app-text-secondary">
                  <Compass size={13} className="text-app-accent" aria-hidden="true" />
                  <span>Countrydle</span>
                </div>
                <div className="w-fit max-w-[92%] rounded-sm border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/60 dark:text-amber-200 space-y-1 shadow-sm">
                  <div className="flex items-center gap-1.5 font-semibold text-amber-900 dark:text-amber-200 text-sm">
                    <AlertTriangle size={13} className="shrink-0 text-amber-700 dark:text-amber-300" aria-hidden="true" />
                    <span>{notice.title}</span>
                  </div>
                  <p className="text-app-text-secondary leading-snug">{notice.reason}</p>
                  {notice.nextStep && (
                    <p className="text-amber-900/80 dark:text-amber-200/80 text-xs pt-1 border-t border-amber-200 dark:border-amber-700/40">{notice.nextStep}</p>
                  )}
                </div>
              </div>
            </li>
          );
        }
        const { question, index } = message;
        // Correct explanations can reveal the target: never mount them during play.
        const showExplanation = Boolean(question.explanation) && (!question.valid || isGameOver);
        const answer = !question.valid ? 'Invalid question' : question.answer === true ? 'Yes' : question.answer === false ? 'No' : 'Unknown';
        const Icon = !question.valid ? AlertTriangle : question.answer === true ? Check : question.answer === false ? X : HelpCircle;
        const tone = !question.valid
          ? 'bg-amber-50 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200 dark:border dark:border-amber-700/50'
          : question.answer === true
            ? 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border dark:border-emerald-700/50'
            : question.answer === false
              ? 'bg-rose-50 text-rose-900 dark:bg-rose-950/60 dark:text-rose-200 dark:border dark:border-rose-700/50'
              : 'bg-app-surface-muted text-app-text-secondary';

        return (
          <li key={`question-${question.id}`} className="space-y-2 animate-message">
            <div className="flex flex-col items-end pl-6">
              <span className="mb-1 px-1 text-xs font-medium text-app-text-secondary">You · {index + 1}</span>
              <PlayerQuestionBubble question={question.original_question} copyLabel={copyLabel} onCopy={copyQuestion} />
            </div>
            <div className="flex flex-col items-start pr-6">
              <div className="flex items-center gap-1.5 mb-1 px-1 text-xs font-medium text-app-text-secondary">
                <Compass size={13} className="text-app-accent" aria-hidden="true" />
                <span>Countrydle</span>
              </div>
              <div className="w-fit max-w-[92%] overflow-hidden rounded-sm border border-app-border/30 bg-app-surface-muted px-3.5 py-2.5 space-y-1.5 shadow-sm">
                <div>
                  <span className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-sm font-semibold ${tone}`}>
                    <Icon size={14} strokeWidth={2.5} aria-hidden="true" />
                    <span>
                      {answer}
                      {question.valid && question.answer !== null && question.clarification
                        ? (() => {
                            const stripped = question.clarification.replace(/^(?:Yes,?\s*|No,?\s*)/i, '');
                            return stripped ? `, ${stripped.charAt(0).toLowerCase()}${stripped.slice(1)}` : '';
                          })()
                        : ''}
                    </span>
                  </span>
                </div>
                {showExplanation && (
                  <div className="text-sm leading-relaxed text-app-text-secondary [overflow-wrap:anywhere] pt-0.5">
                    {!question.valid && <p className="mb-0.5 font-medium text-amber-800 dark:text-amber-300">Try rephrasing your question</p>}
                    <p className="text-app-text-secondary">{question.explanation}</p>
                  </div>
                )}
                {isGameOver && <FactProvenance records={question.fact_provenance} />}
                {isGameOver && question.id > 0 && (
                  <AnswerReportForm mode={mode} questionId={question.id} reportToken={question.report_token} compact />
                )}
              </div>
            </div>
          </li>
        );
      })}
      {isLoading && pendingQuestion && (
        <li key="pending-question-turn" className="space-y-2 animate-message">
          <div className="flex flex-col items-end pl-6">
            <span className="mb-1 px-1 text-xs font-medium text-app-text-secondary">
              You · {questions.length + 1}
            </span>
            <PlayerQuestionBubble question={pendingQuestion} copyLabel={copyLabel} onCopy={copyQuestion} />
          </div>
          <div className="flex flex-col items-start pr-6 space-y-1">
            <div className={`flex items-center gap-1.5 mb-1 px-1 text-xs font-medium transition-colors ${
              isSlowThinking ? 'text-amber-800' : 'text-app-text-secondary'
            }`}>
              <Compass size={13} className={`animate-spin-slow shrink-0 ${isSlowThinking ? 'text-amber-700' : 'text-app-accent'}`} aria-hidden="true" />
              <span className="whitespace-nowrap truncate">
                {isSlowThinking
                  ? t('inputs.slowQuestionMessage')
                  : t('inputs.thinking', { defaultValue: 'Countrydle is thinking...' })}
              </span>
            </div>
            <div className={`w-fit rounded-sm border px-3.5 py-2 shadow-inner transition-colors ${
              isSlowThinking
                ? 'border-amber-200 bg-amber-50 shadow-sm'
                : 'border-app-border/15 bg-app-surface-muted'
            }`}>
              <div className="flex items-center gap-1.5 py-0.5 px-0.5">
                <span className={`h-1.5 w-1.5 rounded-full animate-typing-dot-1 ${isSlowThinking ? 'bg-amber-600' : 'bg-app-accent'}`} />
                <span className={`h-1.5 w-1.5 rounded-full animate-typing-dot-2 ${isSlowThinking ? 'bg-amber-600' : 'bg-app-accent'}`} />
                <span className={`h-1.5 w-1.5 rounded-full animate-typing-dot-3 ${isSlowThinking ? 'bg-amber-600' : 'bg-app-accent'}`} />
              </div>
            </div>
          </div>
        </li>
      )}
    </ol>
  );
}
