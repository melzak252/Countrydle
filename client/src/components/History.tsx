import type { Question } from '../types';
import { Check, X, HelpCircle, Info, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';
import { useState, useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

// Reusable Portal Tooltip Component
interface PortalTooltipProps {
  children: ReactNode;
  content: ReactNode;
  position?: 'top' | 'bottom';
  className?: string;
}

const PortalTooltip = ({ children, content, position = 'top', className }: PortalTooltipProps) => {
  const [isVisible, setIsVisible] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  const updatePosition = () => {
    if (triggerRef.current && isVisible) {
      const rect = triggerRef.current.getBoundingClientRect();
      
      let top = 0;
      let left = rect.left + rect.width / 2;

      if (position === 'top') {
         top = rect.top;
      } else {
         top = rect.bottom;
      }
      
      setCoords({ top, left });
    }
  };

  useEffect(() => {
     if(isVisible) {
         updatePosition();
         // Use capture phase for scroll to catch it from any element
         window.addEventListener('scroll', updatePosition, true);
         window.addEventListener('resize', updatePosition);
     }
     return () => {
         window.removeEventListener('scroll', updatePosition, true);
         window.removeEventListener('resize', updatePosition);
     }
  }, [isVisible]);

  return (
    <div 
        ref={triggerRef}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className={cn("relative w-full block", className)}
    >
      {children}
      {isVisible && createPortal(
        <div 
            className={cn("fixed z-[9999] pointer-events-none", className)}
            style={{ 
                top: coords.top, 
                left: coords.left,
                transform: `translate(-50%, ${position === 'top' ? 'calc(-100% - 10px)' : '10px'})` 
            }}
        >
            {content}
        </div>,
        document.body
      )}
    </div>
  );
}

      
      left = left + window.scrollX;
      
      setCoords({ top, left });
    }
  };

  useEffect(() => {
     if(isVisible) {
         updatePosition();
         window.addEventListener('scroll', updatePosition, true);
         window.addEventListener('resize', updatePosition);
     }
     return () => {
         window.removeEventListener('scroll', updatePosition, true);
         window.removeEventListener('resize', updatePosition);
     }
  }, [isVisible]);

  return (
    <div 
        ref={triggerRef}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className={cn("relative inline-block", className)}
    >

      {children}
      {isVisible && createPortal(
        <div 
            className={cn("fixed z-[9999] pointer-events-none transform -translate-x-1/2", className)}
            style={{ 
                top: coords.top, 
                left: coords.left,
                transform: `translate(-50%, ${position === 'top' ? '-100%' : '0'})` 
            }}
        >
            {content}
        </div>,
        document.body
      )}
    </div>
  );
}

interface HistoryProps {
  questions: Question[];
  isGameOver?: boolean;
}

export default function History({ questions, isGameOver = false }: HistoryProps) {
  // Sort questions by ID descending (newest first)
  const sortedQuestions = [...questions].sort((a, b) => b.id - a.id);

  return (
    <div className="w-full space-y-4 mb-8">
      {sortedQuestions.length === 0 ? (
        <div className="text-center text-zinc-500 py-8">
          No questions asked yet. Start by asking something!
        </div>
      ) : (
        sortedQuestions.map((q, index) => {
          const cardContent = (
            <motion.div
              key={q.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className={cn(
                "p-3 md:p-4 rounded-xl border flex items-center gap-3 md:gap-4 shadow-sm relative transition-all w-full",
                q.valid ? "bg-zinc-900 border-zinc-800" : "bg-red-900/20 border-red-900/50"
              )}
            >
                <div className="flex-shrink-0 relative">
                  {!q.valid ? (
                         <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-500">
                           <HelpCircle size={18} />
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
              
              <div className="flex-1 min-w-0 group/text">
                <p className="font-medium text-base md:text-lg break-words leading-tight">{q.original_question}</p>
              </div>
              
              {q.explanation && isGameOver && (
                  <div className="text-zinc-500 transition-colors">
                      <Info size={18} />
                  </div>
              )}
              
              <div className="text-xs text-zinc-500 font-mono ml-2">
                #{questions.length - index}
              </div>
            </motion.div>
          );

          if (!q.valid) {
            return (
              <PortalTooltip 
                key={q.id}
                position="top"
                className="w-full block"
                content={
                  <div className="bg-zinc-900 border-2 border-amber-500/50 rounded-xl text-sm text-white shadow-2xl p-4 w-[280px] md:w-72 text-center animate-in fade-in zoom-in-95 duration-200 flex flex-col items-center">
                      <div className="flex items-center justify-center gap-2 mb-2 text-amber-500 font-bold text-base">
                          <AlertTriangle size={18} />
                          <span>Invalid Question</span>
                      </div>
                      <p className="text-zinc-200 leading-relaxed mb-2">We couldn't answer this question because:</p>
                      <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-200 italic mb-2">
                          "{q.explanation}"
                      </div>
                      {/* Arrow */}
                      <div className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 bg-zinc-900 border-r-2 border-b-2 border-amber-500/50 transform rotate-45 -mt-[7px]"></div>
                  </div>
                }
              >
                {cardContent}
              </PortalTooltip>
            );
          }

          if (q.explanation && isGameOver) {
            return (
              <PortalTooltip
                key={q.id}
                position="bottom"
                className="w-full block"
                content={
                  <div className="mt-2 p-3 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 shadow-xl max-w-sm md:max-w-md animate-in fade-in zoom-in-95 duration-200 relative">
                      <div className="absolute -top-2 left-1/2 w-4 h-4 bg-zinc-800 border-t border-l border-zinc-700 transform rotate-45 -translate-x-1/2"></div>
                      {q.explanation}
                  </div>
                }
              >
                {cardContent}
              </PortalTooltip>
            );
          }

          return cardContent;
        })

      )}
    </div>
  );
}
