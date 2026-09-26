"""Evaluate country identity questions with real Gemini and the local fact executor."""
import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
import sys
import time

from dotenv import load_dotenv

SERVER = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, required=True, help='New directory for immutable run artifacts.')
parser.add_argument('--env-file', type=Path, default=SERVER.parent / '.env')
args = parser.parse_args()
HERE = args.output_dir.resolve()
CORPUS = SERVER / 'tests/country_identity_model_regressions.json'
load_dotenv(args.env_file)
os.environ.update(
    DATABASE_URL='sqlite+aiosqlite:///:memory:',
    QDRANT_HOST='127.0.0.1',
    LOCAL_QUESTION_MODEL='gemini-2.5-flash-lite',
    GEMINI_QUESTION_MODEL='gemini-2.5-flash-lite',
)
sys.path.insert(0, str(SERVER))
from countrydle.local_planner import analyze_question_for_local_plan
from countrydle.local_answering import execute_local_plan
from planner_protocol import PLANNER_VERSION
from utils.ai_clients import close_ai_clients

CASES_PATH = HERE / 'cases.json'
CASE_BYTES = CORPUS.read_bytes()
CASES = json.loads(CASE_BYTES)
SOURCES = ['countrydle/local_planner.py', 'countrydle/local_answering.py', 'planner_protocol.py']
REPETITIONS = 2


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(case, plan, answers):
    if not plan.valid:
        return 'clarify'
    if not plan.supported:
        return 'fallback_required'
    if any(value is None or type(value.get('answer')) is not bool for value in answers.values()):
        return 'local_unresolved'
    if case['expectation'] == 'clarify_without_guessing':
        return 'wrong_identity'
    expected = case['expected_country']
    if all(value['answer'] is (target == expected) for target, value in answers.items()):
        return 'correct_identity'
    return 'wrong_identity'


