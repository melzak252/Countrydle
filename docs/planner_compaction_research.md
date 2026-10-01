# Countrydle planner compaction: research, local cutover, and measured limits

Research date: 2026-10-01. Scope: Task 08 and Task 12's relation-growth design. Worktree: `Countrydle-planner-compaction`; branch: `feature/planner-compaction`; unchanged baseline: `01fb383` (application version 1.19.0). Original research runs made no production writes, template edits, fact assignments, database-schema change, or executor change. The user subsequently approved publishing and production adoption of the selected setup; release preparation targets **1.19.1** from the existing production baseline, without merging or deploying the unrelated 1.20.0 work on `main`.

## Decision and result

Keep one complete, manually compacted prompt and the existing typed AST. The local candidate is `compact-v5-t1024`: full relation inventory, existing model/schema/operators/executor, original 1,024-token thinking budget and 2,048-token output ceiling. The prompt now describes each relation's type/meaning once, keeps difficult semantic safeguards, and preserves a few contrastive AST examples. No extra classifier, dynamic schema pruning, second planner call, or output truncation shortcut.

**Input compaction works; the requested cost/latency targets do not hold for the safe candidate.** Final prospective input decreased **39.2%**, below the approximate 50% target. The hypothetical all-input-uncached planner charge decreased **20.9%**, below 30%. On 19 same-question provider-warm pairs, the rate-model charge was **0.57% higher**, essentially flat rather than a saving. The conservative candidate used more thought tokens. Mean planning remained **2.86s**, not below one second. Do not release this branch as a demonstrated paid-cost or latency optimization. It is a locally exercised precision/scalability candidate and reproducible evidence for the next decision.

The final 20 unexposed EN/PL stress questions had correct meaning/routing **20/20**, versus **15/20** for the unchanged baseline. That is limited curated evidence, not a guarantee or production accuracy estimate. A separate post-tuning 30-case regression retained one pre-existing organization-alias execution failure (`African Union` versus `AU`); no claim of universal precision.

## Implementation boundaries

- `server/countrydle/local_planner.py`: one compact, complete inventory based on existing `SUPPORTED_RELATIONS` and `LIST_RELATION_QUERIES`; concise per-relation meanings; strict route distinction; clause/negation/quantifier/bound preservation; identity-versus-text spelling; named-country references; point/territory and compass-axis distinctions; Christianity umbrella versus denomination; present/past membership; clear false propositions remain valid; children-before-parent node indexing.
- Cache identity is now `26:countrydle:compact-v5-t1024:<configured-model>`, rather than `26:<configured-model>`. This bumps Countrydle's effective interpretation contract without invalidating unrelated game-mode caches or changing normalization. Shared AST ABI `PLANNER_VERSION=26` is intentionally unchanged. Every cached plan still executes against current target facts.
- Model stays `gemini-2.5-flash-lite`; temperature zero; total-output ceiling 2,048; shared thinking budget 1,024. Country-only budget scaffolding was removed after unsafe lower-budget trials. Other modes' generation settings are unchanged.
- `server/scripts/benchmark_country_planner.py`: opt-in live comparison, cache bypass, strict errors, raw usage/plan capture, route and meaning/denotation evaluation over all 196 country rows, provider-free gold validation, read-only private SQLite backups, no gameplay writes. It rejects output collisions with protected inputs including hard links. It does not repair provider plans or retry failed generations.
- Permanent regressions exercise consumer-visible stale-plan rejection and benchmark protected-input safety. No prompt-wording or source-string tests were added. Existing contract/local-answering/cache/other-mode/fallback suites remain applicable.

## Evaluation protocol and leakage accounting

The initial corpus contained 80 curated cases: 53 development and 27 held out before tuning. Cases cover EN/PL fragments/typos, negation/Boolean scopes, numeric bounds, names/identities, named comparisons, quantifiers, clarification, and valid unsupported predicates. Labels were authored rather than copied from the old model. Two development wordings/gold interpretations were corrected/rechecked; those extra provider calls are not silently removed from historical experiment accounting, but the final development table has 53 unique cases. The original held-out results exposed errors; any later rerun of those cases is **regression evidence, not a blind holdout**.

Additional independently authored, provider-free prospective corpora had 32 and 30 cases, followed by another independently authored 30-case release corpus. Parents reviewed/fixed gold syntax, a missing guard value, ordinary Christianity scope, and ambiguous continent-versus-region cases before first generation where applicable. Once their outputs informed prompt corrections, those corpora ceased to be blind. The final 20-case set was authored/frozen before any generation of its wordings at `compact-v5-t1024`; 10 EN/10 PL. Its source hash and unchanged gold are recorded below. Semantic families overlap earlier work: this is prospective wording/stress validation, **not a disjoint-family or production-frequency benchmark**.

