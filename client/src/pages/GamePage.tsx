import { useEffect } from 'react';
import { useGameStore } from '../stores/gameStore';
import QuestionInput from '../components/QuestionInput';
import History from '../components/History';
import GuessInput from '../components/GuessInput';
import MapBox from '../components/MapBox';
import GameInstructions from '../components/GameInstructions';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function GamePage() {
  const { 
    gameState, 
    questions, 
    guesses, 
    entities: countries, 
    correctEntity: correctCountry,
    isLoading, 
    fetchGameState, 
    fetchEntities: fetchCountries, 
    askQuestion, 
    makeGuess 
  } = useGameStore();
  const { t } = useTranslation();

  useEffect(() => {
    fetchGameState();
    fetchCountries();
  }, [fetchGameState, fetchCountries]);

  if (!gameState && isLoading) {
    return (
      <div className="flex justify-center items-center h-[60vh]">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (!gameState) return null;

  return (
    <div className="flex flex-col max-w-[1920px] mx-auto lg:h-[calc(100vh-65px)] lg:overflow-hidden">
      {/* Top Bar */}
      <div className="sticky top-0 z-30 lg:static flex items-center justify-between px-3 md:px-4 py-2 border-b border-zinc-800 bg-zinc-900/95 backdrop-blur-sm shrink-0">
         <div className="flex items-center gap-2 md:gap-4">
            <h2 className="text-lg md:text-xl font-bold truncate">{t('gamePage.title')}</h2>
            <div className="hidden md:block h-4 w-px bg-zinc-700"></div>
            <p className="hidden md:block text-xs text-zinc-400">{useGameStore.getState().dailyDate}</p>
         </div>
         
         <div className="flex items-center gap-2 md:gap-4">
            <div className="flex gap-2">
                <div className="flex flex-col md:flex-row items-center md:gap-2 px-2 md:px-3 py-1 bg-zinc-800 rounded-lg border border-zinc-700">
                    <span className="text-blue-500 font-bold text-sm md:text-base">{gameState.remaining_questions}</span>
                    <span className="text-[8px] md:text-[10px] text-zinc-400 uppercase tracking-wider hidden md:inline">{t('gamePage.questionsLeft')}</span>
                </div>
                <div className="flex flex-col md:flex-row items-center md:gap-2 px-2 md:px-3 py-1 bg-zinc-800 rounded-lg border border-zinc-700">
                    <span className="text-teal-500 font-bold text-sm md:text-base">{gameState.remaining_guesses}</span>
                    <span className="text-[8px] md:text-[10px] text-zinc-400 uppercase tracking-wider hidden md:inline">{t('gamePage.guessesLeft')}</span>
                </div>
            </div>

            <GameInstructions 
                gameName="Countrydle"
                examples={t('gamePage.examples', { returnObjects: true }) as string[]}
                scoring={{
                maxPoints: 2000,
                details: t('gamePage.scoringDetails', { returnObjects: true }) as string[]
                }}
            />
         </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-col lg:flex-row flex-1 lg:min-h-0">
        
        {/* Left Column: Map & Inputs */}
        <div className="w-full lg:w-3/4 flex flex-col p-3 md:p-4 gap-4 lg:overflow-y-auto custom-scrollbar">
            {/* Map */}
            <div className="h-[300px] md:h-[400px] lg:flex-1 lg:mb-16 min-h-[300px] shrink-0 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden relative shadow-lg">
                <MapBox correctCountryName={gameState.won ? correctCountry?.name : undefined} className="h-full" />
            </div>

            {/* Game Over Message */}
            {gameState.is_game_over && (
              <div className={`text-center p-4 rounded-xl ${gameState.won ? 'bg-green-900/20 border border-green-500/50' : 'bg-red-900/20 border border-red-500/50'} animate-in fade-in zoom-in-95 duration-300`}>
                <h2 className="text-xl md:text-2xl font-bold mb-2">
                  {gameState.won ? t('gamePage.won') : t('gamePage.gameOver')}
                </h2>
                <p className="text-sm md:text-base mb-2 opacity-90">
                  {gameState.won 
                    ? t('gamePage.wonMessage')
                    : t('gamePage.lostMessage')}
                </p>
                 {gameState.won && (correctCountry || guesses.find(g => g.answer)?.guess) && (
                    <p className="text-sm md:text-base">{t('gamePage.answer')} <span className="font-bold">{correctCountry?.name || guesses.find(g => g.answer)?.guess}</span></p>
                 )}
              </div>
            )}

            {/* Input Section - Only for Mobile now */}
            {!gameState.is_game_over && (
                <div className="lg:hidden space-y-3 md:space-y-4 max-w-3xl mx-auto w-full">
                    <QuestionInput 
                        onAsk={askQuestion} 
                        isLoading={isLoading} 
                        remainingQuestions={gameState.remaining_questions} 
                        placeholder={t('gamePage.askPlaceholder', { count: gameState.remaining_questions })}
                    />
                    
                    <GuessInput 
                        countries={countries} 
                        onGuess={async (id, name) => makeGuess(name, id)} 
                        isLoading={isLoading} 
                        remainingGuesses={gameState.remaining_guesses} 
                        placeholder={t('gamePage.guessPlaceholder', { count: gameState.remaining_guesses })}
                    />
                </div>
            )}

            {/* Recent Guesses (Mobile Only or Compact) */}
            {guesses.length > 0 && (
                <div className="lg:hidden bg-zinc-900/50 border border-zinc-800 rounded-xl p-3">
                    <h3 className="font-bold text-zinc-400 uppercase tracking-wider mb-2 text-xs">{t('gamePage.yourGuesses')}</h3>
                    <div className="flex flex-wrap gap-2">
                        {guesses.map((g) => (
                            <div key={g.id} className={`flex items-center gap-2 px-2 py-1 rounded-md border ${g.answer ? 'bg-green-900/10 border-green-500/30 text-green-400' : 'bg-red-900/10 border-red-500/30 text-red-400'} text-xs`}>
                                <span className="font-medium">{g.guess}</span>
                                {g.answer ? <span className="font-bold">✓</span> : <span className="font-bold">✗</span>}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>

        {/* Right Column: History & Desktop Guesses */}
        <div className="w-full lg:w-1/4 flex flex-col bg-zinc-950/30 lg:border-l border-zinc-800 min-h-[400px]">
            
            {/* Guesses Section */}
            <div className="hidden lg:flex flex-col border-b border-zinc-800 bg-zinc-900/20 max-h-[40%] min-h-[150px]">
                <div className="p-3 md:p-4 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/30 sticky top-0 z-10">
                    <h3 className="font-bold text-zinc-200 text-sm md:text-base">{t('gamePage.yourGuesses')}</h3>
                    <span className="text-xs text-zinc-500 bg-zinc-900 px-2 py-1 rounded-md border border-zinc-800">{guesses.length}</span>
                </div>
                
                <div className="flex flex-col flex-1 overflow-hidden">
                    {!gameState.is_game_over && (
                        <div className="p-4 pb-2 border-b border-zinc-800/50">
                            <GuessInput 
                                countries={countries} 
                                onGuess={async (id, name) => makeGuess(name, id)} 
                                isLoading={isLoading} 
                                remainingGuesses={gameState.remaining_guesses} 
                                placeholder={t('gamePage.guessPlaceholder', { count: gameState.remaining_guesses })}
                                className="mb-0"
                            />
                        </div>
                    )}
                    
                    <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
                        {guesses.length > 0 ? (
                            <div className="space-y-2">
                                {guesses.map((g) => (
                                    <div key={g.id} className={`p-3 rounded-xl border flex items-center gap-3 shadow-sm transition-all ${g.answer ? 'bg-zinc-900 border-green-500/30' : 'bg-zinc-900 border-red-500/30'}`}>
                                        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${g.answer ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                                            {g.answer ? <span className="font-bold">✓</span> : <span className="font-bold">✗</span>}
                                        </div>
                                        <span className="font-medium text-sm md:text-base flex-1 truncate">{g.guess}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center text-zinc-500 text-sm py-4">
                                {t('gamePage.makeAGuess')}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* History Section */}
            <div className="flex flex-col flex-1 min-h-0">
                <div className="p-3 md:p-4 border-b border-zinc-800 flex flex-col gap-3 bg-zinc-900/30 sticky top-0 z-10">
                    <div className="flex justify-between items-center">
                        <h3 className="font-bold text-zinc-200 text-sm md:text-base">{t('gamePage.history')}</h3>
                        <span className="text-xs text-zinc-500 bg-zinc-900 px-2 py-1 rounded-md border border-zinc-800">{t('gamePage.questionsAsked', { count: questions.length })}</span>
                    </div>
                    
                    {!gameState.is_game_over && (
                        <div className="hidden lg:block w-full">
                             <QuestionInput 
                                onAsk={askQuestion} 
                                isLoading={isLoading} 
                                remainingQuestions={gameState.remaining_questions} 
                                placeholder={t('gamePage.askPlaceholder', { count: gameState.remaining_questions })}
                            />
                        </div>
                    )}
                </div>
                
                <div className="flex-1 overflow-y-auto p-3 md:p-4 custom-scrollbar">
                    <History questions={questions} isGameOver={gameState.is_game_over} />
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
