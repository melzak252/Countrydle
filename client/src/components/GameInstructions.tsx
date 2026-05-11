import { useState, useRef, useEffect } from 'react';
import { Info, HelpCircle, Languages, Trophy, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { createPortal } from 'react-dom';

interface GameInstructionsProps {
  gameName: string;
  examples: string[];
  scoring?: {
    maxPoints: number;
    details: string[];
  };
}

const GameInstructions = ({ gameName, examples, scoring }: GameInstructionsProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const modalContent = (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div 
        ref={modalRef}
        className="bg-zinc-900 border border-zinc-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900/50 sticky top-0">
           <div className="flex items-center gap-2 text-blue-400">
             <Info size={20} />
             <h3 className="font-bold text-lg">{t('instructions.title')}</h3>
           </div>
           <button 
             onClick={() => setIsOpen(false)}
             className="p-1 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
           >
             <X size={20} />
           </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto custom-scrollbar">
          <div className="space-y-6">
            <p className="text-zinc-300 leading-relaxed text-sm md:text-base">
              {t('instructions.welcome', { gameName })}
            </p>

            <div className="flex items-start gap-3 p-3 bg-blue-500/5 border border-blue-500/20 rounded-lg">
              <Info size={18} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-zinc-400 text-sm italic">
                {t('instructions.wikipedia')}
              </p>
            </div>

            <div className="flex items-start gap-3 p-3 bg-blue-500/5 border border-blue-500/20 rounded-lg">
              <Languages size={18} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-zinc-400 text-sm italic">
                {t('instructions.askAnyLanguage')}
              </p>
            </div>

            <div className="flex items-start gap-3 p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
              <HelpCircle size={18} className="text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-zinc-400 text-sm">
                {t('instructions.reliableInfo')}
              </p>
            </div>

            {scoring && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-yellow-500 text-xs md:text-sm font-semibold uppercase tracking-wider">
                  <Trophy size={16} />
                  {t('instructions.scoring')}
                </div>
                <div className="bg-zinc-800/30 border border-zinc-700/30 rounded-xl p-4">
                  <div className="text-2xl font-bold text-white mb-2">
                    {t('instructions.upToPoints', { maxPoints: scoring.maxPoints })}
                  </div>
                  <ul className="space-y-1">
                    {scoring.details.map((detail, index) => (
                      <li key={index} className="text-zinc-400 text-sm flex items-center gap-2">
                        <div className="w-1 h-1 rounded-full bg-zinc-600" />
                        {detail}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <div className="space-y-3 pt-2">
              <div className="flex items-center gap-2 text-zinc-400 text-xs md:text-sm font-semibold uppercase tracking-wider">
                <HelpCircle size={16} />
                {t('instructions.examples')}
              </div>
              <div className="grid grid-cols-1 gap-2">
                {examples.map((example, index) => (
                  <div key={index} className="bg-zinc-800/50 border border-zinc-700/50 px-4 py-2 rounded-lg text-zinc-400 text-xs md:text-sm italic">
                    "{example}"
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className="p-2 text-zinc-400 hover:text-blue-400 hover:bg-blue-400/10 rounded-lg transition-colors"
        title={t('instructions.title')}
      >
        <HelpCircle size={20} />
      </button>
      {isOpen && createPortal(modalContent, document.body)}
    </>
  );
};

export default GameInstructions;