Both final arms use the same model, temperature, schema, operators, 1,024 thinking, 2,048 output, private read-only fact snapshot and one call per case, `use_cache=False`, two workers. Provider model version returned `gemini-2.5-flash-lite`. Fact-source SHA-256: `521524dd261997793fa4af777709f0eb2d2d50945bae0184070788f6d03f200e`. No forced provider-cold cohort was available. Positive numeric cached-token metadata defines observed provider-warm; absent metadata is unknown, not zero. Application-cache reuse is measured separately through the real API smoke.

Means are arithmetic; p95 is nearest rank (`ceil(.95*n)`). Planning time includes the provider call and planner parsing/compilation. The benchmark's execution time covers evaluation of **196 possible targets**, not one API request. Latencies are descriptive single-run values; live concurrency/provider variation prevents a latency SLA or causal speedup claim. Gold combines full graph, scope/binding/bounds, guard atoms and all-target denotation. Guards are structural aids, not semantic proof; accepted equivalent aliases/Boolean forms require source-backed adjudication.

### Frozen corpora

| File under `server/tests/` | Cases | SHA-256 |
|---|---:|---|
| `country_planner_benchmark.json` | 80 | `69d3e25191a6ad87d2870278cc79514eab30f0af9103c16b6af9be444039209c` |
| `country_planner_prospective.json` | 32 | `ec6032dd29765cd9d9f4c150ae7c1f3b7257b9309a3bf868ef9fc24d0144bb11` |
| `country_planner_acceptance.json` | 30 | `60157bc8a8df0c557a6808d83c855339edea59c699b345c03113d4e6ad570a19` |
| `country_planner_release.json` | 30 | `2aad0e1c9c329c3437c6fe611fc0d0ac437db8a49c52551a0bdeb046c531ca45` |
| `country_planner_final.json` | 20 | `7ed1fbf664e8410a41085a60b63dde628d0cea2dab8c9ad0dc2333c459267a70` |

The 32-case prospective run is retained as an experiment, not as final candidate validation. Its old compact result had six raw semantic failures versus four baseline, including a real named-direction self-reference error. `all(not island)` versus `not(any island)` was equivalent; regional Africa versus physical continent was disputed for Spain; Oceania region/continent matched all 196 rows but differed structurally. These were not hidden by equating JSON validity with accuracy.

### Final prospective comparison: 20 cases per arm

| Measure | Unchanged baseline | Compact-v5-t1024 |
|---|---:|---:|
| Provider calls / app-cache hits | 20 / 0 | 20 / 0 |
| Input tokens, mean / p95 | 7,143.35 / 7,151 | 4,344.35 / 4,352 |
| Cached-input tokens, mean / p95 (observed denominator) | 6,343.30 / 6,823 (20/20) | 3,929.21 / 3,932 (19/20) |
| Candidate output tokens, mean / p95 | 107.15 / 204 | 133.85 / 311 |
| Thought tokens, mean / p95 | 586.50 / 950 | 740.45 / 868 |
| Planning latency, mean / p95 | 2,365.33ms / 3,743.93ms | 2,862.62ms / 3,621.49ms |
| Correct meaning and route | 15/20 | 20/20 |
| Route distribution local / fallback / clarify | 15 / 4 / 1 | 15 / 4 / 1 |
| Route mismatches | 4 | 0 |
| Local plans with no verified result for any target | 2 | 0 |
| Malformed/truncated plans | 0 | 0 |
| HTTP/provider errors / automatic planner retries | 0 / 0 | 0 / 0 |
| Full-input-uncached cost counterfactual / 1,000 attempted calls | $0.991795 | $0.784155 |
| Whole-cohort usage-derived charge / 1,000 calls | $0.420898 (complete) | $0.428682–$0.448208 (one cache count unknown) |

Baseline errors were present Soviet membership sent to fallback (two), Christianity interpreted as the literal stored `Christianity` only, official-name spelling treated as common-name spelling, and historical EU membership forced into unsupported `historical_union`. Actual current answers and routing matched gold; all clauses and bindings were inspected through the saved plans/denotations. The two baseline no-result local plans are not HTTP exceptions.

### Post-tuning regression evidence and remaining error

Final original 80: no route/malformed/execution failures; three guard-only adjudications, accepted after source inspection and zero all-target mismatches: North/South America is normalized from regional to continent coverage (`local_answering.py:1650-1653`); North Africa aliases Northern Africa; a numeric-meridian `east_of`/`greater_than` is equivalent when there is no named-country self-reference. Final release 30: no semantic, routing, malformed or execution failures. Final acceptance 30: 29 correct, one pre-existing failure. Together these are 159/160 observed cases after adjudication, but 140 were exposed/tuned and must not be advertised as independent accuracy.

Remaining acceptance case: north of Senegal AND African Union member AND not island. Both baseline and final can emit membership literal `African Union`, yielding nine gold-relative mismatches, rather than `AU`. `ORG_ALIASES` already defines the name/code mapping, but the AST `contains` path uses generic normalized equality for membership (`local_answering.py:1478-1508`), unlike its currency-specific path. This is pre-existing executor alias handling, intentionally unchanged by Task 08. The compact prompt requests short organization codes; this does not guarantee model compliance. It is a concrete precision limit, not hidden by a narrowed benchmark.

