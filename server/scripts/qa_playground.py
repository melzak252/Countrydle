"""QA Playground Harness for Countrydle and regional game modes.

Evaluates questions across all game modes, capturing planner ASTs, local execution results,
explanations, latencies, and categorizing any defects/edge cases found.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT_DIR / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from dotenv import load_dotenv
if (Path("/home/melzak/dev/Countrydle/.env")).exists():
    load_dotenv("/home/melzak/dev/Countrydle/.env", override=True)
else:
    load_dotenv(ROOT_DIR / ".env", override=False)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOCAL_QUESTION_MODEL", "gemini-2.5-flash-lite")
os.environ.setdefault("GEMINI_QUESTION_MODEL", "gemini-2.5-flash-lite")
os.environ.setdefault("EMAIL_USERNAME", "test@example.com")
os.environ.setdefault("NOREPLY_EMAIL", "test@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "test-password")
os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890123456")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("GEMINI_QUESTION_MODEL", "gemini-2.5-flash-lite")

from countrydle.local_planner import analyze_question_for_local_plan
from countrydle.local_answering import execute_local_plan
from wojewodztwodle.utils import LOCAL_CONFIG as WOJ_CONFIG
from powiatdle.utils import LOCAL_CONFIG as POW_CONFIG
from us_statedle.utils import LOCAL_CONFIG as US_CONFIG
from local_kb_question import analyze_question as analyze_generic_question, execute_plan as execute_generic_plan

MODES = {
    "countrydle": None,
    "wojewodztwodle": WOJ_CONFIG,
    "powiatdle": POW_CONFIG,
    "us_statedle": US_CONFIG,
}

REPORTS_DIR = SERVER_DIR / "test_reports"
FINDINGS_PATH = REPORTS_DIR / "qa_playground_findings.jsonl"


def evaluate_case(
    mode: str,
    question: str,
    target_entity: str,
    expected_answer: bool | None = None,
    notes: str = "",
    category: str = "general",
) -> dict[str, Any]:
    norm_mode = mode.lower().strip()
    if norm_mode not in MODES:
        raise ValueError(f"Unknown game mode '{mode}'. Choose from: {list(MODES.keys())}")

    record: dict[str, Any] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": norm_mode,
        "question": question,
        "target_entity": target_entity,
        "expected_answer": expected_answer,
        "category": category,
        "notes": notes,
    }

    t0 = time.perf_counter()
    try:
        if norm_mode == "countrydle":
            plan_res = analyze_question_for_local_plan(question, use_cache=False)
        else:
            plan_res = analyze_generic_question(question, MODES[norm_mode], use_cache=False)
        plan_ms = (time.perf_counter() - t0) * 1000

        record["valid"] = plan_res.valid
        record["supported"] = plan_res.supported
        record["improved_question"] = plan_res.improved_question
        record["explanation_planner"] = plan_res.explanation
        record["fallback_reason"] = plan_res.fallback_reason
        record["plan_ast"] = plan_res.plan
        record["plan_ms"] = round(plan_ms, 2)

        if plan_res.supported and plan_res.plan:
            t_exec = time.perf_counter()
            if norm_mode == "countrydle":
                ans_res = execute_local_plan(
                    plan_res.plan,
                    target_entity,
                    plan_res.improved_question or question,
                )
                exec_ms = (time.perf_counter() - t_exec) * 1000
                if ans_res:
                    record["actual_answer"] = ans_res.answer
                    record["actual_explanation"] = ans_res.explanation
                    record["actual_relations"] = [ans_res.relation]
                else:
                    record["actual_answer"] = None
                    record["actual_explanation"] = "Target entity not found in SQLite or plan unresolvable"
                    record["actual_relations"] = []
            else:
                ans_res = execute_generic_plan(MODES[norm_mode], target_entity, plan_res)
                exec_ms = (time.perf_counter() - t_exec) * 1000
                if ans_res:
                    record["actual_answer"] = ans_res.answer
                    record["actual_explanation"] = ans_res.explanation
                    record["actual_relations"] = ans_res.relations
                else:
                    record["actual_answer"] = None
                    record["actual_explanation"] = "Target entity not found in SQLite or plan unresolvable"
                    record["actual_relations"] = []
            record["exec_ms"] = round(exec_ms, 2)
        else:
            record["actual_answer"] = None
            record["actual_explanation"] = plan_res.explanation or plan_res.fallback_reason
            record["actual_relations"] = []
            record["exec_ms"] = 0.0

        # Defect categorization
        if expected_answer is not None:
            if not record["valid"]:
                record["verdict"] = "FAIL_INVALID" if expected_answer is not None else "CLARIFY"
            elif not record["supported"]:
                record["verdict"] = "FAIL_FALLTHROUGH"
            elif record["actual_answer"] is None:
                record["verdict"] = "FAIL_UNRESOLVED"
            elif record["actual_answer"] == expected_answer:
                record["verdict"] = "PASS"
            else:
                record["verdict"] = "FAIL_LOGIC"
        else:
            record["verdict"] = "EXPLORATORY"

    except Exception as exc:
        record["verdict"] = "FAIL_CRASH"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["plan_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    return record


def log_record(record: dict[str, Any], output_path: Path = FINDINGS_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_record(record: dict[str, Any]):
    verdict = record.get("verdict", "UNKNOWN")
    color = "\033[92m" if verdict == "PASS" else ("\033[91m" if "FAIL" in verdict else "\033[93m")
    reset = "\033[0m"
    print(f"{color}[{verdict:15}]{reset} [{record['mode']}] Q: {record['question']} -> Target: {record['target_entity']}")
    if "plan_ast" in record and record["plan_ast"]:
        print(f"    AST : {json.dumps(record['plan_ast'], ensure_ascii=False)}")
    print(f"    Ans : {record.get('actual_answer')} (Expected: {record.get('expected_answer')})")
    if record.get("actual_explanation"):
        print(f"    Expl: {record['actual_explanation']}")
    if "error" in record:
        print(f"    ERR : {record['error']}")
    print(f"    Time: plan={record.get('plan_ms', 0)}ms, exec={record.get('exec_ms', 0)}ms")


def main():
    parser = argparse.ArgumentParser(description="Run Countrydle QA Playground queries")
    parser.add_argument("--mode", default="countrydle", choices=list(MODES.keys()))
    parser.add_argument("--question", "-q", help="Natural language question to evaluate")
    parser.add_argument("--target", "-t", default="Poland", help="Target entity name")
    parser.add_argument("--expected", "-e", choices=["true", "false", "null"], help="Expected boolean answer")
    parser.add_argument("--notes", default="", help="Contextual testing notes")
    parser.add_argument("--category", default="interactive", help="Test category")
    parser.add_argument("--batch", "-b", type=Path, help="JSON or JSONL file with batch cases")
    parser.add_argument("--output", "-o", type=Path, default=FINDINGS_PATH, help="Output JSONL findings path")

    args = parser.parse_args()

    if args.batch:
        if not args.batch.exists():
            print(f"Batch file not found: {args.batch}", file=sys.stderr)
            sys.exit(1)
        if args.batch.suffix == ".jsonl":
            cases = [json.loads(line) for line in args.batch.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            cases = json.loads(args.batch.read_text(encoding="utf-8"))

        passed = 0
        failed = 0
        for item in cases:
            rec = evaluate_case(
                mode=item.get("mode", args.mode),
                question=item["question"],
                target_entity=item["target_entity"],
                expected_answer=item.get("expected_answer"),
                notes=item.get("notes", ""),
                category=item.get("category", "batch"),
            )
            log_record(rec, args.output)
            print_record(rec)
            if rec.get("verdict") == "PASS":
                passed += 1
            elif "FAIL" in rec.get("verdict", ""):
                failed += 1

        print(f"\nBatch complete: {len(cases)} cases. Passed: {passed}, Failed: {failed}")
        sys.exit(0 if failed == 0 else 1)

    if not args.question:
        parser.print_help()
        sys.exit(1)

    expected_bool = None
    if args.expected:
        expected_bool = True if args.expected == "true" else (False if args.expected == "false" else None)

    rec = evaluate_case(
        mode=args.mode,
        question=args.question,
        target_entity=args.target,
        expected_answer=expected_bool,
        notes=args.notes,
        category=args.category,
    )
    log_record(rec, args.output)
    print_record(rec)


if __name__ == "__main__":
    main()
