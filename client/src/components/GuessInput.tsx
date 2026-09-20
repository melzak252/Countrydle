import { useState, useMemo, useRef, useEffect } from 'react';
import type { CountryDisplay } from '../types';
import { Search, ArrowRight } from 'lucide-react';

interface GuessInputProps {
  countries: CountryDisplay[];
  onGuess: (countryId: number, name: string) => Promise<void>;
  isLoading: boolean;
  remainingGuesses: number;
  placeholder?: string;
  className?: string;
}

export default function GuessInput({
  countries,
  onGuess,
  isLoading,
  remainingGuesses,
  placeholder,
  className,
}: GuessInputProps) {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredCountries = useMemo(() => {
    if (!query.trim() || !countries) return [];
    const q = query.trim().toLowerCase();
    return countries
      .filter((c) => {
        const name = c.name || (c as any).nazwa || '';
        return name.toLowerCase().includes(q);
      })
      .slice(0, 6);
  }, [countries, query]);

  const handleSelect = (country: any) => {
    onGuess(country.id, country.name || country.nazwa);
    setQuery('');
    setShowSuggestions(false);
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || isLoading || remainingGuesses <= 0) return;

    // 1. Try exact match (case-insensitive)
    const q = query.trim().toLowerCase();
    const exactMatch = countries?.find((c) => {
      const name = (c.name || (c as any).nazwa || '').toLowerCase();
      return name === q;
    });

    if (exactMatch) {
      handleSelect(exactMatch);
      return;
    }

    // 2. If suggestions are visible, take the top suggestion
    if (filteredCountries.length > 0) {
      handleSelect(filteredCountries[0]);
      return;
    }

    // 3. Fallback: submit with id 0 and raw query
    onGuess(0, query.trim());
    setQuery('');
    setShowSuggestions(false);
  };

  const defaultPlaceholder = `Guess the location... (${remainingGuesses} left)`;

  return (
    <div
      ref={containerRef}
      className={`w-full max-w-2xl mx-auto relative ${className || 'mb-6 md:mb-12'}`}
    >
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowSuggestions(true);
          }}
          onFocus={() => setShowSuggestions(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder={placeholder || defaultPlaceholder}
          className="w-full bg-zinc-800 border-2 border-zinc-700 rounded-xl px-3 py-2 md:px-4 md:py-3 pl-9 md:pl-10 pr-24 text-sm md:text-base focus:outline-none focus:border-green-500 transition-colors disabled:opacity-50 text-white"
          disabled={isLoading || remainingGuesses <= 0}
        />
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 w-4 h-4 md:w-5 md:h-5 pointer-events-none" />

        <button
          type="submit"
          disabled={!query.trim() || isLoading || remainingGuesses <= 0}
          className="absolute right-1.5 md:right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 md:px-4 md:py-2 bg-green-600 hover:bg-green-500 disabled:opacity-30 disabled:hover:bg-green-600 text-white font-bold text-xs md:text-sm rounded-lg transition-all flex items-center gap-1 shadow-sm"
        >
          <span>Guess</span>
          <ArrowRight size={14} />
        </button>
      </form>

      {showSuggestions && filteredCountries.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-800 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden z-[100] max-h-56 overflow-y-auto">
          {filteredCountries.map((country) => (
            <button
              key={country.id}
              type="button"
              onClick={() => handleSelect(country)}
              className="w-full text-left px-4 py-2.5 hover:bg-zinc-700/80 transition-colors border-b border-zinc-700/60 last:border-0 text-sm text-white flex items-center justify-between group"
            >
              <span className="font-medium">{country.name || (country as any).nazwa}</span>
              <span className="text-xs text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity">
                Select ↵
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
