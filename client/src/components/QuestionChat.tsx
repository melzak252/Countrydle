import { AlertTriangle, Check, Compass, Copy, HelpCircle, MessageCircle, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import type { AnswerReportMode, Question } from '../types';
import AnswerReportForm from './AnswerReportForm';
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
    <div className="inline-flex max-w-full items-start gap-2 rounded-2xl rounded-br-md border border-emerald-300/15 bg-emerald-400/[0.12] px-3.5 py-2 text-xs sm:text-sm leading-relaxed text-sand-100 [overflow-wrap:anywhere]">
      <span className="min-w-0 flex-1 select-text">{question}</span>
      <button
        type="button"
        aria-label={copyLabel}
        title={copyLabel}
        onClick={() => void onCopy(question)}
        className="mt-0.5 shrink-0 rounded p-1 text-sand-100/65 transition-colors hover:bg-white/10 hover:text-sand-100"
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
      <div className="flex min-h-52 flex-col items-center justify-center px-5 py-8 text-center select-text">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-300/15 bg-emerald-400/10 text-emerald-300">
          <MessageCircle size={23} aria-hidden="true" />
        </div>
        <p className="text-sm font-semibold text-sand-100">Every question is a clue</p>
        <p className="mt-2 max-w-60 text-sm leading-relaxed text-zinc-400">Ask a yes-or-no question below to start narrowing it down.</p>
        <p className="mt-4 rounded-2xl rounded-br-md border border-white/10 bg-white/5 px-4 py-2.5 text-xs text-zinc-400">Try “Does it have a coastline?”</p>
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
                <span className="mb-1 px-1 text-[10px] font-medium text-zinc-500">You · {notice.action}</span>
                <PlayerQuestionBubble question={notice.input} copyLabel={copyLabel} onCopy={copyQuestion} />
              </div>
              <div role="alert" className="flex flex-col items-start pr-6">
                <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-medium text-zinc-400">
                  <Compass size={13} className="text-emerald-400" aria-hidden="true" />
                  <span>Countrydle</span>
                </div>
                <div className="w-fit max-w-[92%] rounded-2xl rounded-tl-md border border-amber-400/25 bg-amber-400/[0.08] px-3.5 py-2.5 text-xs text-amber-200 space-y-1 shadow-sm">
                  <div className="flex items-center gap-1.5 font-semibold text-amber-300 text-xs">
                    <AlertTriangle size={13} className="shrink-0 text-amber-400" aria-hidden="true" />
                    <span>{notice.title}</span>
                  </div>
                  <p className="text-zinc-300 leading-snug">{notice.reason}</p>
                  {notice.nextStep && (
                    <p className="text-amber-200/75 text-[11px] pt-1 border-t border-amber-400/15">{notice.nextStep}</p>
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
        const tone = !question.valid ? 'bg-amber-400/10 text-amber-200' : question.answer === true ? 'bg-emerald-400/10 text-emerald-300' : question.answer === false ? 'bg-rose-400/10 text-rose-300' : 'bg-white/5 text-zinc-300';

        return (
          <li key={`question-${question.id}`} className="space-y-2 animate-message">
            <div className="flex flex-col items-end pl-6">
              <span className="mb-1 px-1 text-[10px] font-medium text-zinc-500">You · {index + 1}</span>
              <PlayerQuestionBubble question={question.original_question} copyLabel={copyLabel} onCopy={copyQuestion} />
            </div>
            <div className="flex flex-col items-start pr-6">
              <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-medium text-zinc-400">
                <Compass size={13} className="text-emerald-400" aria-hidden="true" />
                <span>Countrydle</span>
              </div>
              <div className="w-fit max-w-[92%] overflow-hidden rounded-2xl rounded-tl-md border border-white/10 bg-white/[0.045] px-3.5 py-2.5 space-y-1.5 shadow-sm">
                <div>
                  <span className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold ${tone}`}>
                    <Icon size={14} strokeWidth={2.5} aria-hidden="true" />
                    {answer}
                  </span>
                </div>
                {showExplanation && (
                  <div className="text-xs leading-relaxed text-zinc-300 [overflow-wrap:anywhere] pt-0.5">
                    {!question.valid && <p className="mb-0.5 font-medium text-amber-200">Try rephrasing your question</p>}
                    <p className="text-zinc-400">{question.explanation}</p>
                  </div>
                )}
                {isGameOver && question.id > 0 && (
                  <div className="pt-2 border-t border-white/10">
                    <AnswerReportForm mode={mode} questionId={question.id} reportToken={question.report_token} />
                  </div>
                )}
              </div>
            </div>
          </li>
        );
      })}
      {isLoading && pendingQuestion && (
        <li key="pending-question-turn" className="space-y-2 animate-message">
          <div className="flex flex-col items-end pl-6">
            <span className="mb-1 px-1 text-[10px] font-medium text-zinc-500">
              You · {questions.length + 1}
            </span>
            <PlayerQuestionBubble question={pendingQuestion} copyLabel={copyLabel} onCopy={copyQuestion} />
          </div>
          <div className="flex flex-col items-start pr-6">
            <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] font-medium text-zinc-400">
              <Compass size={13} className="text-emerald-400 animate-spin-slow" aria-hidden="true" />
              <span>{t('inputs.thinking', { defaultValue: 'Countrydle is thinking...' })}</span>
            </div>
            <div className="w-fit rounded-2xl rounded-tl-md border border-white/10 bg-white/[0.045] px-3.5 py-2 shadow-inner">
              <div className="flex items-center gap-1.5 py-0.5 px-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-typing-dot-1" />
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-typing-dot-2" />
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-typing-dot-3" />
              </div>
            </div>
          </div>
        </li>
      )}
    </ol>
  );
}