## Thinking/output experiments: rejected shortcuts

Prompt-only development comparisons initially held settings fixed at 1,024 thinking. An earlier compact candidate had 3,742 mean input tokens versus 7,140 baseline (-47.6%); its thoughts rose from 422 to 580, and mean planning slowed from 2.03s to 2.50s. All-input-uncached estimated cost was $0.927 to $0.651 per 1,000 (-29.8%). These are development results from an earlier prompt, not the final version.

Then the same earlier compact prompt was evaluated at 512 and zero thinking. At 512: mean 1.76s, p95 2.46s, 348 mean thoughts, no initial development semantic failures after alias adjudication. Prospective cases subsequently exposed a repeated negated-`any` self-reference, wrong clarification of a supported cultural-label fallback, named compass replaced by plain numeric comparison, and current membership classified invalid. Repeating two observed failures three times each reproduced six failures; the apparently clean development score was insufficient. The compiler safely rejected invalid references; falling back can cost another call and is not equivalent to correct interpretation.

At zero thinking, mean was 0.914s and p95 1.159s, but six development meanings were wrong. Thought metadata was absent on most calls, so a complete priced population was unavailable. It was rejected, not chosen to hit the one-second aspiration.

The final prompt restores semantic safeguards, including umbrella-religion examples, reference operands, type/axis rules, quoted literals, exact currency codes, tree index ordering, and validity independent of proposition truth. **Default thinking remains 1,024.** The total-output ceiling stays 2,048 to retain compound-plan headroom. No truncation/repair/retry shortcut was introduced.

## Price accounting, cache regimes, and gameplay projection

Rates are Gemini 2.5 Flash-Lite Standard paid list rates: input $0.10/M, cached input $0.01/M, output including thoughts $0.40/M [9]. Charges are a rate-model calculation, not an invoice; free tier, credits, taxes, other pricing tiers/storage and downstream calls are excluded.

`USD = ((I-C)*0.10 + C*0.01 + (O+T)*0.40) / 1,000,000`.

For the final cohort, baseline all 20 costs total $0.00841796. Current 19 observed costs total $0.00815225; one omitted cache count makes all-20 cost $0.00857364–$0.00896415 depending on whether its input was entirely cached or uncached. The interval is **1.85%–6.49% higher than this baseline cohort**, not a >=30% saving. The same-question observed-warm pairs (n=19) total $0.00810627 baseline versus $0.00815225 current: per 1,000 **$0.426646 versus $0.429066**, +0.57%. Per-call p95 charge is $0.00094506 versus $0.00055292. Partial provider hits remain in this cohort; “warm” does not mean identical cached fractions. Missing fields never count as free/zero-cache calls.

No explicit known-zero provider-cache calls were observed in the final cohort. “Cold” values in the table are therefore **counterfactual all-input-full-price**, not measured cold behavior. The Google token counter counted prompt-only and exact full-generation requests identically for the three illustrative pairs; this does not establish a schema/config token contribution of zero. Actual generated usage is authoritative for these calls [10]. Provider implicit cache has no guaranteed discount and is independent of app plan-cache hits [11].

At **5,000 attempted questions**, assume template coverage is unchanged/zero in this isolated projection and an app interpretation-cache hit bypasses the planner; paid planner invocations `N=5,000*(1-h)`. These are conditional **planner-only** projections, not production traffic/site savings:

| Assumed application-cache hit rate | Paid planner calls | Full-input-uncached counterfactual old → compact | Matched observed-warm rate old → compact |
|---|---:|---:|---:|
| 0% | 5,000 | $4.959 → $3.921 (save $1.038) | $2.133 → $2.145 (increase $0.012) |
| 50% | 2,500 | $2.479 → $1.960 (save $0.519) | $1.067 → $1.073 (increase $0.006) |
| 90% | 500 | $0.496 → $0.392 (save $0.104) | $0.213 → $0.215 (increase $0.001) |

The historical 365/382 local-KB answers are routing, not a measured cache-hit rate. Do not infer `h` from them or multiply unobserved template/app/provider-cache percentages. Hosting, scheduled blog generation and unrelated models are separate.

Final route counts are equal but question identities differ: the compact planner replaces incorrect temporal fallbacks with local answers and incorrect name/history local plans with honest fallback. The harness measures only planning, not every downstream fallback's bill. Malformed volume did not increase in the final comparison (0 both); automatic planner retries were 0. Any total question-resolution claim must add observed embedding, retrieval/answer-model and fallback retry costs per question. The actual smoke exercised one correct fallback but does not estimate a population fallback-cost distribution. No unpriced additional call is treated as free.

## Real local API verification

