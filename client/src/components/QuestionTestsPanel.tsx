import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { isAxiosError } from 'axios';
import { Loader2, Play, RefreshCw } from 'lucide-react';
import { adminService } from '../services/api';
import type { AnswerReport, QuestionTestEntity, QuestionTestMode, QuestionTestRequest, QuestionTestResult } from '../types';

const MODE_LABELS: Record<QuestionTestMode, string> = {
  countrydle: 'Countrydle',
  us_statedle: 'US Statedle',
  powiatdle: 'Powiatdle',
  wojewodztwodle: 'Województwodle',
  europe: 'Europa',
  asia: 'Azja',
  africa: 'Afryka',
  americas: 'Ameryki',
  flagdle: 'Flagdle',
};
const SOURCE_LABELS: Record<QuestionTestResult['source'], string> = {
  local_kb: 'Lokalna baza wiedzy',
  local_planner: 'Lokalny planer',
  fallback: 'Ścieżka zapasowa modelu',
  flag_kb: 'Lokalna baza flag',
};
const controlClass = 'w-full min-w-0 rounded-sm border border-white/10 bg-obsidian-950 px-3 py-2 text-sm text-sand-100 disabled:cursor-not-allowed disabled:opacity-40';
const cardClass = 'min-w-0 space-y-4 rounded-sm border border-white/10 bg-obsidian-900 p-4 sm:p-6';

function errorMessage(cause: unknown, fallback: string): string {
  if (isAxiosError(cause) && typeof cause.response?.data?.detail === 'string') {
    return `${fallback} ${cause.response.data.detail}`;
  }
  return fallback;
}

function Answer({ valid, answer }: { valid: boolean; answer: boolean | null }) {
  return (
    <div className="space-y-1">
      <p className={`font-semibold ${valid ? 'text-emerald-300' : 'text-amber-300'}`}>
        {valid ? 'Pytanie poprawne' : 'Pytanie niepoprawne'}
      </p>
      <p className="text-xl font-semibold text-sand-100">
        {!valid || answer === null ? 'Brak odpowiedzi TAK/NIE' : answer ? 'TAK' : 'NIE'}
      </p>
    </div>
  );
}

type CompletedTest = {
  request: QuestionTestRequest;
  entity: QuestionTestEntity;
  result: QuestionTestResult;
  comparableReportId: number | null;
};

