import type { Question } from '../types';
import { Check, X, HelpCircle, Info, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { cn } from '../lib/utils';

interface HistoryProps {
  questions: Question[];
  isGameOver?: boolean;
}

export default function History({ questions, isGameOver = false }: HistoryProps) {
  const { t } = useTranslation();
  // Sort questions by ID descending (newest first)
  const sortedQuestions = [...questions].sort((a, b) => b.id - a.id);

  return (
    <div className="w-full space-y-4 mb-8">
      {sortedQuestions.length === 0 ? (
        <div className="text-center text-zinc-500 py-8">
          {t('history.empty')}
        </div>
      ) : (
        sortedQuestions.map((q, index) => (
          <motion.div
            key={q.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            className={cn(
              "p-4 rounded-xl border flex items-center gap-4 shadow-sm relative group transition-all",
              q.valid ? "bg-zinc-900 border-zinc-800" : "bg-red-900/20 border-red-900/50"
            )}
          >
              <div className="flex-shrink-0 relative group/icon">
                {!q.valid ? (
                   <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-500 cursor-help">
                     <HelpCircle size={18} />
                     <div className="hidden group-hover/icon:block absolute bottom-full left-1/2 -translate-x-1/2 mb-3 p-4 bg-zinc-900 border-2 border-amber-500/50 rounded-xl text-sm text-white shadow-[0_10px_40px_-15px_rgba(0,0,0,0.5),0_0_20px_rgba(245,158,11,0.2)] z-50 w-72 text-center animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center justify-center gap-2 mb-2 text-amber-500 font-bold text-base">
                           <AlertTriangle size={18} />
                           <span>{t('history.invalidTitle')}</span>
                         </div>
                         <p className="text-zinc-200 leading-relaxed mb-2">{t('history.invalidReason')}</p>
                        <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-200 italic">
                          "{q.explanation}"
                        </div>
                        <div className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 bg-zinc-900 border-r-2 border-b-2 border-amber-500/50 transform rotate-45 -mt-[7px]"></div>
                     </div>
                   </div>
                ) : q.answer === true ? (
                  <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center text-green-500">
                    <Check size={18} />
                  </div>
                ) : q.answer === false ? (
                  <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center text-red-500">
                    <X size={18} />
                  </div>
                ) : (
                  <div className="w-8 h-8 rounded-full bg-yellow-500/20 flex items-center justify-center text-yellow-500">
                    <HelpCircle size={18} />
                  </div>
                )}
            </div>
            
            <div className="flex-1">
              <p className="font-medium text-lg">{q.original_question}</p>
              {q.explanation && isGameOver && (
                 <div className="hidden group-hover:block absolute top-full left-0 mt-2 p-3 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 shadow-xl z-20 w-full max-w-md">
                    <div className="absolute -top-2 left-8 w-4 h-4 bg-zinc-800 border-t border-l border-zinc-700 transform rotate-45"></div>
                    {q.explanation}
                 </div>
              )}
            </div>
            
            {q.explanation && isGameOver && (
                <div className="text-zinc-500 hover:text-blue-400 cursor-help transition-colors" title={t('history.hoverExplanation')}>
                    <Info size={18} />
                </div>
            )}
            
            <div className="text-xs text-zinc-500 font-mono ml-2">
              #{questions.length - index}
            </div>
          </motion.div>
        ))
      )}
    </div>
  );
}
