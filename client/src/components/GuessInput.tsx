import { useState, useId } from 'react';
import type { CountryDisplay } from '../types';
import { Search, ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface GuessInputProps {
  countries: CountryDisplay[];
  onGuess: (countryId: number, name: string) => Promise<void>;
  isLoading: boolean;
  remainingGuesses: number;
  placeholder?: string;
  className?: string;
}

function normalizeName(value: string) {
  return value.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
}

function displayName(country: CountryDisplay & { nazwa?: string }) {
  return country.name || country.nazwa || '';
}

export default function GuessInput({
  countries,
  onGuess,
  isLoading,
  remainingGuesses,
  placeholder,
  className,
}: GuessInputProps) {
  const { t } = useTranslation();
  
  const inputId = useId();
  const [query, setQuery] = useState('');
  const disabled = isLoading || remainingGuesses <= 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || disabled) return;

    const normalizedQuery = normalizeName(query);
    const match = countries.find(country => normalizeName(displayName(country)) === normalizedQuery);
    onGuess(match?.id || 0, match ? displayName(match) : query.trim());
    setQuery('');
  };

  return (
    <div className={`relative w-full ${className || ''}`}>
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <label htmlFor={inputId} className="sr-only">Location name</label>
        <input
          id={inputId}
          type="text"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={placeholder || t('inputs.guessPlaceholder', { count: remainingGuesses })}
          className="w-full rounded-sm border border-white/15 bg-obsidian-950 py-3 pl-10 pr-28 text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-40"
          disabled={disabled}
        />
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
        <button
          type="submit"
          disabled={!query.trim() || disabled}
          className="absolute right-1 top-1/2 flex min-h-10 -translate-y-1/2 items-center gap-2 rounded-sm bg-emerald-400 px-3 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:opacity-40"
        >
          <span>{'Guess'}</span>
          <ArrowRight size={14} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