Actual FastAPI routes were exercised through `httpx.ASGITransport`, real live providers, the real cache implementation stored in a private temp SQLite file, an independent fact copy, and a disposable PostgreSQL database on port 55321. No mocked or overridden application dependency; lifespan was intentionally skipped to avoid migrations/schedulers/other startup writes. This is actual route behavior, not a TCP/network or browser latency measurement.

- Seeded a deliberately false plan under the old effective version. First compound Polish question returned true with exactly one new-version cache miss; exact and normalized repeats returned true and each added one cache hit. First API wall time 3,391.9ms; repeated 9.7ms and normalized 12.6ms. Continental Europe reused the interpretation correctly.
- A conjunction with a true border predicate and false population predicate returned false, preserving all clauses. Catholic Poland satisfied the broad Christianity predicate.
- An underspecified importance question returned invalid/clarification without any stored row or turn.
- “Did the country host the 2014 FIFA World Cup?” remained valid, entered real fallback, returned false for Poland, and consumed exactly one turn. Embedding and Gemini calls were live. Qdrant retrieval and auxiliary indexing failed with a hostname-resolution error; the existing fallback/general-knowledge path succeeded and the accepted row stayed committed. This does not verify full vector retrieval.
- An unreviewed/fictitious target missing local facts remained unanswered, with no row or turn. Continental's existing unresolved formatter returns HTTP 200, `valid=false`, no answer; this shape was recorded rather than demanding a fabricated boolean or changing the existing contract.
- Final guest accounting: six Countrydle accepted booleans and one Continental Europe question; counters equaled stored histories. Clarification and unknown answers consumed zero. Pre-end Countrydle/Europe state omitted the answer target. The enforced secrecy boundary is state responses; factual question explanations may name countries under the existing contract, so broader spoiler secrecy is not claimed.

Affected regression suites: **292 passed, two existing warnings** (Python `crypt` deprecation and unavailable Qdrant compatibility lookup). Suites: `test_planner_contract.py`, `test_countrydle_local_kb.py`, `test_plan_cache.py`, `test_local_kb_other_modes.py`, `test_countrydle_fallback.py`, `test_benchmark_country_planner.py`. Targeted hard-link output-collision regression failed before protection and passed afterward; targeted stale-interpretation test passed. No claim of the entire unrelated backend/integration/UI suite.

## Relation growth without prompt bloat: measured design, not facts

The current prompt lists 22 relations; its response enum has 24 names including existing legacy region/subregion aliases. A **design-only** addition of one list relation `cultural_group`, one response relation enum name, and a brief coverage-aware replacement for the current blanket cultural fallback changed the actual token-counter result by **six tokens** on each of three questions:

| CountTokens sample | Current | Design-only cultural relation |
|---|---:|---:|
| English simple geography | 4,337 | 4,343 |
| Polish quantified neighbor | 4,343 | 4,349 |
| English named-reference compound | 4,349 | 4,355 |

Prompt-only and full-request counter forms returned the same counts. No future-feature generation, executor or facts were implemented, so real schema steering/billed delta remains unverified. The small **net** delta replaces obsolete “unsupported culture” prose rather than appending whole taxonomies; it is not six tokens per arbitrary future relation.

Proposed semantics: one multi-valued country-cultural-association relation, not one boolean per category; category names are data values, not relation/schema enum members; country assignments, long definitions, sources and aliases remain in SQLite. Keep explicit cultural-country association distinct from resident ethnicity/identity, minority presence, language family, official-language status/prevalence, religion and region. Ordinary Nordic/Scandinavian geographic shorthand remains geographic; an explicitly cultural predicate cannot use geography as proof.

The executor—not a planner with no coverage manifest—must resolve recognized category aliases and reviewed coverage. A positive association can be known from a reviewed record. A negative needs complete reviewed category/target coverage. Unreviewed, disputed, missing or unknown category is `None`, and negation keeps it unknown. The current generic list-membership implementation must **not** simply treat a missing cultural row as false. A future category-specific `contains` resolver can check definition/version, category and coverage without changing the AST; list-wide existence or quantification needs a separately defined complete universe. Falling back must preserve the adopted meaning, not silently replace a game definition with language-family evidence.

Net contribution requires actual correctly avoided answer calls:

`Net USD = sum(avoided fallback charges) - N_paid_planner * delta_input_tokens * ((1-c)*p_input + c*p_cached) - delta_output_thought_retry_charges - local_operating_cost`.

The six-token counter delta alone would be $0.0000006 per full-price input call, or $0.003 for 5,000 paid calls; this is illustrative input-only arithmetic, **not a net savings forecast**. Fallback demand, correct-coverage rate, provider/app-cache distribution and added output/thought usage are unknown. Historical three-observation fallback charges are not a stable mean. A reviewed game-specific cultural definition, primary sources, positive/negative/unknown coverage and privacy-safe demand data are prerequisites. No Slavic-country classification or cultural facts were invented.

