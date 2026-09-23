import { useState, useMemo, useRef, useEffect, useId } from 'react';
import { Search, ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface LocationOption<Id extends string | number> {
  id: Id;
  name: string;
  nazwa?: string;
}

interface GuessInputProps<Id extends string | number> {
  countries: LocationOption<Id>[];
  onGuess: (countryId: Id, name: string) => Promise<void | boolean>;
  onUnknownGuess?: (name: string) => Promise<void | boolean>;
  isLoading: boolean;
  remainingGuesses?: number;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  submitLabel?: string;
  noMatchesLabel?: string;
  dropup?: boolean;
}

function normalizeName(value: string) {
  return value.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');
}

function displayName(country: { name: string; nazwa?: string }) {
  return country.name || country.nazwa || '';
}

export default function GuessInput<Id extends string | number = number>({
  countries,
  onGuess,
  isLoading,
  onUnknownGuess,
  remainingGuesses,
  placeholder,
  className,
  disabled: externallyDisabled = false,
  submitLabel = 'Guess',
  noMatchesLabel = 'No matching locations.',
  dropup = false,
}: GuessInputProps<Id>) {
  const { t } = useTranslation();
  
  const inputId = useId();
  const listId = `${inputId}-suggestions`;
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const disabled = externallyDisabled || isLoading || (remainingGuesses !== undefined && remainingGuesses <= 0);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const searchableCountries = useMemo(() => countries.map(country => ({
    country,
    name: normalizeName(displayName(country)),
  })), [countries]);
  const normalizedQuery = normalizeName(query);
  const filteredCountries = useMemo(() => normalizedQuery
    ? searchableCountries.filter(item => item.name.includes(normalizedQuery)).slice(0, 6)
    : [], [searchableCountries, normalizedQuery]);
  const suggestionsVisible = showSuggestions && !disabled && filteredCountries.length > 0;

  const handleSelect = async (country: LocationOption<Id>) => {
    if (disabled) return;
    if (await onGuess(country.id, displayName(country)) === false) return;
    setQuery('');
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || disabled) return;

    const selected = suggestionsVisible && activeIndex >= 0 ? filteredCountries[activeIndex] : undefined;
    const match = selected || searchableCountries.find(item => item.name === normalizedQuery) || filteredCountries[0];
    if (match) {
      await handleSelect(match.country);
      return;
    }

    if (!onUnknownGuess || await onUnknownGuess(query.trim()) === false) return;
    setQuery('');
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-full ${className || ''}`}
      onBlur={e => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setShowSuggestions(false);
      }}
    >
      <form onSubmit={handleSubmit} autoComplete="off" className="relative flex items-center">
        <label htmlFor={inputId} className="sr-only">{'Search for a location'}</label>
        <input
          id={inputId}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={suggestionsVisible}
          aria-controls={suggestionsVisible ? listId : undefined}
          aria-activedescendant={suggestionsVisible && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          value={query}
          onChange={e => {
            setQuery(e.target.value);
            setShowSuggestions(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setShowSuggestions(true)}
          onKeyDown={e => {
            if (e.key === 'Escape') {
              setShowSuggestions(false);
              setActiveIndex(-1);
            } else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && filteredCountries.length > 0) {
              e.preventDefault();
              setShowSuggestions(true);
              setActiveIndex(index => e.key === 'ArrowDown'
                ? (index + 1) % filteredCountries.length
                : (index <= 0 ? filteredCountries.length - 1 : index - 1));
            }
          }}
          placeholder={placeholder || t('inputs.guessPlaceholder', { count: remainingGuesses })}
          className="w-full rounded-sm border border-white/15 bg-obsidian-950 py-3 pl-10 pr-28 text-base sm:text-sm text-sand-100 placeholder:text-zinc-500 focus:border-emerald-500/70 focus:outline-none focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-40"
          disabled={disabled}
        />
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
        <button
          type="submit"
          disabled={!query.trim() || disabled || (!filteredCountries.length && !onUnknownGuess)}
          className="absolute right-1 top-1/2 flex min-h-10 -translate-y-1/2 items-center gap-2 rounded-sm bg-emerald-400 px-3 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:opacity-40"
        >
          <span>{submitLabel}</span>
          <ArrowRight size={14} aria-hidden="true" />
        </button>
      </form>

      {suggestionsVisible && (
        <div id={listId} role="listbox" aria-label={'Matching locations'} className={`absolute left-0 right-0 ${dropup ? 'bottom-full mb-1.5' : 'top-full mt-1'} z-50 max-h-72 overflow-y-auto rounded-sm border border-white/15 bg-obsidian-900/95 shadow-xl backdrop-blur-md divide-y divide-white/5`}>
          {filteredCountries.map(({ country }, index) => (
            <button
              id={`${listId}-${index}`}
              key={country.id}
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              tabIndex={-1}
              onMouseDown={e => e.preventDefault()}
              onClick={() => handleSelect(country)}
              onMouseEnter={() => setActiveIndex(index)}
              className={`flex min-h-11 w-full items-center justify-between gap-3 border-b border-white/10 px-4 py-3 text-left text-sm text-sand-100 last:border-0 hover:bg-white/5 ${index === activeIndex ? 'bg-white/5' : ''}`}
            >
              <span>{displayName(country)}</span>
              <ArrowRight size={13} className="shrink-0 text-emerald-400" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
      {query.trim() && !filteredCountries.length && !onUnknownGuess && !disabled && <p role="status" className="mt-2 text-xs text-zinc-400">{noMatchesLabel}</p>}
    </div>
  );
}
