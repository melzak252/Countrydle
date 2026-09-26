import { AlertTriangle, Check, ChevronDown, Compass, HelpCircle, MessageCircle, X } from 'lucide-react';
import type { AnswerReportMode, Question } from '../types';
import AnswerReportForm from './AnswerReportForm';
import type { GameplayNotice } from '../lib/gameplayNotices';
import { getConversationMessages } from '../lib/chatMessages';

interface QuestionChatProps {
  questions: Question[];
  mode: AnswerReportMode;
  isGameOver: boolean;
  notices?: GameplayNotice[];
}

export default function QuestionChat({ questions, mode, isGameOver, notices = [] }: QuestionChatProps) {
  if (questions.length === 0 && notices.length === 0) {
    return (
      <div className="flex min-h-52 flex-col items-center justify-center px-5 py-8 text-center">
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
    <ol aria-label="Question conversation" className="space-y-6 py-1">
      {messages.map(message => {
        if (message.kind === 'notice') {
          const { notice } = message;
          return (
            <li key={notice.id} className="space-y-3">
              <div className="flex flex-col items-end pl-8">
                <span className="mb-1.5 px-1 text-[10px] font-medium text-zinc-500">You · {notice.action}</span>
                <p className="max-w-full rounded-2xl rounded-br-md border border-emerald-300/15 bg-emerald-400/[0.12] px-4 py-3 text-sm leading-relaxed text-sand-100 [overflow-wrap:anywhere]">{notice.input}</p>
              </div>
              <div role="alert" className="flex items-start gap-2.5 pr-5">
                <div className="mt-5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-emerald-300">
                  <Compass size={15} aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="mb-1.5 px-1 text-[10px] font-medium text-zinc-400">Countrydle</p>
                  <details open className="group rounded-2xl rounded-tl-md border border-amber-300/20 bg-amber-300/[0.06] text-sm leading-relaxed [overflow-wrap:anywhere]">
                    <summary className="flex cursor-pointer list-none items-center gap-2 rounded-2xl px-4 py-3 font-semibold text-amber-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-200 [&::-webkit-details-marker]:hidden">
                      <AlertTriangle size={16} className="shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1">{notice.title}</span>
                      <ChevronDown size={16} className="shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" />
                    </summary>
                    <div className="px-4 pb-3">
                      <p className="text-zinc-200">{notice.reason}</p>
                      <p className="mt-3 text-zinc-400"><span className="font-medium text-zinc-300">What to do: </span>{notice.nextStep}</p>
                    </div>
                  </details>
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
          <li key={`question-${question.id}`} className="space-y-3">
            <div className="flex flex-col items-end pl-8">
              <span className="mb-1.5 px-1 text-[10px] font-medium text-zinc-500">You · {index + 1}</span>
              <div className="max-w-full rounded-2xl rounded-br-md border border-emerald-300/15 bg-emerald-400/[0.12] px-4 py-3 text-sm leading-relaxed text-sand-100 [overflow-wrap:anywhere]">
                {question.original_question}
              </div>
            </div>
            <div className="flex items-start gap-2.5 pr-5">
              <div className="mt-5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-emerald-300">
                <Compass size={15} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="mb-1.5 px-1 text-[10px] font-medium text-zinc-400">Countrydle</p>
                <div className="w-fit max-w-full overflow-hidden rounded-2xl rounded-tl-md border border-white/10 bg-white/[0.045]">
                  <div className="px-4 py-3">
                    <span className={`inline-flex items-center gap-2 rounded-lg px-2.5 py-1 text-sm font-semibold ${tone}`}>
                      <Icon size={16} strokeWidth={2.5} aria-hidden="true" />
                      {answer}
                    </span>
                    {showExplanation && (
                      <div className="mt-3 text-sm leading-relaxed text-zinc-300 [overflow-wrap:anywhere]">
                        {!question.valid && <p className="mb-1 font-medium text-amber-200">Try rephrasing your question</p>}
                        <p>{question.explanation}</p>
                      </div>
                    )}
                  </div>
                  {isGameOver && question.id > 0 && <AnswerReportForm mode={mode} questionId={question.id} reportToken={question.report_token} />}
                </div>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