async def main():
    HERE.mkdir(parents=True, exist_ok=False)
    CASES_PATH.write_bytes(CASE_BYTES)
    if digest(CORPUS) != digest(CASES_PATH):
        raise RuntimeError('Input corpus changed before the run began.')

    targets = sorted(
        {case['expected_country'] for case in CASES if case['expected_country']}
        | {'Poland', 'Dominica', 'Dominican Republic', 'Niger', 'Nigeria'}
    )
    source_hashes = {name: digest(SERVER / name) for name in SOURCES}
    metadata = {
        'model': 'gemini-2.5-flash-lite',
        'planner_version': PLANNER_VERSION,
        'repetitions': REPETITIONS,
        'concurrency': 2,
        'cache': 'application plan cache bypassed (use_cache=False)',
        'scope': 'Real local planner and deterministic local executor. No fallback generation, HTTP gameplay or gameplay database writes.',
        'corpus_path': str(CORPUS.relative_to(SERVER)),
        'corpus_sha256': digest(CORPUS),
        'cases_sha256': digest(CASES_PATH),
        'facts_sha256': digest(SERVER / 'data/country_facts.sqlite'),
        'source_hashes': source_hashes,
        'targets': targets,
        'scoreable_case_count': sum(bool(case['scoreable']) for case in CASES),
        'case_count': len(CASES),
    }
    (HERE / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    semaphore = asyncio.Semaphore(2)
    rows = []

    async def run(case, repetition):
        async with semaphore:
            start = time.perf_counter()
            row = {
                'case_id': case['case_id'],
                'question': case['question'],
                'expected_country': case['expected_country'],
                'expectation': case['expectation'],
                'scoreable': case['scoreable'],
                'repetition': repetition,
            }
            try:
                evidence = {}
                plan = await asyncio.to_thread(
                    analyze_question_for_local_plan,
                    case['question'],
                    use_cache=False,
                    strict_errors=True,
                    evidence=evidence,
                )
                row['plan'] = asdict(plan)
                row['diagnostics'] = {
                    key: evidence.get(key)
                    for key in ('model', 'model_version', 'contract_version', 'cache_hit', 'usage', 'duration_ms')
                }
                row['answers'] = {}
                if plan.valid and plan.supported:
                    for target in targets:
                        result = await asyncio.to_thread(
                            execute_local_plan,
                            plan.plan,
                            target,
                            plan.improved_question or case['question'],
                        )
                        row['answers'][target] = asdict(result) if result else None
                row['outcome'] = classify(case, plan, row['answers'])
                if case['expectation'] == 'clarify_without_guessing':
                    row['expectation_met'] = row['outcome'] in ('clarify', 'local_unresolved')
                else:
                    row['expectation_met'] = row['outcome'] == 'correct_identity'
            except Exception as exc:
                row.update(outcome='technical_error', expectation_met=False, error_type=type(exc).__name__)
            row['duration_ms'] = round((time.perf_counter() - start) * 1000, 2)
            rows.append(row)
            with (HERE / 'results.jsonl').open('a') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps({
                'case_id': case['case_id'],
                'question': case['question'],
                'repetition': repetition,
                'outcome': row['outcome'],
                'expectation_met': row['expectation_met'],
            }, ensure_ascii=False), flush=True)

    await asyncio.gather(*(run(case, repetition) for repetition in range(1, REPETITIONS + 1) for case in CASES))
    metadata.update(
        source_unchanged=all(digest(SERVER / name) == value for name, value in source_hashes.items()),
        cases_unchanged=digest(CASES_PATH) == metadata['cases_sha256'],
        corpus_unchanged=digest(CORPUS) == metadata['corpus_sha256'],
        facts_unchanged=digest(SERVER / 'data/country_facts.sqlite') == metadata['facts_sha256'],
    )
    if not all(metadata[key] for key in ('source_unchanged', 'cases_unchanged', 'corpus_unchanged', 'facts_unchanged')):
        raise RuntimeError('Source, facts, or case inputs changed during the experiment.')

    scored_rows = [row for row in rows if row['scoreable']]
    outcome_counts = {}
    for row in scored_rows:
        outcome_counts[row['outcome']] = outcome_counts.get(row['outcome'], 0) + 1
    contrast = [row for row in rows if row['case_id'] == 'identity-29']
    summary = {
        'model': metadata['model'],
        'planner_version': PLANNER_VERSION,
        'repetitions': REPETITIONS,
        'case_count': len(CASES),
        'scoreable_case_count': len(scored_rows) // REPETITIONS,
        'scored_observations': len(scored_rows),
        'expectation_met': sum(row['expectation_met'] for row in scored_rows),
        'outcome_counts': outcome_counts,
        'scope': metadata['scope'],
        'inputs': {
            'corpus_sha256': metadata['corpus_sha256'],
            'cases_sha256': metadata['cases_sha256'],
            'facts_sha256': metadata['facts_sha256'],
            'source_hashes': source_hashes,
        },
        'dominica_on_dominican_republic': [
            {
                'case_id': row['case_id'],
                'question': row['question'],
                'repetition': row['repetition'],
                'expected_country': row['expected_country'],
                'observed_answer': row.get('answers', {}).get('Dominican Republic', {}).get('answer')
                if row.get('answers', {}).get('Dominican Republic') else None,
                'outcome': row['outcome'],
            }
            for row in contrast
        ],
        'cases': [
            {
                'case_id': row['case_id'],
                'repetition': row['repetition'],
                'outcome': row['outcome'],
                'expectation_met': row['expectation_met'],
                'scoreable': row['scoreable'],
            }
            for row in rows
        ],
        'inputs_unchanged': all(metadata[key] for key in ('source_unchanged', 'cases_unchanged', 'corpus_unchanged', 'facts_unchanged')),
    }
    (HERE / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    return all(row['expectation_met'] for row in scored_rows)


if __name__ == '__main__':
    try:
        passed = asyncio.run(main())
    finally:
        close_ai_clients()
    raise SystemExit(0 if passed else 1)
