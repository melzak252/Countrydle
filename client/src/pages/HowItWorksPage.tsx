import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Cpu,
  Database,
  Zap,
  GitBranch,
  Code2,
  CheckCircle2,
  XCircle,
  Compass,
  Globe,
  Layers,
  Terminal,
  ArrowRight,
  ShieldCheck,
  FileCode,
  HelpCircle,
  Binary,
  Check,
  X,
  Search,
  Scale,
  Lock,
} from 'lucide-react';
import { cn } from '../lib/utils';

interface QuestionExample {
  id: string;
  questionEn: string;
  questionPl: string;
  mode: string;
  stageName: string;
  stageBadge: string;
  stageColor: string;
  latency: string;
  operator: string;
  relation: string;
  planJson: string;
  sqlQuery: string;
  targetEntity: string;
  verdict: boolean | null;
  explanationEn: string;
  explanationPl: string;
  auditTag: string;
  whyThisStageEn: string;
  whyThisStagePl: string;
}

const QUESTION_EXAMPLES: QuestionExample[] = [
  {
    id: 'country-landlocked',
    questionEn: 'Is it landlocked?',
    questionPl: 'Czy państwo jest śródlądowe?',
    mode: 'Countrydle (World)',
    stageName: 'Stage 0: Deterministic Fast-Path Template',
    stageBadge: '< 1 ms Fast-Path',
    stageColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    latency: '0.4 ms',
    operator: 'not(exists(water_access))',
    relation: 'water_access',
    planJson: JSON.stringify(
      [
        { entity: 'target_country', relation: 'water_access', operator: 'exists' },
        { operator: 'not', args: [0] },
      ],
      null,
      2
    ),
    sqlQuery: 'SELECT water_body FROM country_water_access WHERE country_id = ? LIMIT 1;',
    targetEntity: 'Poland (Target)',
    verdict: false,
    explanationEn: 'Poland borders the Baltic Sea and is not landlocked.',
    explanationPl: 'Polska ma dostęp do Morza Bałtyckiego i nie jest krajem śródlądowym.',
    auditTag: 'local_kb:water_access',
    whyThisStageEn: 'Common natural language templates (landlocked, island, borders, driving side) compile into abstract syntax trees in sub-millisecond memory without invoking any LLM, costing zero tokens.',
    whyThisStagePl: 'Popularne szablony językowe (kraj śródlądowy, wyspa, granice, ruch lewostronny) kompilują się w pamięci poniżej milisekundy bez udziału LLM i bez kosztu tokenów.',
  },
  {
    id: 'country-borders',
    questionEn: 'Does it border Germany?',
    questionPl: 'Czy graniczy z Niemcami?',
    mode: 'Countrydle (World)',
    stageName: 'Stage 0: Deterministic Fast-Path Template',
    stageBadge: '< 1 ms Fast-Path',
    stageColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    latency: '0.3 ms',
    operator: 'contains(borders_country)',
    relation: 'borders_country',
    planJson: JSON.stringify(
      [
        {
          operator: 'contains',
          left: { entity: 'target_country', relation: 'borders_country' },
          right: { value: 'Germany' },
        },
      ],
      null,
      2
    ),
    sqlQuery: 'SELECT border_country_name FROM country_borders WHERE country_id = ? UNION SELECT c.app_country_name FROM country_borders cb JOIN countries c ON cb.border_cca3 = c.cca3 WHERE cb.country_id = ?;',
    targetEntity: 'Poland (Target)',
    verdict: true,
    explanationEn: 'Poland shares a land border with Germany.',
    explanationPl: 'Polska dzieli granicę lądową z Niemcami.',
    auditTag: 'local_kb:borders_country',
    whyThisStageEn: 'Polish and English country names and inflections ("z Niemcami" → Germany) are mapped directly via compiled regular expressions to SQLite relational lookups.',
    whyThisStagePl: 'Polskie i angielskie odmiany nazw państw („z Niemcami” → Germany) są natychmiastowo mapowane przez skompilowane wyrażenia regularne do zapytań w bazie SQLite.',
  },
  {
    id: 'us-pacific-ocean',
    questionEn: 'Does it have access to the Pacific Ocean?',
    questionPl: 'Czy ma dostęp do Oceanu Spokojnego?',
    mode: 'US Statedle (50 States)',
    stageName: 'Stage 0: Deterministic Fast-Path Template',
    stageBadge: '< 1 ms Fast-Path',
    stageColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    latency: '0.4 ms',
    operator: 'contains_exact(water_access)',
    relation: 'water_access',
    planJson: JSON.stringify(
      {
        operator: 'contains_exact',
        left: { entity: 'target_state', relation: 'water_access' },
        right: { value: 'Pacific Ocean' },
      },
      null,
      2
    ),
    sqlQuery: 'SELECT water_body FROM us_state_water_access WHERE state_id = ?;',
    targetEntity: 'Washington (Target)',
    verdict: true,
    explanationEn: 'Washington has coastline along the Pacific Ocean.',
    explanationPl: 'Stan Waszyngton posiada linię brzegową nad Oceanem Spokojnym.',
    auditTag: 'local_kb:water_access',
    whyThisStageEn: 'Specific ocean bodies (Pacific, Atlantic, Arctic, Gulf of Mexico) are mapped to explicit water_access entries rather than broad boolean coastline checks.',
    whyThisStagePl: 'Konkretne akweny (Pacyfik, Atlantyk, Arktyczny, Zatoka Meksykańska) są mapowane do dokładnych wpisów tabeli dostępu do wód, a nie do ogólnej flagi nadmorskiej.',
  },
  {
    id: 'powiat-city-county',
    questionEn: 'Is it a city with county rights?',
    questionPl: 'Czy to miasto na prawach powiatu?',
    mode: 'Powiatdle (380 Counties)',
    stageName: 'Stage 0: Deterministic Fast-Path Template',
    stageBadge: '< 1 ms Fast-Path',
    stageColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    latency: '0.2 ms',
    operator: 'equals(is_city_county, True)',
    relation: 'is_city_county',
    planJson: JSON.stringify(
      {
        operator: 'equals',
        left: { entity: 'target_powiat', relation: 'is_city_county' },
        right: { value: 1 },
      },
      null,
      2
    ),
    sqlQuery: 'SELECT is_city_county FROM powiaty WHERE id = ?;',
    targetEntity: 'Powiat m. Kraków (Target)',
    verdict: true,
    explanationEn: 'm. Kraków is a city with county rights (miasto na prawach powiatu).',
    explanationPl: 'm. Kraków to miasto na prawach powiatu.',
    auditTag: 'local_kb:is_city_county',
    whyThisStageEn: 'Domain-specific Polish administrative structures (powiat grodzki vs powiat ziemski) are indexed as primary booleans and resolved instantaneously.',
    whyThisStagePl: 'Specyficzne polskie struktury administracyjne (powiat grodzki vs ziemski) są zaindeksowane jako podstawowe flagi logiczne i rozwiązywane błyskawicznie.',
  },
  {
    id: 'wojewodztwo-population',
    questionEn: 'Does this voivodeship have over 3 million residents?',
    questionPl: 'Czy to województwo ma ponad 3 miliony mieszkańców?',
    mode: 'Województwodle (16 Voivodeships)',
    stageName: 'Stage 1: Gemini 2.5 Flash Lite AST Planner',
    stageBadge: 'Structured AST Planner',
    stageColor: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
    latency: '1,020 ms',
    operator: 'greater_than(population, 3000000)',
    relation: 'population',
    planJson: JSON.stringify(
      {
        route: 'local',
        plan: {
          operator: 'greater_than',
          left: { entity: 'target_voivodeship', relation: 'population' },
          right: { value: 3000000 },
        },
      },
      null,
      2
    ),
    sqlQuery: 'SELECT population FROM voivodeships WHERE id = ?;',
    targetEntity: 'Województwo Mazowieckie (Target)',
    verdict: true,
    explanationEn: 'Mazowieckie: population = 5,514,699 (greater than 3,000,000).',
    explanationPl: 'Mazowieckie: liczba ludności = 5 514 699 (więcej niż 3 000 000).',
    auditTag: 'local_kb:population',
    whyThisStageEn: 'Arbitrary numeric thresholds, comparisons, and custom quantitative phrasing are translated into an Abstract Syntax Tree by Gemini Flash Lite, and evaluated by the SQLite engine.',
    whyThisStagePl: 'Dowolne progi liczbowe, porównania i niestandardowe sformułowania ilościowe są tłumaczone na drzewo AST przez Gemini Flash Lite i ewaluowane w silniku SQLite.',
  },
  {
    id: 'spatial-coordinates',
    questionEn: 'Is it located east of Italy?',
    questionPl: 'Czy leży na wschód od Włoch?',
    mode: 'Countrydle (World)',
    stageName: 'Stage 1: Gemini 2.5 Flash Lite AST Planner',
    stageBadge: 'Structured AST Planner',
    stageColor: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
    latency: '1,180 ms',
    operator: 'east_of(coordinates.longitude, Italy)',
    relation: 'coordinates.longitude',
    planJson: JSON.stringify(
      [
        {
          operator: 'east_of',
          left: { entity: 'target_country', relation: 'coordinates.longitude' },
          right: { entity: 'Italy', relation: 'coordinates.longitude' },
        },
      ],
      null,
      2
    ),
    sqlQuery: 'SELECT longitude FROM countries WHERE app_country_name = "Poland"; SELECT longitude FROM countries WHERE app_country_name = "Italy";',
    targetEntity: 'Poland (Target)',
    verdict: true,
    explanationEn: 'Poland (19.14°E) is east of Italy (12.57°E).',
    explanationPl: 'Polska (19,14°E) leży na wschód od Włoch (12,57°E).',
    auditTag: 'local_kb:coordinates.longitude',
    whyThisStageEn: 'Cardinal direction operators (north_of, south_of, east_of, west_of) resolve reference entity coordinates from SQLite and mathematically compare longitudes and latitudes.',
    whyThisStagePl: 'Operatory stron świata (north_of, south_of, east_of, west_of) pobierają współrzędne encji odniesienia z bazy SQLite i precyzyjnie porównują stopnie długości i szerokości geograficznej.',
  },
  {
    id: 'world-cup-rag',
    questionEn: 'Did this country win the 1998 FIFA World Cup?',
    questionPl: 'Czy ten kraj wygrał Mistrzostwa Świata w 1998 roku?',
    mode: 'Countrydle (World)',
    stageName: 'Stage 3: Vector Retrieval & LLM Fallback (RAG)',
    stageBadge: 'Semantic Vector RAG',
    stageColor: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    latency: '1,840 ms',
    operator: 'vector_search(qdrant) + gpt-4o-mini',
    relation: 'rag:wikipedia_corpus',
    planJson: JSON.stringify(
      {
        route: 'fallback',
        plan: null,
        fallback_reason: 'The local facts database does not store historical sports tournament results.',
      },
      null,
      2
    ),
    sqlQuery: '-- Qdrant Vector Collection: "countries"\n-- Query vector: OpenAI text-embedding-3-small (1536 dims)\n-- Filter: payload.country_id = ?\n-- Model reasoning: gpt-4o-mini with mandatory verbatim source citation',
    targetEntity: 'France (Target)',
    verdict: true,
    explanationEn: 'Yes. France won the 1998 FIFA World Cup on home soil, defeating Brazil 3–0 in the final.',
    explanationPl: 'Tak. Francja wygrała Mistrzostwa Świata 1998 u siebie, pokonując w finale Brazylię 3:0.',
    auditTag: 'rag:vector_search',
    whyThisStageEn: 'When questions ask about specialized history, sports, or culture outside local SQLite tables, the planner triggers a Qdrant semantic vector search against indexed Wikipedia archives.',
    whyThisStagePl: 'Gdy pytania dotyczą wiedzy specjalistycznej, sportu czy kultury wykraczającej poza tabele SQLite, planner uruchamia wyszukiwanie wektorowe w Qdrant na zaindeksowanych zasobach Wikipedii.',
  },
  {
    id: 'open-ended-rejected',
    questionEn: 'What is the capital city?',
    questionPl: 'Jaka jest stolica?',
    mode: 'All Game Modes',
    stageName: 'Stage 0: Deterministic Input Guard',
    stageBadge: 'Rejected (0 turns charged)',
    stageColor: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
    latency: '0.1 ms',
    operator: 'check_open_ended_question()',
    relation: 'input_guard',
    planJson: JSON.stringify(
      {
        valid: false,
        supported: false,
        explanation: 'Questions must be binary Yes/No questions. Please ask whether the location has a specific property.',
      },
      null,
      2
    ),
    sqlQuery: '-- No database queries executed. The turn quota is preserved.',
    targetEntity: 'Any Target',
    verdict: null,
    explanationEn: 'Rejected as an open-ended question. Your turn was not deducted.',
    explanationPl: 'Odrzucono jako pytanie otwarte. Tura nie została potrącona.',
    auditTag: 'guard:open_ended',
    whyThisStageEn: 'Wh-questions ("what", "who", "which", "where", "jaki", "gdzie") are caught at the entry gate, preventing wasted LLM calls and preserving the player\'s question quota.',
    whyThisStagePl: 'Pytania zaimkowe („co”, „kto”, „jaki”, „gdzie”) są wychwytywane na bramce wejściowej, co zapobiega zbędnym wywołaniom API i chroni limit pytań gracza.',
  },
];

