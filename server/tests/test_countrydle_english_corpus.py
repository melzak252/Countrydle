"""Reviewed adversarial questions and actual captured-provider semantic regressions."""
import asyncio
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from countrydle import local_answering, local_planner, template_compiler, utils
from utils import ai_clients


FIXTURES = Path(__file__).parent
QUESTIONS = json.loads((FIXTURES / "countrydle_english_questions.json").read_text())["cases"]
MODEL_CASES = json.loads((FIXTURES / "countrydle_english_model_cases.json").read_text())["cases"]
MODEL_SCENARIOS = [(case, target, expected) for case in MODEL_CASES
                   for target, expected in case["answers"].items()]


@pytest.mark.parametrize("case", QUESTIONS, ids=[case["question"] for case in QUESTIONS])
def test_all_collected_tricky_questions_preserve_complete_template_meaning(case):
    compiled = template_compiler.compile_template_plan(case["question"], english_only=True)
    if case["expected_plan"] is None:
        assert compiled is None
    else:
        assert compiled is not None
        assert compiled[0] == case["expected_plan"]


@pytest.fixture(scope="module")
def frozen_facts(tmp_path_factory):
    path = tmp_path_factory.mktemp("english-model-facts") / "country_facts.sqlite"
    facts = json.loads((FIXTURES / "countrydle_english_facts.json").read_text())
    with sqlite3.connect(path) as connection:
        for table in facts["tables"]:
            columns = ", ".join(f'"{name}" {datatype}' for name, datatype in table["columns"])
            connection.execute(f'CREATE TABLE "{table["name"]}" ({columns})')
            placeholders = ", ".join("?" for _ in table["columns"])
            connection.executemany(f'INSERT INTO "{table["name"]}" VALUES ({placeholders})', table["rows"])
    return path


@pytest.mark.parametrize("case, target, expected", MODEL_SCENARIOS,
                         ids=[f'{case["question"]} [{target}]' for case, target, _ in MODEL_SCENARIOS])
def test_captured_model_wires_produce_reviewed_player_answers(frozen_facts, monkeypatch, case, target, expected):
    monkeypatch.setattr(local_answering, "DEFAULT_DB_PATH", frozen_facts)
    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-captured-provider")
    monkeypatch.setattr(ai_clients, "generate_gemini_json", lambda *args, **kwargs: case["response"])
    monkeypatch.setattr(utils.CountryRepository, "get", AsyncMock(return_value=SimpleNamespace(
        name=target, official_name=target,
    )))
    plan = local_planner.analyze_question_for_local_plan(case["question"], use_cache=False)
    result = local_answering.execute_local_plan(
        plan.plan, target, plan.improved_question or case["question"],
    ) if plan.supported and plan.plan else None
    assert (result.answer if result is not None else None) is expected
    # Exercise the consumer path too: the provider supplies plans, never answers.
    response, _ = asyncio.run(utils.analyze_and_answer_locally(
        case["question"], SimpleNamespace(country_id=1, id=1), None, AsyncMock(), strict_errors=True,
    ))
    assert (response.answer if response is not None else None) is expected
    if response is not None and ("(" in case["question"] or ")" in case["question"]):
        for group in re.findall(r"\([^()]*\)", case["question"]):
            assert group in response.question