## Evidence files and reproduction

Raw local results are in `/tmp/countrydle-planner-results/`, including `baseline-development-final.json`, `heldout-prompt-only.json`, `prospective-final-comparison.json`, `final-acceptance-comparison.json`, `final-release-comparison.json`, `final-original.json`, `final-acceptance.json`, `final-release.json`, `final-prospective-comparison.json`, `final-api-smoke.json`, `final-token-counts.json`, and frozen manifests. Earlier snapshots are explicitly intermediate, not final candidate metrics. The benchmark tool/corpora and this report remain in the worktree; throwaway counter/API scripts and disposable service are cleaned after proof.

From `server/`:

```bash
python scripts/benchmark_country_planner.py --corpus tests/country_planner_final.json --validate-only --output /tmp/planner-gold.json
python scripts/benchmark_country_planner.py --corpus tests/country_planner_final.json --variant both --baseline-planner /path/to/unchanged/local_planner.py --env-file /path/to/local/.env --output /tmp/planner-comparison.json
python -m pytest -q tests/test_planner_contract.py tests/test_countrydle_local_kb.py tests/test_plan_cache.py tests/test_local_kb_other_modes.py tests/test_countrydle_fallback.py tests/test_benchmark_country_planner.py
```

Provide real local fact data and test-safe application env configuration; the live comparison reads provider credentials from the explicitly selected `.env` without printing/copying them. `--validate-only` performs no provider generation. Live runs incur real charges. Baseline must be a captured unchanged source file in an importable package-depth path. Compare exact model/settings, semantics and priced denominators, not prompt characters or a successful AST alone.

## What this means for the one-second and cost objectives

The full-catalogue design is suitable for controlled relation growth and improved precision, but input compaction is **not** the main paid saving once provider input is mostly cached. Thought/output cost and avoided calls matter more. Do not swap in the unsafe lower thinking budget or prune relations to obtain a flattering timing/cost number. Existing app-cache reuse was under one second in the local smoke; the independently owned safe-template path is the other deterministic no-model path. Their production coverage/hit distribution must be measured, not assumed. No extra router/retry/validation model is justified by this experiment.

A release decision should therefore treat this branch as local research/precision work, not a proven cost cutover. Further cost work must demonstrate stable semantic behavior at a lower thought cost and include production-like provider-cache/downstream-call accounting; cultural coverage requires its missing semantic/source prerequisites first.

## Follow-up comparison: prompt examples and thinking budgets

The follow-up evaluated eight configurations over 200 curated questions each: 160 existing regression questions and 40 newly frozen wordings (20 EN / 20 PL), using the actual Gemini provider and unchanged all-country executor. The final comparison matrix comprises 1,600 generations, with additional superseded experiments retained separately. Application-cache lookup was bypassed. Prior 0/1,024-budget control measurements were reused for existing cases; the trials were not simultaneous randomized pairs.

`current` is the deployed-candidate compact prompt; `examples-v2` adds semantic examples and corrects a false De Morgan sentence found in its superseded v1. The v2 prompt correction followed exposure to current-prompt holdout results, so its 40-question evaluation is reused-holdout evidence, not a new untouched holdout. Semantic families overlap previous evaluation; these percentages are not production accuracy.

| Prompt / thinking budget | Correct / 200 | Mean / p95 planning | Mean input tokens | USD / 1,000 common observed-warm calls | USD / 1,000 full-price-input calls (counterfactual) | New known failures vs current-1024 |
|---|---:|---:|---:|---:|---:|---:|
| current / 0 | 160 | 0.948s / 1.319s | 4,343 | $0.140612 | $0.496703 | 38 |
| current / 512 | 189 | 1.750s / 2.285s | 4,343 | $0.269742 | $0.625915 | 9 |
| current / 768 | 190 | 2.383s / 3.197s | 4,343 | $0.370692 | $0.720741 | 8 |
| **current / 1024 (selected)** | **196** | **2.364s / 3.418s** | **4,343** | **$0.368483** | **$0.721037** | **0 (control)** |
| examples-v2 / 0 | 172 | 0.872s / 1.222s | 4,859 | $0.121119 | $0.547303 | 26 |
| examples-v2 / 512 | 191 | 1.904s / 2.436s | 4,859 | $0.246434 | $0.673149 | 7 |
| examples-v2 / 768 | 191 | 2.269s / 3.257s | 4,859 | $0.340675 | $0.757855 | 7 |
| examples-v2 / 1024 | 196 | 2.364s / 3.712s | 4,859 | $0.322005 | $0.745901 | 2 |

Warm prices use the same 88 questions with positive cached-input metadata for every configuration, including errors rather than deleting their charges. A separate intersection has 62 cases correct under every configuration. Full-price-input prices are all-200 counterfactuals, not observed cold-cache charges. Provider total-output usage was reconciled as `totalTokenCount - promptTokenCount`, including thoughts omitted as a separate metadata field. Downstream fallback costs remain outside these estimates.

