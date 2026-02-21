import { useEffect, useState } from 'react';
import { usePowiatyGameStore } from '../stores/gameStore';
import { useAuthStore } from '../stores/authStore';
import { useNavigate } from 'react-router-dom';
import QuestionInput from '../components/QuestionInput';
import History from '../components/History';
import GuessInput from '../components/GuessInput';
import PowiatyMap from '../components/PowiatyMap';
import GameInstructions from '../components/GameInstructions';
import { Loader2, ChevronDown, ChevronUp, Map as MapIcon } from 'lucide-react';

export default function PowiatyGamePage() {
  const { 
    gameState, 
    questions, 
    guesses, 
    entities: powiaty, 
    correctEntity: correctPowiat,
    isLoading, 
    fetchGameState, 
    fetchEntities: fetchPowiaty, 
    askQuestion, 
    makeGuess
  } = usePowiatyGameStore();

  const { isAuthenticated, isLoading: isAuthLoading } = useAuthStore();
  const navigate = useNavigate();
  const [isMapOpen, setIsMapOpen] = useState(true);

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, isAuthLoading, navigate]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchGameState();
      fetchPowiaty();
    }
  }, [isAuthenticated, fetchGameState, fetchPowiaty]);

  if (isAuthLoading || (!gameState && isLoading)) {
    return (
      <div className="flex justify-center items-center h-[60vh]">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (!gameState) return null;

  return (
    <div className="max-w-6xl mx-auto pb-20 px-4">
      <div className="text-center mb-6">
        <h2 className="text-4xl font-bold mb-2 bg-gradient-to-r from-red-500 to-white text-transparent bg-clip-text">
          Zgadnij Powiat
        </h2>
        <p className="text-zinc-400">Data: {usePowiatyGameStore.getState().dailyDate}</p>
      </div>

      <GameInstructions 
        gameName="Zgadnij Powiat"
        isPolish={true}
        examples={[
          "Czy leży w województwie mazowieckim?",
          "Czy graniczy z innym państwem?",
          "Czy jest to miasto na prawach powiatu?",
          "Czy liczba ludności przekracza 100 tysięcy?"
        ]}
      />

      {/* Collapsible Map Section */}
      <div className="mb-8 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg">

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Main Column: Inputs & History (8 cols) */}
        <div className="lg:col-span-8 space-y-8">
            {gameState.is_game_over && (
              <div className={`text-center p-8 rounded-xl ${gameState.won ? 'bg-green-900/20 border border-green-500/50' : 'bg-red-900/20 border border-red-500/50'}`}>
                <h2 className="text-4xl font-bold mb-4">
                  {gameState.won ? 'Wygrałeś! 🎉' : 'Koniec Gry 😔'}
                </h2>
                <p className="text-xl mb-4">
                  {gameState.won 
                    ? `Odgadłeś powiat poprawnie!` 
                    : `Skończyły Ci się próby.`}
                </p>
                 {(correctPowiat || guesses.find(g => g.answer)?.guess) && (
                    <p className="text-lg">Powiat to: <span className="font-bold">{correctPowiat?.nazwa || guesses.find(g => g.answer)?.guess}</span></p>
                 )}
              </div>
            )}

            {!gameState.is_game_over && (
              <div className="space-y-6">
                <QuestionInput 
                  onAsk={askQuestion} 
                  isLoading={isLoading} 
                  remainingQuestions={gameState.remaining_questions} 
                  placeholder={`Zadaj pytanie o powiat... (zostało ${gameState.remaining_questions})`}
                />
                
                <GuessInput 
                  countries={powiaty} 
                  onGuess={async (id, name) => makeGuess(name, id)} 
                  isLoading={isLoading} 
                  remainingGuesses={gameState.remaining_guesses} 
                  placeholder={`Zgadnij powiat... (zostało ${gameState.remaining_guesses})`}
                />
              </div>
            )}

            <div>
               <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-bold">Historia Pytań</h3>
                  <span className="text-sm text-zinc-500">{questions.length} zadanych pytań</span>
               </div>
               <History questions={questions} isGameOver={gameState.is_game_over} />
            </div>
        </div>

        {/* Side Column: Stats & Guesses (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
               <h3 className="font-bold text-zinc-400 uppercase tracking-wider mb-4 text-sm">Status Gry</h3>
               <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className="text-2xl font-bold text-blue-500 mb-1">
                      {gameState.remaining_questions}
                    </div>
                    <div className="text-xs text-zinc-500 uppercase">Pytania</div>
                  </div>
                  <div className="text-center p-3 bg-zinc-800/50 rounded-lg">
                    <div className="text-2xl font-bold text-teal-500 mb-1">
                      {gameState.remaining_guesses}
                    </div>
                    <div className="text-xs text-zinc-500 uppercase">Próby</div>
                  </div>
               </div>
            </div>

            {guesses.length > 0 && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                    <h3 className="font-bold text-zinc-400 uppercase tracking-wider mb-4 text-sm">Twoje Strzały</h3>
                    <div className="space-y-2">
                        {guesses.map((g) => (
                            <div key={g.id} className={`flex items-center justify-between p-3 rounded-lg border ${g.answer ? 'bg-green-900/20 border-green-500/50 text-green-400' : 'bg-red-900/20 border-red-500/50 text-red-400'}`}>
                                <span className="font-medium">{g.guess}</span>
                                {g.answer ? <span className="text-green-500">Poprawnie</span> : <span className="text-red-500">Błędnie</span>}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
      </div>
    </div>
  );
}
