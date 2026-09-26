"""Permanent regression test suite for QA playground findings and edge cases."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
FINDINGS_PATH = SERVER_DIR / "test_reports" / "qa_playground_findings.jsonl"
REPORT_PATH = SERVER_DIR / "test_reports" / "qa_playground_report.md"


def test_qa_playground_dataset_integrity():
    assert FINDINGS_PATH.exists(), f"Findings dataset missing at {FINDINGS_PATH}"
    assert REPORT_PATH.exists(), f"QA report missing at {REPORT_PATH}"

    lines = [json.loads(line) for line in FINDINGS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 165, f"Expected at least 165 findings records, got {len(lines)}"

    modes = {r["mode"] for r in lines}
    assert {"countrydle", "wojewodztwodle", "powiatdle", "us_statedle"}.issubset(modes)

    for r in lines:
        assert "question" in r and r["question"]
        assert "target_entity" in r and r["target_entity"]
        assert "verdict" in r


@pytest.mark.parametrize("mode, question, target, expected", [
    ("countrydle", "Is it in Europe?", "Poland", True),
    ("countrydle", "Is it in the Northern Hemisphere?", "Kiribati", True),
    ("countrydle", "Is it in the Southern Hemisphere?", "Kiribati", True),
    ("countrydle", "Is it entirely in the Northern Hemisphere?", "Kiribati", False),
    ("countrydle", "Is it entirely in the Northern Hemisphere?", "Poland", True),
    ("countrydle", "Does it have access to the sea?", "Poland", True),
    ("countrydle", "Is it landlocked?", "Czech Republic", True),
    ("countrydle", "Is it an island country?", "Dominican Republic", True),
    ("wojewodztwodle", "Czy to województwo graniczy z województwem łódzkim?", "Śląskie", True),
    ("wojewodztwodle", "Czy ma dostęp do morza?", "Pomorskie", True),
    ("wojewodztwodle", "Czy to województwo graniczy ze Słowacją?", "Małopolskie", True),
    ("powiatdle", "Czy to miasto na prawach powiatu?", "Kraków", True),
    ("powiatdle", "Czy to powiat ziemski?", "Powiat krakowski", True),
    ("us_statedle", "Does it border Texas?", "New Mexico", True),
    ("us_statedle", "Is it coastal?", "California", True),
])
def test_qa_playground_golden_evaluations(mode, question, target, expected):
    from scripts.qa_playground import evaluate_case

    rec = evaluate_case(
        mode=mode,
        question=question,
        target_entity=target,
        expected_answer=expected,
        category="golden_regression",
    )
    assert rec["verdict"] == "PASS", f"Failed for {mode} question '{question}' on {target}: {rec}"
    assert rec["actual_answer"] == expected