**Selection: retain `compact-v5-t1024`, not a new smaller model or a lower thinking budget.** The examples-v2/1,024 variant ties 196/200 but introduces a missing-criterion routing error and malformed XOR while fixing other cases: equal aggregate score is not a no-regression result. The examples-v2/768 run also contained one `MAX_TOKENS` response near the 2,048-token ceiling. No output-ceiling reduction, planner repair, or extra retry was adopted.

The selected control's four observed failures are the existing African Union alias mismatch, a negated border-name interpretation that differs for Germany, and two ambiguous north-direction questions routed local instead of clarification. This release does not claim to fix them. Typed relation/item metadata and a simpler model-facing representation remain an unmeasured hypothesis, not shipped functionality.

For **1,000 full games × 10 questions**, an assumed **60% combined whole-question template / application-plan-cache bypass** leaves 4,000 paid planner calls. Selected-control planner cost is **$1.473930** at the common observed-warm rate, or **$2.884146** under the full-price-input counterfactual. Both exclude fallback, embeddings, hosting, retries, taxes and other models. The 60% bypass and benchmark token mix are assumptions, not measured production coverage.

Follow-up source files: `/tmp/countrydle-planner-balance/comparison-summary.json`, `selection-evidence.json`, `experiment-provenance.json`, and frozen `holdout.json` (SHA-256 `9020f8efea7427cc6df3547f2132667801630a6ad051ee8d44be945f8ae83a51`). The original reproducible harness/corpora remain committed with this report; intermediate examples prompts are not part of the production setup.

## Approved release configuration

- Release: **1.19.1**, isolated from unreleased `main` changes; branch `feature/planner-compaction`.
- Local model: **`gemini-2.5-flash-lite`**; temperature **0**; thinking budget **1,024**; total-output ceiling **2,048**.
- Countrydle revision: **`compact-v5-t1024`**; effective cache identity **`26:countrydle:compact-v5-t1024:gemini-2.5-flash-lite`**.
- Shared AST, executor, relations, fact databases, template behavior and other modes' prompt/cache versions remain unchanged.
- Existing production image-digest pinning, environment, proxy trust and data volumes must be preserved. Release deployment evidence is recorded only after live verification.

### Release preflight verification

The 1.19.1 release preflight passed **305 tests** covering the planner contract, Countrydle local answering, cache cutover, other-mode local answering, fallback, benchmark input safety and patch-note publication. Two warnings remained: pytest's already-imported `anyio` rewrite warning and unavailable local Qdrant compatibility lookup. Tests used an isolated temporary plan cache and a non-production database URL.

A fresh live-provider rerun of the 20-question final corpus had **zero route mismatches, malformed plans, semantic failures or executor failures**, with 15 local answers and five correct non-local routes. Mean/p95 planning was **2.964s / 3.812s**; mean input was **4,344.35 tokens**. Positive provider-cache metadata was present on only **5/20** calls; the other 15 were unknown, so no full-cohort actual charge or cold-cache claim is made. Evidence: `/tmp/countrydle-planner-release-live.json`.

The release manifest passed `python -m scripts.publish_patch_notes --check`. Frontend typecheck, production build and 46-route prerender passed on **Node 22.23.3**; the existing large-bundle warning remained. Production adoption and public release-note publication are separate from these preflight results.


---

## Research basis

## Decision

Keep the current one-call planner architecture and compact the fixed prompt by hand. The target design is one complete, compact catalogue of supported relations, a stable semantic core, and the existing typed, constrained plan representation. Each relation should have one canonical identifier and concise meaning/type metadata; derive both the prompt inventory and JSON-schema enum from that registry. Keep every supported relation visible to the planner, including for mixed-domain questions. Do not add an LLM router or dynamically remove relations from the schema. Preserve accuracy gates above input-token reduction.

This recommendation is an architectural inference, not a result proved by the cited benchmarks. Research on semantic parsing identifies schema encoding and question-to-schema alignment as distinct challenges [1], and schema linking has been found important in text-to-SQL [2]. Those findings support clear, consistent relation naming and evaluation of relation linking; they do not establish that selective retrieval is worthwhile for Countrydle’s compact catalogue. LinkAlign studies very large, multi-database schema pools and more involved retrieval/grounding [3]. That is a different scale and its omission risk is particularly concerning where one question can join multiple domains. If catalogue growth later makes the full inventory materially expensive, first benchmark deterministic retrieval of *supplemental descriptions or examples* while retaining the complete relation/operator inventory. Any design that hides a supported relation must prove recall against every gold-required relation, including mixed questions.

