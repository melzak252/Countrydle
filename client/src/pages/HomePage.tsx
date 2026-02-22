import { useNavigate } from 'react-router-dom';
import { 
  Globe, 
  Trophy, 
  MessageSquare, 
  Search, 
  MapPin, 
  Map as MapIcon,
  Flag
} from 'lucide-react';
import { motion } from 'framer-motion';

const games = [
  {
    id: 'world',
    title: 'Countrydle',
    description: 'Guess the mystery country from across the globe.',
    path: '/game',
    icon: <Globe size={32} className="text-blue-500" />,
    color: 'from-blue-600 to-teal-600',
    hoverColor: 'group-hover:text-blue-400'
  },
  {
    id: 'us-states',
    title: 'US Statedle',
    description: 'Test your knowledge of the 50 United States.',
    path: '/us-states',
    icon: <MapIcon size={32} className="text-indigo-500" />,
    color: 'from-indigo-600 to-purple-600',
    hoverColor: 'group-hover:text-indigo-400'
  },
  {
    id: 'powiaty',
    title: 'Powiatdle',
    description: 'Polish counties (powiaty) challenge for experts.',
    path: '/powiaty',
    icon: <MapPin size={32} className="text-red-500" />,
    color: 'from-red-600 to-orange-600',
    hoverColor: 'group-hover:text-red-400'
  },
  {
    id: 'wojewodztwa',
    title: 'Województwdle',
    description: 'Can you identify the 16 Polish provinces?',
    path: '/wojewodztwa',
    icon: <Flag size={32} className="text-green-500" />,
    color: 'from-green-600 to-emerald-600',
    hoverColor: 'group-hover:text-green-400'
  }
];

export default function HomePage() {
  const navigate = useNavigate();

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-12 md:py-20">
      {/* Hero Section */}
      <section className="text-center mb-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-5xl md:text-7xl font-black mb-6 bg-gradient-to-r from-blue-500 via-teal-400 to-green-500 text-transparent bg-clip-text">
            Explore the World
          </h1>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto mb-10">
            The ultimate geography guessing game. Ask questions, analyze facts, and pinpoint the daily location.
          </p>
        </motion.div>
      </section>

      {/* How It Works Section */}
      <section className="mb-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">How to Play?</h2>
          <div className="w-20 h-1.5 bg-blue-500 mx-auto rounded-full"></div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-blue-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <MessageSquare className="text-blue-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">1. Ask YES/NO Questions</h3>
            <p className="text-zinc-400">Ask any Yes/No question to narrow down the possibilities. Is it landlocked? Is it in the Northern Hemisphere?</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-teal-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Search className="text-teal-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">2. Guess for Points</h3>
            <p className="text-zinc-400">Make your guess! The faster you find the daily mystery location, the more points you earn for your profile.</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-800 rounded-3xl text-center">
            <div className="w-16 h-16 bg-yellow-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Trophy className="text-yellow-500" size={32} />
            </div>
            <h3 className="text-xl font-bold mb-3">3. See Explanations</h3>
            <p className="text-zinc-400">Once the game is over, you'll see detailed explanations for why each question was answered the way it was.</p>
          </div>
        </div>
      </section>

      {/* Game Tiles Section */}
      <section>
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">Choose Your Map</h2>
          <p className="text-zinc-500">Pick a territory and start your challenge.</p>
        </div>

        <motion.div 
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          {games.map((game) => (
            <motion.div
              key={game.id}
              variants={itemVariants}
              whileHover={{ y: -10 }}
              onClick={() => navigate(game.path)}
              className="group cursor-pointer bg-zinc-900 border border-zinc-800 p-8 rounded-3xl hover:border-zinc-600 transition-all shadow-xl flex flex-col h-full"
            >
              <div className="mb-6 p-4 bg-zinc-800/50 rounded-2xl w-fit group-hover:scale-110 transition-transform">
                {game.icon}
              </div>
              <h3 className={`text-2xl font-bold mb-3 transition-colors ${game.hoverColor}`}>
                {game.title}
              </h3>
              <p className="text-zinc-400 mb-8 flex-grow">
                {game.description}
              </p>
              <div className={`mt-auto w-full py-3 rounded-xl bg-gradient-to-r ${game.color} text-center font-bold shadow-lg opacity-90 group-hover:opacity-100 transition-opacity`}>
                Play Now
              </div>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Footer-like Stats section */}
      <motion.div 
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-32 p-12 bg-zinc-900 border border-zinc-800 rounded-[3rem] text-center"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
          <div>
            <div className="text-4xl font-black mb-2">250+</div>
            <div className="text-zinc-500 uppercase tracking-widest text-xs font-bold">Countries & States</div>
          </div>
          <div>
            <div className="text-4xl font-black mb-2">Daily</div>
            <div className="text-zinc-500 uppercase tracking-widest text-xs font-bold">New Challenges</div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
