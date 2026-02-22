import { useState, useMemo } from 'react';
import type { CountryDisplay } from '../types';
import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface GuessInputProps {
  countries: CountryDisplay[];
  onGuess: (countryId: number, name: string) => Promise<void>;
  isLoading: boolean;
  remainingGuesses: number;
  placeholder?: string;
}

export default function GuessInput({ countries, onGuess, isLoading, remainingGuesses, placeholder }: GuessInputProps) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const { t } = useTranslation();

  const filteredCountries = useMemo(() => {
    if (!query || !countries) return [];
    return countries
      .filter(c => {
        const name = c.name || (c as any).nazwa;
        return name?.toLowerCase().includes(query.toLowerCase());
      })
      .slice(0, 5); // Limit to 5 suggestions
  }, [countries, query]);

  const handleSelect = (country: any) => {
    onGuess(country.id, country.name || country.nazwa);
    setQuery('');
    setShowSuggestions(false);
  };

  const defaultPlaceholder = t('inputs.guessPlaceholder', { count: remainingGuesses });

  return (
    <div className="w-full max-w-2xl mx-auto mb-12 relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowSuggestions(true);
          }}
          onFocus={() => setShowSuggestions(true)}
          placeholder={placeholder || defaultPlaceholder}
          className="w-full bg-zinc-800 border-2 border-zinc-700 rounded-xl px-6 py-4 pl-12 text-lg focus:outline-none focus:border-green-500 transition-colors disabled:opacity-50"
          disabled={isLoading || remainingGuesses <= 0}
        />
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500" size={20} />
      </div>

      {showSuggestions && filteredCountries.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-800 border border-zinc-700 rounded-xl shadow-xl overflow-hidden z-10">
          {filteredCountries.map((country) => (
            <button
              key={country.id}
              onClick={() => handleSelect(country)}
              className="w-full text-left px-6 py-3 hover:bg-zinc-700 transition-colors border-b border-zinc-700 last:border-0"
            >
              {country.name || (country as any).nazwa}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