The typed constrained AST is useful as a boundary: it can constrain relation names, operators, tree shape and bindings, then let deterministic local code compile and execute a plan. It cannot prove that the selected relation, polarity, scope or threshold expresses the user’s question. Google explicitly cautions that structured output guarantees syntactically correct JSON, “it does not guarantee the values are semantically correct” [4]. The logical-parsing study likewise notes that “semantic errors not captured by Context-Free Grammars continue to pose challenges” [5]. Keep structure validation and semantic evaluation separate. Do not prune the schema aggressively to make output smaller: a structurally valid plan over an incomplete choice set can still be wrong.

## What the compact semantic core must preserve

Compact prose should retain distinctions that alter truth conditions, not duplicate every implementation detail. At minimum, preserve: local versus clarify versus fallback (unsupported facts/operators are not vagueness); all stated conditions and polarity; Boolean connective and negation scope; `any`/`all` binding to list items rather than list existence; strict versus inclusive bounds and every supplied bound; and distinct meanings for cultural group, official language, language family/prevalence, minority, region, religion and political membership. Geographic extent must also remain explicit: a coordinate point, a country crossing a line, territory north of a line, and an entire country north of it are not interchangeable.

These are semantic safeguards, not claims of measured performance. Existing planner rules include examples such as “Neither A nor B” as `not(or(A, B))`, distinguishing it from `not(and(A, B))`. The 2025 constrained-decoding paper finds grammar constraints and in-context examples complementary in its tested logical parsing tasks [5]. That supports testing a few concise contrastive examples, not replacing the core or assuming examples improve this app. Compression research also cautions that task and context length matter: one broad prompt-compression study reports that “All methods result in some degree of increased hallucination” [6]. LongLLMLingua reports speedups for roughly 10k-token long-context inputs at 2–6x compression, with a compression stage [7]; those results do not justify dynamic compression of this short, fixed planner contract. Prefer manual removal of repetition and measure end-to-end before considering compressor overhead.

## Relations, cultural data and unknowns

For future sourced cultural coverage, follow Task 12’s requirement for one compact multi-valued relation (provisionally `cultural_group`) where justified, with categories as data values—not one boolean relation per group, prompt paragraphs, or country lists in the prompt. Keep category definitions, aliases, memberships, provenance and coverage in SQLite/local code. Distinguish genuinely different facts: a cultural classification is not official-language status, a language-family claim, regional location, religion, organization membership, minority presence or population prevalence. Add a distinct relation only when the proposition and sourced data model require it. This recommendation is grounded in Task 12’s design contract, not external validation of any cultural taxonomy; no new classification or country facts are proposed here.

Coverage must be explicit and versioned with source provenance and the adopted definition. A positive association is true when supported; a negative answer requires reviewed, complete coverage for the category and target. Missing, unreviewed or disputed information is unknown, not false. Under negation, unknown remains unknown; it must not become true merely by applying `not` to a missing row. PostgreSQL documents three-valued logic: “true, false, and `null`, which represents ‘unknown’” [8]. That is a useful semantic reference, not evidence that Countrydle currently implements SQL NULL propagation. The executor’s lookup and Boolean semantics must be independently inspected and tested before implementation. Unknown or unsupported qualifiers should retain fallback/clarification behavior rather than be coerced into a negative membership result.

## Costs, caching, thinking and latency

For Google Gemini 2.5 Flash-Lite Standard paid usage, current documented rates are $0.10 per million ordinary text input tokens, $0.01 per million cached input tokens, and $0.40 per million output tokens including thinking [9]. Given usage metadata `I` (input), `C` (cached input), `O` (candidate output), and `T` (thought tokens), estimate a priced call as `((I-C)*0.10 + C*0.01 + (O+T)*0.40) / 1,000,000` USD. Apply this to each response with usage; report failed calls without usage as unpriced, not free or automatically billed at an assumed amount. Count the actual full request where supported, but use post-generation provider usage as the observed consumption: Google says `count_tokens` is input-only and response usage carries generated/thought/cached usage [10].

Separate provider prompt caching from the application’s plan/answer cache. Google says implicit caching is enabled for Gemini 2.5+ but offers “no cost saving guarantee”; its published minimum table lists Gemini 2.5 Flash and Pro but omits Flash-Lite [11]. Do not assign Flash-Lite the Flash threshold or infer hits from prompt layout. Keep common static instructions first and the question last as a cache-friendly hypothesis, then record actual `cachedContentTokenCount` in temporally clustered repeated-prefix and first-seen runs. Compaction could reduce ordinary input while also changing observed cache eligibility; report both regimes. Explicit cache storage and cache-input prices need their own break-even calculation against measured implicit hits, not an assumed benefit [9,11].

Keep thinking and output settings fixed during prompt compaction. Google says Flash-Lite’s default does not think; explicit budget `0` disables thinking, dynamic budget is `-1`, and positive budgets are 512–24,576 [12]. `maxOutputTokens` covers thoughts plus visible output; hitting the ceiling during thinking can truncate output while still incurring thought-token charges [12]. Therefore thinking-budget experiments are a separate axis, after compact-prompt semantic comparison. Neither reducing the output ceiling nor assuming zero thought tokens is a valid proxy. Likewise, no provider latency SLA or source benchmark establishes sub-second Countrydle planning. A faster-model description is not a p95 guarantee. Measure full request wall time, retries, local parse/compile/execute, and provider latency; report cold/warm process and cache conditions separately. No paper or provider document cited here supports a claim of <1 second.

