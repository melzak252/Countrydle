import { useId } from 'react';
import { AlertTriangle, Check, ChevronDown, Copy, HelpCircle, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';
import type { AnswerReportMode, Question } from '../types';
import type { GameplayNotice } from '../lib/gameplayNotices';
import { getConversationMessages } from '../lib/chatMessages';
import AnswerReportForm from './AnswerReportForm';

interface ResultsQuestionHistoryProps {
  questions: Question[];
  mode: AnswerReportMode;
  notices?: GameplayNotice[];
}

export default function ResultsQuestionHistory({ questions, mode, notices = [] }: ResultsQuestionHistoryProps) {
  const { t } = useTranslation();
  const disclosureGroup = useId();
  const copyQuestion = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t('chat.questionCopied', 'Question copied to clipboard.'));
    } catch {
      toast.error(t('chat.copyFailed', 'Could not copy the question. Select its text and copy it manually.'));
    }
  };

  return (
    <ol aria-label={t('chat.historyTitle', 'Question History')} className="min-w-0 space-y-2 select-text">
      {getConversationMessages(questions, notices).map(message => {
        const question = message.kind === 'question' ? message.question : null;
        const notice = message.kind === 'notice' ? message.notice : null;
        const input = message.kind === 'question' ? message.question.original_question : message.notice.input;
        const warning = Boolean(notice) || question?.valid === false;
        const answer = notice
          ? t('chat.notice', 'Notice')
          : warning
          ? t('chat.invalidAnswer', 'Invalid')
          : question?.answer === true
          ? t('chat.answerYes', 'Yes')
          : question?.answer === false
          ? t('chat.answerNo', 'No')
          : t('chat.answerUnknown', 'Unknown');
        const Icon = warning ? AlertTriangle : question?.answer === true ? Check : question?.answer === false ? X : HelpCircle;
        const tone = warning ? 'text-amber-300 bg-amber-400/10' : question?.answer === true ? 'text-emerald-300 bg-emerald-400/10' : question?.answer === false ? 'text-rose-300 bg-rose-400/10' : 'text-zinc-300 bg-white/5';

        return (
          <li key={message.kind === 'question' ? `question-${message.question.id}` : `notice-${message.notice.id}`} className="min-w-0">
            <details name={disclosureGroup} className="group rounded-sm border border-white/10 bg-obsidian-900/40">
              <summary className="flex min-h-12 cursor-pointer list-none items-start gap-2 px-3 py-3 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 [&::-webkit-details-marker]:hidden">
                <span className="w-5 shrink-0 pt-0.5 font-mono text-xs text-zinc-500">
                  {message.kind === 'question' ? message.index + 1 : '—'}
                </span>
                <span className="min-w-0 flex-1 leading-relaxed text-sand-100 [overflow-wrap:anywhere]">{input}</span>
                <span className={`inline-flex shrink-0 items-center gap-1 rounded-sm px-1.5 py-1 text-[10px] font-semibold ${tone}`}>
                  <Icon size={12} aria-hidden="true" />
                  {answer}
                </span>
                <ChevronDown size={15} className="mt-1 shrink-0 text-zinc-400 transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div className="space-y-3 border-t border-white/10 px-3 py-3 text-xs leading-relaxed text-zinc-300 [overflow-wrap:anywhere]">
                {notice ? (
                  <div className="space-y-2">
                    <p className="font-semibold text-amber-300">{notice.title}</p>
                    <p className="whitespace-pre-wrap">{notice.reason}</p>
                    {notice.nextStep && <p className="text-amber-200/80">{notice.nextStep}</p>}
                  </div>
                ) : question?.explanation ? (
                  <p className="whitespace-pre-wrap">{question.explanation}</p>
                ) : null}
                <button
                  type="button"
                  onClick={() => void copyQuestion(input)}
                  className="inline-flex min-h-11 items-center gap-2 rounded-sm px-2 text-xs text-zinc-400 hover:bg-white/5 hover:text-sand-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
                >
                  <Copy size={14} aria-hidden="true" />
                  {t('chat.copyQuestion', 'Copy question')}
                </button>
                {question && question.id > 0 && (
                  <AnswerReportForm mode={mode} questionId={question.id} reportToken={question.report_token} compact />
                )}
              </div>
            </details>
          </li>
        );
      })}
    </ol>
  );
}
