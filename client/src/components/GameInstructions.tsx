import { useState } from 'react';
import { Info, HelpCircle, ChevronDown, ChevronUp, Languages } from 'lucide-react';

interface GameInstructionsProps {
  gameName: string;
  examples: string[];
  isPolish?: boolean;
}

const GameInstructions = ({ gameName, examples, isPolish }: GameInstructionsProps) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-6 overflow-hidden shadow-lg transition-all duration-300">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-4 flex items-center justify-between bg-zinc-800/30 hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-blue-400">
          <Info size={20} />
          <h3 className="font-bold text-lg">
            {isPolish ? 'Jak grać & Informacje' : 'How to Play & Info'}
          </h3>
        </div>
        {isOpen ? <ChevronUp size={20} className="text-zinc-500" /> : <ChevronDown size={20} className="text-zinc-500" />}
      </button>
      
      {isOpen && (
        <div className="p-6 border-t border-zinc-800 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="space-y-4">
            <p className="text-zinc-300 leading-relaxed text-sm md:text-base">
              {isPolish 
                ? `Witaj w ${gameName}! Gra jest obecnie w fazie rozwoju, więc przepraszamy za ewentualne błędy AI w odpowiedziach. Staramy się stale ulepszać jakość rozgrywki.`
                : `Welcome to ${gameName}! This game is currently in development, so we apologize for any potential AI mistakes in the answers. We are constantly working to improve the experience.`}
            </p>

            <div className="flex items-start gap-3 p-3 bg-blue-500/5 border border-blue-500/20 rounded-lg">
              <Languages size={18} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-zinc-400 text-sm italic">
                {isPolish
                  ? "Możesz zadawać pytania w dowolnym języku (np. polskim, angielskim, niemieckim) - AI zrozumie Twój zamiar!"
                  : "You can ask questions in any language (e.g., English, Polish, German) - the AI will understand your intent!"}
              </p>
            </div>

            <div className="space-y-3 pt-2">
              <div className="flex items-center gap-2 text-zinc-400 text-xs md:text-sm font-semibold uppercase tracking-wider">
                <HelpCircle size={16} />
                {isPolish ? 'Przykładowe pytania:' : 'Example questions:'}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {examples.map((example, index) => (
                  <div key={index} className="bg-zinc-800/50 border border-zinc-700/50 px-4 py-2 rounded-lg text-zinc-400 text-xs md:text-sm italic">
                    "{example}"
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GameInstructions;