export default function QuestionTestsPanel({ report, onClearReport }: { report: AnswerReport | null; onClearReport: () => void }) {
  const [mode, setMode] = useState<QuestionTestMode>(report?.mode ?? 'countrydle');
  const [question, setQuestion] = useState(report?.details.original_question ?? '');
  const [entityId, setEntityId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [revision, setRevision] = useState(0);
  const [entities, setEntities] = useState<{ mode: QuestionTestMode; items: QuestionTestEntity[]; error: string | null } | null>(null);
  const [completed, setCompleted] = useState<CompletedTest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(false);
  const pending = useRef(false);
  const loadingEntities = entities === null || entities.mode !== mode;
  const availableEntities = loadingEntities ? [] : entities.items;
  const selectedEntity = availableEntities.find((entity) => entity.id === entityId);
  const matchingTargets = report && mode === report.mode
    ? availableEntities.filter((entity) => entity.name === report.details.target_name)
    : [];
  const normalizedSearch = search.trim().toLocaleLowerCase('pl');
  const filteredEntities = availableEntities.filter((entity) => entity.name.toLocaleLowerCase('pl').includes(normalizedSearch));
  const visibleEntities = selectedEntity && !filteredEntities.some((entity) => entity.id === selectedEntity.id)
    ? [selectedEntity, ...filteredEntities]
    : filteredEntities;
  const trimmedQuestion = question.trim();
  const canSubmit = !busy && !loadingEntities && !!selectedEntity && trimmedQuestion.length > 0 && question.length <= 100;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setEntities(null);
    setEntityId(null);
    setCompleted(null);
    setError(null);
    adminService.getQuestionTestEntities(mode, controller.signal)
      .then((items) => {
        if (cancelled) return;
        setEntities({ mode, items, error: null });
        const matches = report?.mode === mode ? items.filter((entity) => entity.name === report.details.target_name) : [];
        if (matches.length === 1) setEntityId(matches[0].id);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setEntities({ mode, items: [], error: errorMessage(cause, 'Nie udało się pobrać obiektów. Spróbuj ponownie.') });
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [mode, report, revision]);

  const clearResult = () => {
    setCompleted(null);
    setError(null);
  };

  const runTest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending.current || !canSubmit || !selectedEntity) return;
    pending.current = true;
    setBusy(true);
    clearResult();
    const request: QuestionTestRequest = { mode, entity_id: selectedEntity.id, question: trimmedQuestion };
    const comparableReportId = report && report.mode === mode
      && matchingTargets.length === 1 && matchingTargets[0].id === selectedEntity.id
      && report.details.original_question.trim() === request.question ? report.id : null;
    try {
      const result = await adminService.testQuestion(request);
      if (mounted.current) setCompleted({ request, entity: selectedEntity, result, comparableReportId });
    } catch (cause: unknown) {
      if (mounted.current) setError(errorMessage(cause, 'Test nie powiódł się. Nie uzyskano odpowiedzi. Spróbuj ponownie.'));
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  return (
    <section aria-labelledby="question-tests-title" className="min-w-0 space-y-5">
      <div>
        <h2 id="question-tests-title" className="font-serif text-2xl text-sand-100">Test pytań</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-sand-100/65">
          Wybierz dowolny obiekt i zadaj pytanie niezależnie od dzisiejszego celu gry. Test używa aktualnych danych i modeli oraz uruchamia planer od nowa, bez zapisanej w pamięci interpretacji — nie odtwarza historycznej wersji serwera. Nie zużywa prób ani nie zmienia postępów graczy. Możesz powtarzać pytania.
        </p>
      </div>

      <form onSubmit={(event) => void runTest(event)} className={cardClass} aria-busy={busy}>
        <fieldset disabled={busy} className="min-w-0 space-y-4">
          <legend className="sr-only">Parametry testu pytania</legend>
          <div className="grid min-w-0 gap-4 sm:grid-cols-2">
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-sand-100/65">
              Tryb gry
              <select value={mode} onChange={(event) => {
                setMode(event.target.value as QuestionTestMode);
                setEntityId(null);
                setSearch('');
                clearResult();
              }} className={controlClass}>
                {Object.entries(MODE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-sand-100/65">
              Szukaj obiektu
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Wpisz nazwę…" disabled={loadingEntities || !!entities?.error} className={controlClass} />
            </label>
            <label className="flex min-w-0 flex-col gap-1.5 text-xs text-sand-100/65 sm:col-span-2">
              Obiekt do testu
              <select value={entityId ?? ''} disabled={loadingEntities || !!entities?.error || availableEntities.length === 0} required onChange={(event) => {
                setEntityId(event.target.value ? Number(event.target.value) : null);
                clearResult();
              }} className={controlClass}>
                <option value="">{loadingEntities ? 'Ładowanie obiektów…' : 'Wybierz obiekt'}</option>
                {visibleEntities.map((entity) => <option key={entity.id} value={entity.id}>{entity.name} · ID {entity.id}</option>)}
              </select>
            </label>
          </div>
          {loadingEntities && <p role="status" className="text-sm text-sand-100/65">Ładowanie obiektów…</p>}
          {entities?.error && !loadingEntities && <div role="alert" className="space-y-2 text-sm text-red-300">
            <p>{entities.error}</p>
            <button type="button" onClick={() => { setEntities(null); setRevision((value) => value + 1); }} className={`${controlClass} flex w-auto items-center gap-2`}><RefreshCw size={14} aria-hidden="true" />Ponów pobieranie</button>
          </div>}
          {!loadingEntities && !entities?.error && availableEntities.length === 0 && <p role="status" className="text-sm text-sand-100/65">Brak obiektów w tym trybie.</p>}
          {!loadingEntities && availableEntities.length > 0 && filteredEntities.length === 0 && <p role="status" className="text-sm text-sand-100/65">Brak wyników wyszukiwania. Zmień filtr; wcześniej wybrany obiekt pozostaje wybrany.</p>}
          {report && mode === report.mode && !loadingEntities && !entities?.error && matchingTargets.length !== 1 && <p role="status" className="text-sm text-amber-300">
            Nie znaleziono jednoznacznego dopasowania nazwy „{report.details.target_name}”. Wybierz obiekt ręcznie. Automatyczne porównanie ze zgłoszeniem nie jest możliwe bez jednoznacznego celu.
          </p>}
          <label className="flex min-w-0 flex-col gap-1.5 text-xs text-sand-100/65">
            Pytanie
            <textarea value={question} maxLength={100} rows={3} required aria-describedby="question-test-counter" onChange={(event) => {
              setQuestion(event.target.value);
              clearResult();
            }} placeholder="Czy ten obiekt…?" className={`${controlClass} resize-y`} />
          </label>
          <p id="question-test-counter" className={`text-right text-xs ${question.length > 100 ? 'text-red-300' : 'text-sand-100/55'}`}>{question.length}/100 znaków{question.length > 100 ? ' — skróć pytanie, aby uruchomić test' : ''}</p>
          <button type="submit" disabled={!canSubmit} className="flex w-full items-center justify-center gap-2 rounded-sm border border-emerald-400/30 bg-emerald-400/10 px-4 py-2.5 text-sm font-semibold text-emerald-300 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto">
            {busy ? <Loader2 size={16} aria-hidden="true" className="animate-spin" /> : <Play size={16} aria-hidden="true" />}
            {busy ? 'Testowanie…' : completed ? 'Uruchom ponownie' : 'Uruchom test'}
          </button>
        </fieldset>
        {busy && <p role="status" className="text-sm text-sand-100/65">Oczekiwanie na odpowiedź. Parametry testu są zablokowane do zakończenia.</p>}
        {error && <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-300">{error}</p>}
      </form>

      {report && <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-sand-100/65">
        <p>Porównanie ze zgłoszeniem #{report.id}. Test nie zmienia statusu zgłoszenia.</p>
        <button type="button" disabled={busy} onClick={onClearReport} className={`${controlClass} w-auto hover:bg-white/5`}>Odłącz zgłoszenie</button>
      </div>}
      <div className={`grid min-w-0 gap-4 ${report ? 'lg:grid-cols-2' : ''}`}>
        {report && <article className={cardClass} aria-labelledby="historical-answer-title">
          <h3 id="historical-answer-title" className="font-semibold text-sand-100">Historyczna odpowiedź ze zgłoszenia #{report.id}</h3>
          <p className="break-words text-sm text-sand-100/65">{MODE_LABELS[report.mode]} · {report.details.target_name} · {report.details.game_date}</p>
          <p className="whitespace-pre-wrap break-words text-sm text-sand-100">{report.details.original_question}</p>
          <Answer valid={report.details.valid} answer={report.details.answer} />
          <dl className="space-y-3 text-sm">
            <div><dt className="text-xs text-sand-100/55">Wersja historycznego serwera</dt><dd className="break-words font-mono text-xs text-sand-100/80">{report.details.server_version ?? 'Nie zapisano'}</dd></div>
            <div><dt className="text-xs text-sand-100/55">Wyjaśnienie historyczne</dt><dd className="whitespace-pre-wrap break-words text-sand-100/80">{report.details.explanation || 'Nie zapisano wyjaśnienia.'}</dd></div>
          </dl>
        </article>}
        {completed ? <article className={cardClass} aria-labelledby="current-answer-title">
          <h3 id="current-answer-title" className="font-semibold text-sand-100">Aktualny wynik testu</h3>
          <p className="break-words text-sm text-sand-100/65">{MODE_LABELS[completed.request.mode]} · {completed.entity.name} · ID {completed.request.entity_id}</p>
          <dl className="space-y-3 text-sm">
            <div><dt className="text-xs text-sand-100/55">Wysłane pytanie</dt><dd className="whitespace-pre-wrap break-words text-sand-100">{completed.request.question}</dd></div>
            <div><dt className="text-xs text-sand-100/55">Zinterpretowane pytanie</dt><dd className="whitespace-pre-wrap break-words text-sand-100/80">{completed.result.question ?? 'Brak interpretacji'}</dd></div>
          </dl>
          <Answer valid={completed.result.valid} answer={completed.result.answer} />
          {report && <p role="status" className={`rounded-sm border p-3 text-sm ${completed.comparableReportId === report.id ? 'border-emerald-400/30 text-sand-100' : 'border-white/10 text-sand-100/65'}`}>
            {completed.comparableReportId !== report.id
              ? 'Nie porównujemy wyników: wybrano inny tryb, obiekt lub pytanie albo cel zgłoszenia nie jest jednoznaczny.'
              : completed.result.valid === report.details.valid && completed.result.answer === report.details.answer
                ? 'Zgodność: poprawność pytania i odpowiedź TAK/NIE są takie same jak w zgłoszeniu.'
                : 'Różnica: poprawność pytania lub odpowiedź TAK/NIE zmieniła się względem zgłoszenia.'}
          </p>}
          <dl className="grid min-w-0 gap-3 text-sm sm:grid-cols-2">
            <div className="min-w-0 sm:col-span-2"><dt className="text-xs text-sand-100/55">Wyjaśnienie</dt><dd className="whitespace-pre-wrap break-words text-sand-100/80">{completed.result.explanation || 'Brak wyjaśnienia.'}</dd></div>
            <div className="min-w-0"><dt className="text-xs text-sand-100/55">Źródło odpowiedzi</dt><dd className="text-sand-100/80">{SOURCE_LABELS[completed.result.source]} <span className="font-mono text-xs">({completed.result.source})</span></dd></div>
            <div><dt className="text-xs text-sand-100/55">Czas wykonania na serwerze</dt><dd className="text-sand-100/80">{completed.result.duration_ms.toLocaleString('pl-PL')} ms</dd></div>
            <div className="min-w-0 sm:col-span-2"><dt className="text-xs text-sand-100/55">Aktualna wersja serwera</dt><dd className="break-words font-mono text-xs text-sand-100/80">{completed.result.server_version}</dd></div>
          </dl>
          <details className="min-w-0 border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-sm text-emerald-300">Kontekst odpowiedzi</summary>
            <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-obsidian-950 p-3 text-xs text-sand-100/75">{completed.result.context || 'Brak kontekstu.'}</pre>
          </details>
          <details className="min-w-0 border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-sm text-emerald-300">Plan diagnostyczny (JSON)</summary>
            <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-obsidian-950 p-3 text-xs text-sand-100/75">{completed.result.plan === null ? 'Brak planu diagnostycznego.' : JSON.stringify(completed.result.plan, null, 2)}</pre>
          </details>
        </article> : <div className={`${cardClass} text-sm text-sand-100/65`}><p>{busy ? 'Trwa testowanie — wynik pojawi się tutaj.' : 'Brak aktualnego wyniku. Wybierz parametry i uruchom test.'}</p></div>}
      </div>
    </section>
  );
}