interface PipelineStep {
  step: string;
  nameEn: string;
  namePl: string;
  tag: string;
  tagColor: string;
  icon: typeof Terminal;
  summaryEn: string;
  summaryPl: string;
  antiHallucinationEn: string;
  antiHallucinationPl: string;
  codeSnippet: string;
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    step: '01',
    nameEn: 'Input Intake & Security Guard',
    namePl: 'Normalizacja & Bramka Bezpieczeństwa',
    tag: '< 0.1 ms Execution',
    tagColor: 'text-zinc-300 border-white/10 bg-white/5',
    icon: Terminal,
    summaryEn: 'Applies Unicode NFKD decomposition, Polish character folding (ł→l), phonetic typo tolerance, and immediately stops non-binary questions ("what", "where", "who", "jaka") before any AI API call.',
    summaryPl: 'Wykonuje dekompozycję Unicode NFKD, usuwanie znaków diakrytycznych, tolerancję literówek i natychmiast zatrzymuje pytania otwarte („jaka”, „gdzie”, „co”) przed wywołaniem AI.',
    antiHallucinationEn: 'Eliminates open-ended speculation and prompt injection attempts before they reach the reasoning layer. Preserves player turns when queries are unanswerable.',
    antiHallucinationPl: 'Eliminuje spekulacje otwarte oraz próby wstrzykiwania promptów zanim dotrą do modeli. Zachowuje limit tur gracza.',
    codeSnippet: 'if check_generic_open_ended_question(query):\n    return QuestionPlan(valid=False, explanation="Must be a Yes/No question.")',
  },
  {
    step: '02',
    nameEn: 'Sub-millisecond Template Compiler',
    namePl: 'Błyskawiczny Kompilator Szablonów',
    tag: '< 1 ms (No LLM Call)',
    tagColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    icon: Zap,
    summaryEn: 'Fast-path in-memory compiler executing compiled regex trees across 672 country forms, 50 states, Polish counties, borders, seas, license plates, and population ranges. Intercepts ~50% of all player questions.',
    summaryPl: 'Błyskawiczny kompilator w pamięci RAM obsługujący 672 formy państw, 50 stanów, powiaty, granice, morza i tablice. Przechwytuje około 50% wszystkich zapytań graczy.',
    antiHallucinationEn: 'Zero hallucination probability. The question completely bypasses generative language models and translates deterministically into an AST node directly in RAM.',
    antiHallucinationPl: 'Zerowe prawdopodobieństwo halucynacji. Pytanie w 100% omija modele językowe i tłumaczy się deterministycznie na węzeł AST wprost w pamięci RAM.',
    codeSnippet: 'def compile_template(q: str):\n    if re.search(r"\\b(landlocked|srodladow\\w*)\\b", q):\n        return [_node("exists", "water_access"), {"operator": "not", "args": [0]}]',
  },
  {
    step: '03',
    nameEn: 'Plan Hash-Cache Layer',
    namePl: 'Warstwa Pamięci Podręcznej Planów',
    tag: 'SQLite plan_cache.sqlite',
    tagColor: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    icon: Database,
    summaryEn: 'Before calling external models, normalized questions are looked up against an indexed SQLite plan cache. If an identical query was compiled for this engine version, the AST is replayed instantly.',
    summaryPl: 'Przed wywołaniem modelu zewnętrzne zapytanie jest sprawdzane w zindeksowanym buforze planów SQLite. Identyczne pytania zwracają zweryfikowane drzewo natychmiast.',
    antiHallucinationEn: 'Guarantees idempotence: the same query will never receive conflicting structural interpretations between different players or consecutive turns.',
    antiHallucinationPl: 'Gwarantuje idempotencję: to samo zapytanie nigdy nie otrzyma sprzecznych interpretacji strukturalnych u różnych graczy.',
    codeSnippet: 'cached_ast = plan_cache.get(mode, normalized_query, version=ENGINE_VERSION)\nif cached_ast:\n    return execute_plan(config, target_entity, cached_ast)',
  },
  {
    step: '04',
    nameEn: 'Constrained Gemini AST Planner',
    namePl: 'Ściśle Ograniczony Parser AST (Gemini)',
    tag: 'Gemini 2.5 Flash Lite',
    tagColor: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
    icon: Cpu,
    summaryEn: 'For complex, nuanced, or creative phrasing, Gemini 2.5 Flash Lite runs in strict JSON schema mode. Crucially, the model is FORBIDDEN from answering the question. It acts solely as a programming language parser.',
    summaryPl: 'Dla nietypowych sformułowań model Gemini 2.5 Flash Lite działa w ścisłym trybie schematu JSON. Modelowi pod groźbą błędu NIE WOLNO odpowiadać na pytanie — działa tylko jako parser.',
    antiHallucinationEn: 'The model has no authority over facts. It cannot declare whether Poland borders Germany or Washington touches the Pacific. It can only emit a formal syntax tree to be proven by the database.',
    antiHallucinationPl: 'Model nie decyduje o faktach. Nie może orzec, czy Polska graniczy z Niemcami. Może wyłącznie wygenerować formalne drzewo do udowodnienia w bazie.',
    codeSnippet: '{\n  "route": "local",\n  "plan": [\n    {"operator": "east_of", "left": {"relation": "coordinates.longitude"}, "right": {"entity": "Germany"}}\n  ]\n}',
  },
  {
    step: '05',
    nameEn: 'Semantic Entity Safety Validator',
    namePl: 'Weryfikator Bezpieczeństwa Encji',
    tag: 'find_country / find_state',
    tagColor: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
    icon: ShieldCheck,
    summaryEn: 'Any entity literal produced by the planner (e.g. "Germany", "Micronesia", "California") is verified against the canonical SQLite catalog. If a spelling is unknown or ambiguous, the engine refuses to guess and asks for clarification.',
    summaryPl: 'Każda encja wskazana przez planner (np. „Niemcy”, „Mikronezja”, „Kalifornia”) jest sprawdzana w katalogu SQLite. Jeśli zapis jest nierozpoznany, silnik żąda doprecyzowania zamiast zgadywać.',
    antiHallucinationEn: 'Prevents phantom entities or hallucinated spellings from producing false negative or false positive results during relational execution.',
    antiHallucinationPl: 'Zapobiega sytuacjom, w których wymyślona przez model nazwa encji dałaby fałszywy wynik w kwerendzie bazy.',
    codeSnippet: 'for candidate in _extract_names(plan):\n    if find_country(conn, candidate) is None:\n        return QuestionPlan(valid=False, explanation=f"Clarify: {candidate!r}")',
  },
  {
    step: '06',
    nameEn: 'Deterministic Relational Fact Engine',
    namePl: 'Relacyjny Silnik Ewaluacji Faktów (SQLite)',
    tag: '0.0% Hallucination Truth',
    tagColor: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    icon: Binary,
    summaryEn: 'The AST tree is executed mathematically and relationally against normalized SQLite tables. Computes coordinate degrees, water body sets, and border relationships with mathematical certainty.',
    summaryPl: 'Drzewo AST jest wykonywane matematycznie i relacyjnie na znormalizowanych tabelach SQLite. Oblicza współrzędne, zbiory wód i sąsiedztwa ze 100% pewnością matematyczną.',
    antiHallucinationEn: 'This is the core pillar of Countrydle. The final True/False answer is produced by database rows, never by stochastic neural token probabilities.',
    antiHallucinationPl: 'To główny filar Countrydle. Ostateczna odpowiedź True/False pochodzi z rekordów bazy danych, a nie z probabilistycznych tokenów sieci neuronowej.',
    codeSnippet: 'db_waters = {r[0] for r in conn.execute("SELECT water_body FROM country_water_access WHERE country_id=?", (cid,))}\nanswer = "Atlantic Ocean" in db_waters',
  },
  {
    step: '07',
    nameEn: 'Verifiable Fallback RAG Pipeline',
    namePl: 'Weryfikowalny Fallback Wektorowy RAG',
    tag: 'Qdrant + gpt-4o-mini',
    tagColor: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    icon: Search,
    summaryEn: 'If a question asks about specialized cultural or sports history outside SQLite tables (e.g. "Did this country win the 1998 World Cup?"), the question triggers a Qdrant semantic vector search against indexed Wikipedia summaries.',
    summaryPl: 'Gdy pytanie dotyczy kultury lub sportu spoza tabel SQLite, następuje wyszukiwanie wektorowe w Qdrant na zindeksowanych artykułach Wikipedii.',
    antiHallucinationEn: 'The reasoning model (gpt-4o-mini) is strictly constrained: it MUST quote the exact sentence from the retrieved text snippet as proof. If the text does not mention the fact, it refuses to confirm.',
    antiHallucinationPl: 'Model gpt-4o-mini ma ścisły nakaz cytowania dokładnego zdania z pobranego fragmentu jako dowodu. Bez wyraźnego potwierdzenia w tekście nie zatwierdzi odpowiedzi.',
    codeSnippet: 'docs = qdrant.search(collection="countries", query_vector=emb, limit=3)\nresponse = rag_model.generate(system_prompt=STRICT_CITATION, context=docs)',
  },
  {
    step: '08',
    nameEn: 'Audit Trail & Transparency Tagging',
    namePl: 'Ścieżka Audytu & Transparentne Tagowanie',
    tag: 'Audit Relation Tag',
    tagColor: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/10',
    icon: FileCode,
    summaryEn: 'Every resolved answer is stamped with its human proof and audit relation tag (e.g. "local_kb:water_access", "rag:vector_search"). Players can report questionable answers post-game without exposing secret targets.',
    summaryPl: 'Każda odpowiedź otrzymuje dowód tekstowy i tag relacji (np. „local_kb:water_access”, „rag:vector_search”). Gracze mogą zgłaszać wątpliwe odpowiedzi bez ujawniania hasła dnia.',
    antiHallucinationEn: 'Crowdsourced accountability. Every single factual evaluation is stored and auditable by administrators and verified by players after round completion.',
    antiHallucinationPl: 'Pełna transparentność. Każda ewaluacja jest zapisana i audytowalna przez administratorów oraz weryfikowalna przez graczy po zakończeniu gry.',
    codeSnippet: 'return QuestionDisplay(answer=True, explanation="Poland borders Baltic Sea.", context="local_kb:water_access")',
  },
];