## Gold evaluation and limits

Build a privacy-safe, adjudicated EN/PL corpus and lock a held-out partition before prompt tuning. Split by semantic template/paraphrase family, keeping translations and generated variants together, rather than random utterance. Include mixed-domain conjunctions/disjunctions; negation scope; nested/repeated conditions; `any`/`all`; exact boundary values below/equal/above; relation confusions such as culture versus language family; ambiguity/clarification; valid unsupported facts/fallback; missing or disputed coverage; and geographic extent. Gold should record a predicate/denotation graph (relation, operator, operands, polarity, connective, scope and bindings), expected route, clarification requirement, and answers on deterministic fixtures containing boundary, multi-item and missing-data cases.

Compare current prompt with manually compacted prompt under identical model, schema, temperature, thinking budget and output ceiling. Keep schema and executor fixed. Score gold denotation and semantic-graph equivalence, condition preservation/false-added conditions, relation/operator selection, polarity, scope, bound inclusivity and route confusion separately. Report schema/compile validity only as an operational measure, never as correctness. Use paired case comparisons, denominators and uncertainty intervals; inspect counterexamples and prespecify a non-inferiority margin. Semantic and routing gates outrank token savings. Add a minimal contrastive-example variant only as a separately measured ablation. Corpus benchmarks such as Spider motivate held-out cross-domain evaluation but do not predict this app’s accuracy [1,13]. MultiSpider reports a non-English drop in its tested languages, but does not include Polish [14]; neither that result nor any benchmark/model score is a PL estimate. No cited study directly evaluates this planner, its EN/PL semantics, or Gemini Flash-Lite on Countrydle questions.

Report input and cached-input tokens, visible output and thought tokens, priced calls, failures/retries, latency distributions, route outcomes and semantic scores together. The existing preliminary single-question probe is not aggregate evidence and should not be used to claim a baseline or target attainment; aggregate results belong after the project’s held-out gates. Final judgment: compact the fixed prompt manually, preserve a complete typed relation inventory and semantic core, treat SQLite coverage as explicit sourced data with unknown distinct from false, and make any further optimization conditional on held-out accuracy and measured whole-pipeline cost/latency.


## Bibliography

[1] **RAT-SQL: Relation-Aware Schema Encoding and Linking for Text-to-SQL Parsers.** ACL 2020. https://aclanthology.org/2020.acl-main.677/

[2] **Re-examining the Role of Schema Linking in Text-to-SQL.** EMNLP 2020. https://aclanthology.org/2020.emnlp-main.564/

[3] **LinkAlign: Scalable Schema Linking for Real-World Large-Scale Multi-Database Text-to-SQL.** EMNLP 2025. https://aclanthology.org/2025.emnlp-main.51/

[4] **Structured outputs — Gemini API.** Google AI for Developers. https://ai.google.dev/gemini-api/docs/generate-content/structured-output

[5] **Grammar-Constrained Decoding Makes Large Language Models Better Logical Parsers.** ACL 2025 Industry Track. https://aclanthology.org/2025.acl-industry.34/

[6] **An Empirical Study on Prompt Compression for Large Language Models.** Zhang et al., arXiv, 2025. https://arxiv.org/html/2505.00019v1

[7] **LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression.** Jiang et al., 2024. https://arxiv.org/html/2310.06839v2

[8] **PostgreSQL 18 Documentation: 9.1. Logical Operators.** https://www.postgresql.org/docs/18/functions-logical.html

[9] **Gemini Developer API pricing.** Google AI for Developers. https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite

[10] **Understand and count tokens.** Google AI for Developers. https://ai.google.dev/gemini-api/docs/tokens

[11] **Context caching — Gemini Generate Content API.** Google AI for Developers. https://ai.google.dev/gemini-api/docs/generate-content/caching

[12] **Gemini thinking — generateContent API.** Google AI for Developers. https://ai.google.dev/gemini-api/docs/generate-content/thinking

[13] **Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task.** EMNLP 2018. https://aclanthology.org/D18-1425/

[14] **MultiSpider: Towards Benchmarking Multilingual Text-to-SQL Semantic Parsing.** AAAI 2023. https://arxiv.org/abs/2212.13492

### Local design inputs (not external research citations)

- **Task 12: Add Sourced Cultural Facts to SQLite Without Bloated Planner Prompts.** Local project task specification, especially §§3–5; defines proposed one-relation/coverage/provenance constraints, not factual cultural classifications.
- **Countrydle planner protocol and local planner.** Local implementation context supplied through inspected research outputs; informs the existing AST and semantic invariants, not independent empirical evidence.
