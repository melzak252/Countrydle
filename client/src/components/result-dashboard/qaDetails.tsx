import { BookOpen, MessageSquare } from 'lucide-react';
import LocationFieldNotes from '../LocationFieldNotes';
import ResultsQuestionHistory from '../ResultsQuestionHistory';
import type { AnswerReportMode, Question } from '../../types';
import type { GameplayNotice } from '../../lib/gameplayNotices';
import type { ResultDashboardDetailTab } from './types';

export function buildQADetailTabs({
  targetName,
  reportMode,
  questions,
  notices,
}: {
  targetName?: string;
  reportMode: AnswerReportMode;
  questions?: Question[];
  notices?: GameplayNotice[];
}): ResultDashboardDetailTab[] {
  const tabs: ResultDashboardDetailTab[] = [
    {
      id: 'notes',
      label: 'Location Field Notes',
      icon: <BookOpen size={15} className="shrink-0" aria-hidden="true" />,
      content: <LocationFieldNotes targetName={targetName} mode={reportMode} />,
    },
  ];

  if (questions && questions.length > 0) {
    tabs.push({
      id: 'questions',
      label: 'Question History',
      badge: questions.length,
      icon: <MessageSquare size={15} className="shrink-0" aria-hidden="true" />,
      content: (
        <div className="space-y-3">
          <p className="text-xs text-zinc-400">
            Select a question to review its explanation or report an issue.
          </p>
          <ResultsQuestionHistory
            questions={questions}
            notices={notices}
            mode={reportMode}
            isGameOver
          />
        </div>
      ),
    });
  }

  return tabs;
}