interface OperatorSpec {
  name: string;
  category: 'comparison' | 'collection' | 'spatial' | 'string' | 'logic';
  signature: string;
  descriptionEn: string;
  descriptionPl: string;
  exampleEn: string;
  exampleAst: string;
}

const OPERATOR_SPECS: OperatorSpec[] = [
  {
    name: 'equals',
    category: 'comparison',
    signature: 'equals(left: Reference, right: Literal)',
    descriptionEn: 'Tests strict equality between a scalar property and an expected value.',
    descriptionPl: 'Sprawdza ścisłą równość między właściwością skalarną a wartością oczekiwaną.',
    exampleEn: '"Is it an island?" → equals(is_island, True)',
    exampleAst: '{"operator": "equals", "left": {"entity": "target_country", "relation": "is_island"}, "right": {"value": true}}',
  },
  {
    name: 'greater_than / less_than',
    category: 'comparison',
    signature: 'greater_than(left: Reference, right: Literal)',
    descriptionEn: 'Evaluates numeric thresholds for population, square area, admission order, or year.',
    descriptionPl: 'Porównuje progi numeryczne populacji, powierzchni, roku przyjęcia lub kolejności.',
    exampleEn: '"Does it have more than 50 million people?"',
    exampleAst: '{"operator": "greater_than", "left": {"entity": "target_country", "relation": "population"}, "right": {"value": 50000000}}',
  },
  {
    name: 'contains / contains_exact',
    category: 'collection',
    signature: 'contains_exact(left: Reference, right: Literal)',
    descriptionEn: 'Checks membership in one-to-many sets: water bodies, border neighbors, or international organizations.',
    descriptionPl: 'Sprawdza przynależność do zbiorów relacyjnych: akwenów, sąsiadów granicznych, organizacji.',
    exampleEn: '"Does it border France?"',
    exampleAst: '{"operator": "contains_exact", "left": {"entity": "target_country", "relation": "borders_country"}, "right": {"value": "France"}}',
  },
  {
    name: 'exists',
    category: 'collection',
    signature: 'exists(left: Reference)',
    descriptionEn: 'Unary operator checking if a relation contains at least one record (e.g. has coastline or mountain ranges).',
    descriptionPl: 'Operator jednoargumentowy badający, czy relacja zawiera co najmniej jeden wpis (np. czy ma góry lub wybrzeże).',
    exampleEn: '"Does this state have mountain ranges?"',
    exampleAst: '{"operator": "exists", "left": {"entity": "target_state", "relation": "mountain_ranges"}}',
  },
  {
    name: 'north_of / east_of',
    category: 'spatial',
    signature: 'east_of(left: Reference, right: Reference)',
    descriptionEn: 'Geographic coordinate comparison across longitudes or latitudes against reference entities.',
    descriptionPl: 'Przestrzenne porównanie współrzędnych geograficznych względem encji odniesienia.',
    exampleEn: '"Is it east of Germany?"',
    exampleAst: '{"operator": "east_of", "left": {"entity": "target_country", "relation": "coordinates.longitude"}, "right": {"entity": "Germany", "relation": "coordinates.longitude"}}',
  },
  {
    name: 'starts_with / ends_with',
    category: 'string',
    signature: 'starts_with(left: Reference, right: Literal)',
    descriptionEn: 'Case-insensitive prefix or suffix matching on entity names or license plate codes.',
    descriptionPl: 'Dopasowanie prefiksu lub sufiksu nazwy encji lub tablic rejestracyjnych bez względu na wielkość liter.',
    exampleEn: '"Does the country name start with B?"',
    exampleAst: '{"operator": "starts_with", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": "B"}}',
  },
  {
    name: 'char_count_equals',
    category: 'string',
    signature: 'char_count_equals(left: Reference, right: Literal)',
    descriptionEn: 'Compares the exact letter count of the name, ignoring spaces and hyphens.',
    descriptionPl: 'Porównuje dokładną liczbę liter w nazwie z pominięciem spacji i łączników.',
    exampleEn: '"Does the name have 6 letters?"',
    exampleAst: '{"operator": "char_count_equals", "left": {"entity": "target_country", "relation": "name"}, "right": {"value": 6}}',
  },
  {
    name: 'and / or / not',
    category: 'logic',
    signature: 'and(args: [nodeIndex1, nodeIndex2])',
    descriptionEn: 'Topological node combinators chaining sub-conditions with strict boolean algebra.',
    descriptionPl: 'Topologiczne kombinatory węzłów łączące podwarunki ścisłą algebrą Boole’a.',
    exampleEn: '"Is it in Europe and landlocked?"',
    exampleAst: '{"operator": "and", "args": [0, 1]}',
  },
];

export default function HowItWorksPage() {
  const { i18n } = useTranslation();
  const isPl = i18n.language.startsWith('pl');

  const [selectedExampleId, setSelectedExampleId] = useState<string>(QUESTION_EXAMPLES[0].id);
  const [activeStepIndex, setActiveStepIndex] = useState<number>(1); // Step 2 (Templates) by default
  const [operatorCategory, setOperatorCategory] = useState<'all' | 'comparison' | 'collection' | 'spatial' | 'string' | 'logic'>('all');
  const [activeTab, setActiveTab] = useState<'ast' | 'sql' | 'details'>('ast');

  const currentExample = QUESTION_EXAMPLES.find((e) => e.id === selectedExampleId) || QUESTION_EXAMPLES[0];
  const activeStep = PIPELINE_STEPS[activeStepIndex];
  const filteredOperators = operatorCategory === 'all'
    ? OPERATOR_SPECS
    : OPERATOR_SPECS.filter((op) => op.category === operatorCategory);

  return (
    <div className="mx-auto min-w-0 max-w-5xl space-y-16 pb-16 pt-4 text-sand-100">
      {/* 1. Header & Technical Metrics */}
      <header className="border-b border-white/10 pb-12">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-mono text-xs font-semibold uppercase tracking-widest text-emerald-400">
          <Cpu size={14} aria-hidden="true" />
          {isPl ? 'Architektura Silnika QA' : 'Question Answering Architecture'}
        </div>
        <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl lg:text-6xl">
          {isPl ? 'Jak Countrydle Odpowiada na Pytania?' : 'How Countrydle Answers Questions'}
        </h1>
        <p className="mt-5 max-w-3xl text-base leading-relaxed text-zinc-400 sm:text-lg">
          {isPl
            ? 'Zamiast polegać na halucynacjach generatorów tekstu, Countrydle wykorzystuje hybrydowy silnik: deterministyczne kompilatory szablonów (<1ms), formalny parser AST (Gemini 2.5 Flash Lite), lokalne bazy wiedzy SQLite oraz fallback RAG z wektorami w Qdrant.'
            : 'Rather than trusting raw LLM hallucinations, Countrydle uses a hybrid engine: sub-millisecond deterministic template compilers, Gemini 2.5 Flash Lite as a formal AST parser, curated local SQLite relational fact tables, and verifiable semantic vector RAG.'}
        </p>

        {/* Metrics Grid */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs uppercase tracking-wider font-mono">{isPl ? 'Szablony' : 'Templates'}</span>
              <Zap size={16} className="text-emerald-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-emerald-300">&lt; 1 ms</div>
            <p className="mt-1 text-[11px] text-zinc-500">{isPl ? 'Kompilacja bez LLM' : 'Zero LLM overhead'}</p>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs uppercase tracking-wider font-mono">{isPl ? 'Planner AST' : 'AST Planner'}</span>
              <Cpu size={16} className="text-cyan-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-cyan-300">~1.1 s</div>
            <p className="mt-1 text-[11px] text-zinc-500">{isPl ? 'Gemini 2.5 Flash Lite' : 'Structured query plan'}</p>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs uppercase tracking-wider font-mono">{isPl ? 'Halucynacja' : 'Hallucination'}</span>
              <ShieldCheck size={16} className="text-amber-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-sand-100">0.0%</div>
            <p className="mt-1 text-[11px] text-zinc-500">{isPl ? 'Baza SQLite weryfikuje prawdę' : 'SQLite verifies truth'}</p>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900/60 p-4">
            <div className="flex items-center justify-between text-zinc-400">
              <span className="text-xs uppercase tracking-wider font-mono">{isPl ? 'Lokalne Encje' : 'Local Entities'}</span>
              <Database size={16} className="text-indigo-400" />
            </div>
            <div className="mt-2 font-mono text-2xl font-bold text-indigo-300">642</div>
            <p className="mt-1 text-[11px] text-zinc-500">{isPl ? 'Kraje, stany, powiaty, woj.' : 'Countries, states, counties'}</p>
          </div>
        </div>
      </header>

      {/* 2. Comprehensive Flow Graph of a Question & Anti-Hallucination Pipeline */}
      <section aria-labelledby="flow-graph-title" className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 id="flow-graph-title" className="font-serif text-2xl text-sand-100 sm:text-3xl flex items-center gap-2.5">
              <GitBranch className="text-emerald-400" size={26} aria-hidden="true" />
              <span>{isPl ? 'Graf Przepływu Pytania & Tarcza Anty-Halucynacyjna' : 'Question Flow Graph & Anti-Hallucination Shield'}</span>
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              {isPl
                ? 'Kliknij dowolny etap w grafie, aby zobaczyć dokładny kod, kwerendy i mechanizm eliminacji halucynacji AI.'
                : 'Click any step in the pipeline flow to inspect the exact code, queries, and anti-hallucination defense applied.'}
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 self-start sm:self-auto rounded-sm border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-mono text-xs text-emerald-300">
            <Lock size={13} />
            {isPl ? '8 Poziomów Ochrony' : '8 Defensive Layers'}
          </span>
        </div>

        {/* The Visual Flowchart Grid */}
        <div className="rounded-md border border-white/10 bg-obsidian-900 p-6 sm:p-8">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE_STEPS.map((stepItem, idx) => {
              const isCurrent = idx === activeStepIndex;
              const IconComp = stepItem.icon;
              return (
                <button
                  key={stepItem.step}
                  type="button"
                  aria-pressed={isCurrent}
                  onClick={() => setActiveStepIndex(idx)}
                  className={cn(
                    'group relative flex flex-col justify-between rounded-sm border p-4 text-left transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400',
                    isCurrent
                      ? 'border-emerald-400/60 bg-emerald-400/10 shadow-lg shadow-emerald-950/50 ring-1 ring-emerald-400/30'
                      : 'border-white/10 bg-obsidian-950/60 hover:border-white/20 hover:bg-obsidian-950/90 text-zinc-400'
                  )}
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className={cn(
                        'font-mono text-[10px] font-bold px-1.5 py-0.5 rounded border',
                        isCurrent ? 'border-emerald-400/40 text-emerald-300 bg-emerald-400/10' : 'border-white/10 text-zinc-500 bg-white/5'
                      )}>
                        STEP {stepItem.step}
                      </span>
                      <IconComp size={16} className={isCurrent ? 'text-emerald-300' : 'text-zinc-500 group-hover:text-zinc-400'} />
                    </div>
                    <h3 className={cn('mt-2.5 font-serif text-sm font-semibold leading-snug', isCurrent ? 'text-sand-50' : 'text-sand-200')}>
                      {isPl ? stepItem.namePl : stepItem.nameEn}
                    </h3>
                  </div>

                  <div className="mt-3 border-t border-white/5 pt-2">
                    <span className={cn('font-mono text-[10px] block truncate', isCurrent ? 'text-emerald-400' : 'text-zinc-500')}>
                      {stepItem.tag}
                    </span>
                  </div>

                  {/* Flow Arrow for larger screens */}
                  {idx < PIPELINE_STEPS.length - 1 && (
                    <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 pointer-events-none">
                      {idx % 4 !== 3 && (
                        <div className="h-4 w-4 rounded-full bg-obsidian-950 border border-white/15 flex items-center justify-center text-zinc-500">
                          <ArrowRight size={10} />
                        </div>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Active Step Deep-Dive Inspector Panel */}
          <div className="mt-6 rounded-sm border border-emerald-500/30 bg-obsidian-950/80 p-5 sm:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-sm border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center text-emerald-400 shrink-0">
                  <activeStep.icon size={18} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-emerald-400 font-bold">
                      PIPELINE STAGE {activeStep.step}
                    </span>
                    <span className="font-mono text-[10px] text-zinc-500">&bull;</span>
                    <span className="font-mono text-[10px] text-zinc-400">{activeStep.tag}</span>
                  </div>
                  <h3 className="font-serif text-xl text-sand-100 mt-0.5">
                    {isPl ? activeStep.namePl : activeStep.nameEn}
                  </h3>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={activeStepIndex === 0}
                  onClick={() => setActiveStepIndex((prev) => Math.max(0, prev - 1))}
                  className="rounded px-2.5 py-1 text-xs font-mono border border-white/10 bg-obsidian-900 text-zinc-400 hover:text-sand-100 disabled:opacity-30 disabled:pointer-events-none"
                >
                  &larr; Prev
                </button>
                <button
                  type="button"
                  disabled={activeStepIndex === PIPELINE_STEPS.length - 1}
                  onClick={() => setActiveStepIndex((prev) => Math.min(PIPELINE_STEPS.length - 1, prev + 1))}
                  className="rounded px-2.5 py-1 text-xs font-mono border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-30 disabled:pointer-events-none"
                >
                  Next &rarr;
                </button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="space-y-4">
                <div>
                  <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 block">
                    {isPl ? 'Co Robi Ten Etap?' : 'What Happens at This Stage?'}
                  </span>
                  <p className="mt-1.5 text-xs leading-relaxed text-zinc-300">
                    {isPl ? activeStep.summaryPl : activeStep.summaryEn}
                  </p>
                </div>

                <div className="rounded-sm border border-emerald-500/20 bg-emerald-500/[0.03] p-3.5">
                  <div className="flex items-center gap-2 text-emerald-400 font-mono text-[11px] font-semibold uppercase tracking-wider">
                    <ShieldCheck size={14} />
                    {isPl ? 'Tarcza Anty-Halucynacyjna' : 'Anti-Hallucination Defense'}
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-zinc-300">
                    {isPl ? activeStep.antiHallucinationPl : activeStep.antiHallucinationEn}
                  </p>
                </div>
              </div>

              <div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 block mb-1.5">
                  {isPl ? 'Wycinek Kodu Silnika' : 'Core Engine Logic'}
                </span>
                <pre className="overflow-x-auto rounded-sm border border-white/10 bg-obsidian-950 p-3.5 font-mono text-xs leading-relaxed text-sand-200">
                  <code>{activeStep.codeSnippet}</code>
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Interactive Live Pipeline Inspector (GRID LAYOUT) */}
      <section aria-labelledby="interactive-inspector-title" className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 id="interactive-inspector-title" className="font-serif text-2xl text-sand-100 sm:text-3xl flex items-center gap-2.5">
              <Binary className="text-cyan-400" size={26} aria-hidden="true" />
              <span>{isPl ? 'Interaktywny Inspektor Zapytań' : 'Interactive Pipeline Inspector'}</span>
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              {isPl
                ? 'Wybierz prawdziwe pytanie z siatki, aby prześwietlić jego wewnętrzny plan AST, kwerendy SQLite i dowód prawdy.'
                : 'Select a real query from the uniform grid to inspect its wire AST plan, SQLite queries, and ground truth proof.'}
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 self-start sm:self-auto rounded-sm border border-white/10 bg-obsidian-900 px-3 py-1 font-mono text-xs text-zinc-400">
            <Scale size={13} className="text-cyan-400" />
            Verified Case Bank
          </span>
        </div>

        {/* Question Selector Grid — UNIFORM ALIGNED GRID */}
        <div role="group" aria-label="Question examples" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUESTION_EXAMPLES.map((ex) => {
            const isSelected = ex.id === selectedExampleId;
            return (
              <button
                key={ex.id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setSelectedExampleId(ex.id)}
                className={cn(
                  'flex flex-col justify-between rounded-sm border p-4 text-left transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400 min-h-[140px]',
                  isSelected
                    ? 'border-emerald-400/60 bg-emerald-400/10 shadow-lg shadow-emerald-950/40 ring-1 ring-emerald-400/30'
                    : 'border-white/10 bg-obsidian-900/90 hover:border-white/20 hover:bg-obsidian-900 text-zinc-400'
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn('rounded px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider border truncate max-w-[120px]', ex.stageColor)}>
                      {ex.stageBadge}
                    </span>
                    <span className="font-mono text-[10px] text-zinc-500 shrink-0">{ex.latency}</span>
                  </div>
                  <p className={cn(
                    'mt-2.5 font-sans text-sm font-semibold leading-snug line-clamp-2',
                    isSelected ? 'text-sand-50' : 'text-sand-200'
                  )}>
                    "{isPl ? ex.questionPl : ex.questionEn}"
                  </p>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-white/5 pt-2 font-mono text-[10px] text-zinc-500">
                  <span className="truncate max-w-[110px]">{ex.mode}</span>
                  <span className={cn(
                    'font-bold shrink-0',
                    ex.verdict === true ? 'text-emerald-400' : ex.verdict === false ? 'text-rose-400' : 'text-amber-400'
                  )}>
                    {ex.verdict === true ? 'TRUE' : ex.verdict === false ? 'FALSE' : 'INVALID'}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Example Detail Card */}
        <div className="overflow-hidden rounded-md border border-white/10 bg-obsidian-900">
          {/* Card Top Banner */}
          <div className="flex flex-col gap-4 border-b border-white/10 bg-obsidian-950/60 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold border', currentExample.stageColor)}>
                  {currentExample.stageBadge}
                </span>
                <span className="font-mono text-xs text-zinc-400">{currentExample.mode}</span>
                <span className="font-mono text-xs text-zinc-600">&bull;</span>
                <span className="font-mono text-xs text-emerald-400">{currentExample.latency}</span>
              </div>
              <h3 className="mt-2 font-serif text-2xl text-sand-100">
                "{isPl ? currentExample.questionPl : currentExample.questionEn}"
              </h3>
            </div>

            {/* Verdict Box with Crisp Lucide Icons */}
            <div className="flex items-center gap-3 self-start rounded-sm border border-white/10 bg-obsidian-900 px-4 py-2.5 sm:self-auto">
              <div className="text-right">
                <span className="block font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  {isPl ? 'Wynik Prawdy' : 'Truth Verdict'}
                </span>
                <span
                  className={cn(
                    'font-mono text-base font-bold',
                    currentExample.verdict === true
                      ? 'text-emerald-400'
                      : currentExample.verdict === false
                      ? 'text-rose-400'
                      : 'text-amber-400'
                  )}
                >
                  {currentExample.verdict === true
                    ? 'TRUE'
                    : currentExample.verdict === false
                    ? 'FALSE'
                    : 'INVALID'}
                </span>
              </div>
              {currentExample.verdict === true && <CheckCircle2 size={24} className="text-emerald-400 shrink-0" />}
              {currentExample.verdict === false && <XCircle size={24} className="text-rose-400 shrink-0" />}
              {currentExample.verdict === null && <HelpCircle size={24} className="text-amber-400 shrink-0" />}
            </div>
          </div>

          {/* Sub-tab Navigation */}
          <div className="flex border-b border-white/10 bg-obsidian-950/30 px-5 text-xs font-mono">
            <button
              type="button"
              onClick={() => setActiveTab('ast')}
              className={cn(
                'flex items-center gap-2 border-b-2 py-3 px-3 transition-colors',
                activeTab === 'ast'
                  ? 'border-emerald-400 text-emerald-300 font-semibold'
                  : 'border-transparent text-zinc-400 hover:text-sand-100'
              )}
            >
              <Code2 size={14} />
              {isPl ? 'Drzewo AST (JSON)' : 'AST Wire Plan (JSON)'}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('sql')}
              className={cn(
                'flex items-center gap-2 border-b-2 py-3 px-3 transition-colors',
                activeTab === 'sql'
                  ? 'border-emerald-400 text-emerald-300 font-semibold'
                  : 'border-transparent text-zinc-400 hover:text-sand-100'
              )}
            >
              <Database size={14} />
              {isPl ? 'Kwerenda SQLite / Wektory' : 'Database Query / Facts'}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('details')}
              className={cn(
                'flex items-center gap-2 border-b-2 py-3 px-3 transition-colors',
                activeTab === 'details'
                  ? 'border-emerald-400 text-emerald-300 font-semibold'
                  : 'border-transparent text-zinc-400 hover:text-sand-100'
              )}
            >
              <Layers size={14} />
              {isPl ? 'Uzasadnienie & Audyt' : 'Explanation & Audit'}
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-5 sm:p-6">
            {activeTab === 'ast' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span className="font-mono">{isPl ? 'Sformalizowany Plan Wykonawczy (AST)' : 'Formal Abstract Syntax Tree (AST)'}</span>
                  <span className="font-mono text-emerald-400">Operator: {currentExample.operator}</span>
                </div>
                <pre className="overflow-x-auto rounded-sm border border-white/10 bg-obsidian-950 p-4 font-mono text-xs leading-relaxed text-sand-200">
                  <code>{currentExample.planJson}</code>
                </pre>
                <p className="text-xs leading-relaxed text-zinc-400">
                  {isPl ? currentExample.whyThisStagePl : currentExample.whyThisStageEn}
                </p>
              </div>
            )}

            {activeTab === 'sql' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span className="font-mono">{isPl ? 'Fizyczne Wykonanie na SQLite' : 'Physical Execution on SQLite / Vector Database'}</span>
                  <span className="font-mono text-indigo-400">{currentExample.targetEntity}</span>
                </div>
                <pre className="overflow-x-auto rounded-sm border border-white/10 bg-obsidian-950 p-4 font-mono text-xs leading-relaxed text-sand-200">
                  <code>{currentExample.sqlQuery}</code>
                </pre>
                <div className="rounded-sm border border-white/10 bg-obsidian-950/40 p-4">
                  <span className="block font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                    {isPl ? 'Fakt w Bazie Danych' : 'Extracted Factual Ground Truth'}
                  </span>
                  <p className="mt-1 text-sm font-medium text-sand-100">
                    {isPl ? currentExample.explanationPl : currentExample.explanationEn}
                  </p>
                </div>
              </div>
            )}

            {activeTab === 'details' && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-sm border border-white/10 bg-obsidian-950/60 p-4">
                  <span className="block font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                    {isPl ? 'Uzasadnienie Odpowiedzi' : 'Human-Readable Explanation'}
                  </span>
                  <p className="mt-2 text-sm text-sand-100">
                    {isPl ? currentExample.explanationPl : currentExample.explanationEn}
                  </p>
                </div>

                <div className="rounded-sm border border-white/10 bg-obsidian-950/60 p-4">
                  <span className="block font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                    {isPl ? 'Tag Audytowy Relacji' : 'Audit Relation Tag'}
                  </span>
                  <div className="mt-2 inline-flex items-center gap-2 rounded bg-white/5 px-2.5 py-1 font-mono text-xs text-emerald-300 border border-white/10">
                    <FileCode size={13} />
                    {currentExample.auditTag}
                  </div>
                  <p className="mt-3 text-xs text-zinc-500">
                    {isPl
                      ? 'Tag powiązany z pytaniem umożliwia graczom zgłaszanie spornych faktów bez ujawniania tajnego celu.'
                      : 'Audit tags permit post-game reporting and admin logging without ever exposing the secret target.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 4. AST Operators Grammar Reference */}
      <section aria-labelledby="operator-reference-title" className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 id="operator-reference-title" className="font-serif text-2xl text-sand-100 sm:text-3xl flex items-center gap-2.5">
              <Code2 className="text-amber-400" size={26} aria-hidden="true" />
              <span>{isPl ? 'Gramatyka Operatorów AST' : 'Formal AST Operator Specification'}</span>
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              {isPl
                ? 'Język pośredni, na który tłumaczona jest mowa potoczna przed wykonaniem w relacyjnej bazie wiedzy.'
                : 'The intermediate representation executed against our offline facts databases.'}
            </p>
          </div>
        </div>

        {/* Category Pills */}
        <div role="group" aria-label="Operator categories" className="flex flex-wrap gap-2 text-xs font-mono">
          {(['all', 'comparison', 'collection', 'spatial', 'string', 'logic'] as const).map((cat) => (
            <button
              key={cat}
              type="button"
              aria-pressed={operatorCategory === cat}
              onClick={() => setOperatorCategory(cat)}
              className={cn(
                'rounded-sm border px-3 py-1.5 uppercase tracking-wider transition-colors',
                operatorCategory === cat
                  ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-300 font-semibold'
                  : 'border-white/10 bg-obsidian-900 text-zinc-400 hover:border-white/20 hover:text-sand-100'
              )}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Operators Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {filteredOperators.map((op) => (
            <div key={op.name} className="flex flex-col justify-between rounded-sm border border-white/10 bg-obsidian-900 p-5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-emerald-400">{op.name}</span>
                  <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[10px] text-zinc-400 border border-white/10">
                    {op.category}
                  </span>
                </div>
                <div className="mt-2 font-mono text-xs text-zinc-400">{op.signature}</div>
                <p className="mt-3 text-xs leading-relaxed text-zinc-300">
                  {isPl ? op.descriptionPl : op.descriptionEn}
                </p>
              </div>

              <div className="mt-4 border-t border-white/10 pt-3">
                <span className="block font-mono text-[10px] uppercase text-zinc-500">
                  {isPl ? 'Przykład' : 'Example'}
                </span>
                <p className="mt-1 font-mono text-xs text-sand-200">{op.exampleEn}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 5. Facts Knowledge Base Matrix */}
      <section aria-labelledby="facts-matrix-title" className="space-y-6">
        <div>
          <h2 id="facts-matrix-title" className="font-serif text-2xl text-sand-100 sm:text-3xl flex items-center gap-2.5">
            <Database className="text-indigo-400" size={26} aria-hidden="true" />
            <span>{isPl ? 'Katalog Baz Wiedzy SQLite' : 'Offline Relational Facts Catalog'}</span>
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            {isPl
              ? 'Każdy tryb gry posiada odrębną, zoptymalizowaną bazę SQLite zawierającą zweryfikowane fakty geograficzne.'
              : 'Every game mode operates on dedicated, curated relational SQLite tables with indexed foreign keys.'}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-emerald-400">
                <Globe size={20} />
                <span className="font-mono text-xs">196 {isPl ? 'krajów' : 'countries'}</span>
              </div>
              <h3 className="mt-3 font-serif text-lg text-sand-100">country_facts.sqlite</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                {isPl
                  ? '16 tabel relacyjnych: kontynenty, granice, morza i oceany, stolice, waluty, języki urzędowe, unie historyczne (ZSRR, Jugosławia), ruch drogowy.'
                  : '16 relational tables: continents, borders, water bodies, capitals, currencies, languages, historical unions (USSR, Yugoslavia), driving sides.'}
              </p>
            </div>
            <div className="mt-4 font-mono text-[11px] text-zinc-500 border-t border-white/5 pt-3">
              Source: CIA Factbook &amp; RestCountries
            </div>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-cyan-400">
                <Compass size={20} />
                <span className="font-mono text-xs">50 {isPl ? 'stanów' : 'states'}</span>
              </div>
              <h3 className="mt-3 font-serif text-lg text-sand-100">us_state_facts.sqlite</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                {isPl
                  ? '8 tabel: granice stanowe i międzynarodowe, dostęp do Pacyfiku/Atlantyku/Wielkich Jezior, pasma górskie, autostrady międzystanowe (I-5, I-90), Wojna Secesyjna.'
                  : '8 tables: state/international borders, ocean access (Pacific, Atlantic, Great Lakes), mountain ranges, interstates, 13 colonies, Civil War side.'}
              </p>
            </div>
            <div className="mt-4 font-mono text-[11px] text-zinc-500 border-t border-white/5 pt-3">
              Source: US Census Bureau &amp; USGS
            </div>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-amber-400">
                <Layers size={20} />
                <span className="font-mono text-xs">16 {isPl ? 'województw' : 'voivodeships'}</span>
              </div>
              <h3 className="mt-3 font-serif text-lg text-sand-100">voivodeship_facts.sqlite</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                {isPl
                  ? '7 tabel: granice z krajami sąsiednimi, dostęp do Bałtyku, siedziby wojewody i sejmiku, główne rzeki (Wisła, Odra, Warta), etykiety makroregionalne.'
                  : '7 tables: neighboring country borders, Baltic coastline, dual capital seats, river courses (Wisła, Odra), macro-regional geographic tags.'}
              </p>
            </div>
            <div className="mt-4 font-mono text-[11px] text-zinc-500 border-t border-white/5 pt-3">
              Source: Główny Urząd Statystyczny (GUS)
            </div>
          </div>

          <div className="rounded-sm border border-white/10 bg-obsidian-900 p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-indigo-400">
                <Database size={20} />
                <span className="font-mono text-xs">380 {isPl ? 'powiatów' : 'counties'}</span>
              </div>
              <h3 className="mt-3 font-serif text-lg text-sand-100">powiat_facts.sqlite</h3>
              <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                {isPl
                  ? '6 tabel: status miasta na prawach powiatu, tablice rejestracyjne, granice z innymi województwami i państwami, siedziby władz powiatowych.'
                  : '6 tables: city vs land county flags, registration plate codes, neighboring voivodeship borders, international frontiers, seat cities.'}
              </p>
            </div>
            <div className="mt-4 font-mono text-[11px] text-zinc-500 border-t border-white/5 pt-3">
              Source: Rejestr TERYT &amp; MSWiA
            </div>
          </div>
        </div>
      </section>

      {/* 6. Why Zero Hallucinations? Engineering Deep-Dive (CRISP VECTOR SVG ICONS) */}
      <section aria-labelledby="zero-hallucination-title" className="space-y-6">
        <div>
          <h2 id="zero-hallucination-title" className="font-serif text-2xl text-sand-100 sm:text-3xl flex items-center gap-2.5">
            <ShieldCheck className="text-emerald-400" size={26} aria-hidden="true" />
            <span>{isPl ? 'Dlaczego Gwarantujemy 0% Halucynacji?' : 'Why Zero Hallucinations? The Architecture'}</span>
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            {isPl
              ? 'Kluczowa różnica architektoniczna między typowym chatbotem a silnikiem decyzyjnym Countrydle.'
              : 'The architectural contrast between conversational chatbots and Countrydle’s query engine.'}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Approach A: Typical Chatbot (Crisp Lucide X icons) */}
          <div className="rounded-sm border border-rose-500/20 bg-rose-500/[0.03] p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 font-mono text-xs font-semibold uppercase text-rose-400">
                <XCircle size={16} />
                {isPl ? 'Tradycyjny Chatbot LLM' : 'Standard Generative Chatbot'}
              </div>
              <h3 className="mt-3 font-serif text-xl text-sand-100">
                {isPl ? 'Model bezpośrednio wymyśla odpowiedź' : 'The Model Generates the Truth'}
              </h3>
              <ul className="mt-5 space-y-3.5 text-xs text-zinc-300">
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <X size={11} className="text-rose-400" />
                  </div>
                  <span>{isPl ? 'Wysokie ryzyko halucynacji faktów: odpowiedzi są zgadywane probabilistycznie przez losowanie kolejnych tokenów.' : 'High hallucination rate: answers are guessed probabilistically via stochastic token sampling.'}</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <X size={11} className="text-rose-400" />
                  </div>
                  <span>{isPl ? 'Niepowtarzalne wyniki: to samo pytanie zadane dwa razy może przynieść sprzeczne odpowiedzi.' : 'Non-deterministic: identical questions can yield contradictory answers across sessions.'}</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <X size={11} className="text-rose-400" />
                  </div>
                  <span>{isPl ? 'Brak weryfikowalności: gracz nie wie, czy AI pomyliło się w faktach geograficznych.' : 'Zero auditability: players have no guarantee whether the AI remembered facts correctly.'}</span>
                </li>
              </ul>
            </div>
            <div className="mt-6 font-mono text-[11px] text-rose-400/80 border-t border-rose-500/20 pt-3">
              Unreliable for trivia deduction games
            </div>
          </div>

          {/* Approach B: Countrydle Pipeline (Crisp Lucide Check icons) */}
          <div className="rounded-sm border border-emerald-500/30 bg-emerald-500/[0.04] p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 font-mono text-xs font-semibold uppercase text-emerald-400">
                <CheckCircle2 size={16} />
                {isPl ? 'Podejście Countrydle' : 'Countrydle Hybrid Pipeline'}
              </div>
              <h3 className="mt-3 font-serif text-xl text-emerald-200">
                {isPl ? 'Model jest tylko parserem, baza liczy prawdę' : 'The Model is Only a Parser; Database Computes Truth'}
              </h3>
              <ul className="mt-5 space-y-3.5 text-xs text-zinc-300">
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <Check size={11} className="text-emerald-400 font-bold" />
                  </div>
                  <span>{isPl ? '0.0% halucynacji faktów lokalnych: odpowiedź wynika bezpośrednio z relacyjnych kwerend w bazie SQLite.' : '0.0% local hallucination: ground truth is evaluated mathematically by relational SQLite queries.'}</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <Check size={11} className="text-emerald-400 font-bold" />
                  </div>
                  <span>{isPl ? 'Poniżej 1 ms dla popularnych zapytań: szablony kompilują drzewo bez udziału zewnętrznej sieci.' : 'Sub-millisecond latency: regex compilers resolve common templates instantly in RAM.'}</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <div className="h-4 w-4 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <Check size={11} className="text-emerald-400 font-bold" />
                  </div>
                  <span>{isPl ? 'Pełna weryfikowalność: każde zapytanie generuje dowód tekstowy i permanentny tag relacji do audytu.' : 'Complete audit trail: every answer provides an exact human proof and audit relation tag.'}</span>
                </li>
              </ul>
            </div>
            <div className="mt-6 font-mono text-[11px] text-emerald-400 border-t border-emerald-500/20 pt-3">
              Deterministic &bull; Verifiable &bull; Zero Hallucination
            </div>
          </div>
        </div>
      </section>

      {/* 7. Footer CTA / Navigation */}
      <footer className="rounded-sm border border-white/10 bg-obsidian-900 p-8 text-center sm:text-left flex flex-col sm:flex-row items-center justify-between gap-6">
        <div>
          <h3 className="font-serif text-xl text-sand-100">
            {isPl ? 'Chcesz przetestować ten silnik w praktyce?' : 'Ready to Test the Engine in Practice?'}
          </h3>
          <p className="mt-1 text-xs text-zinc-400">
            {isPl
              ? 'Wróć do gry, zadaj pytanie i sprawdź, jak precyzyjnie reaguje na Twoje teorie.'
              : 'Return to the game, ask any geographic question, and observe the instant factual feedback.'}
          </p>
        </div>
        <div className="flex gap-3">
          <a
            href="/game"
            className="inline-flex items-center gap-2 rounded-sm bg-emerald-400 px-4 py-2 text-xs font-semibold text-obsidian-950 transition-colors hover:bg-emerald-300"
          >
            {isPl ? 'Zagraj w Countrydle' : 'Play Countrydle'}
            <ArrowRight size={14} />
          </a>
        </div>
      </footer>
    </div>
  );
}
