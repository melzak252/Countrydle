"""Friend guidance exercises the normal evaluators with explicit, non-daily targets."""
import hashlib
from contextlib import ExitStack
import json
import threading
import httpx

import pytest

from friend_matches import providers
from local_kb_question import QuestionPlan
from utils import ai_clients


@pytest.fixture
def gemini_http(monkeypatch):
    with ExitStack() as resources:
        def install(handler):
            client = resources.enter_context(httpx.Client(transport=httpx.MockTransport(handler)))
            monkeypatch.setattr(ai_clients, "_http_client", client)
        yield install


@pytest.mark.parametrize(
    "mode,name,relation,value",
    [
        ("countrydle", "Poland", "capital", "Warsaw"),
        ("europe", "Poland", "capital", "Warsaw"),
        ("asia", "Japan", "capital", "Tokyo"),
        ("africa", "Egypt", "capital", "Cairo"),
        ("americas", "Brazil", "capital", "Brasília"),
        ("us_statedle", "California", "region", "West"),
        ("wojewodztwodle", "Dolnośląskie", "seat", "Wrocław"),
        ("powiatdle", "Biała Podlaska", "is_city_county", 1),
    ],
)
@pytest.mark.anyio
async def test_guidance_resolves_canonical_id_not_supplied_name(monkeypatch, mode, name, relation, value):
    engine = providers._engine(mode)
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entity = next(item for item in providers.list_entities(mode) if item["name"] == name)
    plan = QuestionPlan(
        original_question="Question?", valid=True, supported=True,
        improved_question="Question?", explanation="Check canonical fact.",
        plan={"operator": "equals", "left": {"entity": engine.target_entity, "relation": relation}, "right": {"value": value}},
    )
    monkeypatch.setattr(providers, "_plan", lambda *args: plan)
    result = await providers.evaluate_question(mode, {**entity, "name": "Wrong target"}, "Question?")
    assert result["answer"] == "YES"
    assert result["evidence"]["target"] == entity
    assert result["evidence"]["planner"]["output"]["plan"] == plan.plan
    assert result["explanation"]
    assert isinstance(entity["id"], str)


def test_entity_list_cannot_be_mutated_by_a_caller():
    engine = providers._engine("countrydle")
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entities = providers.list_entities("countrydle")
    original = entities[0].copy()
    entities[0]["name"] = "Corrupted"
    entities.clear()
    assert providers.list_entities("countrydle")[0] == original


@pytest.mark.parametrize("value,expected", [(True, "YES"), (False, "NO"), (None, "INVALID")])
def test_normalize_distinguishes_no_from_uncertainty(value, expected):
    assert providers._normalize_answer(value) == expected


@pytest.mark.parametrize("value", ["false", "NO", 0, {}, []])
def test_malformed_model_answers_raise_instead_of_becoming_no(value):
    with pytest.raises(RuntimeError):
        providers._normalize_answer(value)


@pytest.mark.anyio
async def test_provider_failure_propagates_off_event_loop(monkeypatch):
    loop_thread = threading.get_ident()

    def failure(*args):
        assert threading.get_ident() != loop_thread
        raise RuntimeError("Provider unavailable")

    monkeypatch.setattr(providers, "_evaluate", failure)
    with pytest.raises(RuntimeError, match="Provider unavailable"):
        await providers.evaluate_question("countrydle", {"id": "POL"}, "Question?")


@pytest.mark.parametrize(
    "mode,name",
    [
        ("countrydle", "Poland"),
        ("us_statedle", "California"),
        ("wojewodztwodle", "Dolnośląskie"),
        ("powiatdle", "Biała Podlaska"),
    ],
)
@pytest.mark.anyio
async def test_unsupported_question_uses_gemini_with_canonical_facts_and_markdown(monkeypatch, gemini_http, mode, name):
    import openai
    import qdrant.utils
    import db

    engine = providers._engine(mode)
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entity = next(item for item in providers.list_entities(mode) if item["name"] == name)
    question = "Does it have mountains?"
    plan = QuestionPlan(question, True, False, None, "Interpretation", None, "unsupported relation")
    monkeypatch.setattr(providers, "_plan", lambda *args: plan)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_QUIZ_MODEL", "gemini-test")
    loop_thread = threading.get_ident()
    sent = {}

    def forbidden(*args, **kwargs):
        pytest.fail("Duel guidance must not call OpenAI, vector retrieval, or PostgreSQL")

    monkeypatch.setattr(openai.OpenAI, "__init__", forbidden)
    monkeypatch.setattr(qdrant.utils, "get_fragments_matching_question_sync", forbidden)
    monkeypatch.setattr(db, "AsyncSessionLocal", forbidden)

    def response(request):
        assert threading.get_ident() != loop_thread
        assert str(request.url).startswith("https://generativelanguage.googleapis.com/v1beta/models/gemini-test:")
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={
            "modelVersion": "gemini-test-001",
            "responseId": "answer-response",
            "candidates": [{"content": {"parts": [{"text": json.dumps({
                "answer": False, "explanation": "The requested property does not apply.",
            })}]}}],
        })

    gemini_http(response)
    result = await providers.evaluate_question(mode, {**entity, "name": "Wrong target"}, question)
    assert result["answer"] == "NO"
    assert result["source"] == "normal_fallback"
    evidence = result["evidence"]
    assert evidence["target"] == entity
    context = evidence["context"]
    markdown = (providers.local.ROOT_DIR / context["markdown"]["file"]).read_bytes().decode("utf-8")
    assert context["source"] == "canonical_facts_and_markdown"
    assert context["markdown"]["sha256"] == hashlib.sha256(markdown.encode()).hexdigest()
    prompt = sent["contents"][0]["parts"][0]["text"]
    assert markdown in prompt
    assert json.dumps(evidence["facts"]["target_row"], ensure_ascii=False) in prompt
    assert json.dumps(evidence["facts"]["target_relations"], ensure_ascii=False) in prompt
    assert question in prompt
    assert "Wrong target" not in prompt
    assert evidence["fallback"]["provider"] == "gemini"
    assert evidence["fallback"]["model"] == "gemini-test"
    assert evidence["fallback"]["model_version"] == "gemini-test-001"
    assert evidence["fallback"]["response_id"] == "answer-response"


@pytest.mark.anyio
async def test_invalid_question_does_not_call_fallback(monkeypatch):
    engine = providers._engine("countrydle")
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entity = providers.list_entities("countrydle")[0]
    plan = QuestionPlan("Name it", False, False, None, "Not a yes/no question.", None)
    monkeypatch.setattr(providers, "_plan", lambda *args: plan)
    from countrydle import utils as gemini

    monkeypatch.setattr(gemini, "generate_gemini_json", lambda *args, **kwargs: pytest.fail("Invalid question called fallback"))
    result = await providers.evaluate_question("countrydle", entity, "Name it")
    assert result["answer"] == "INVALID"


def test_country_missing_provider_is_operational_only_when_strict(monkeypatch):
    from countrydle import local_planner

    monkeypatch.setattr(local_planner, "load_dotenv_if_present", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # The opt-in contract must not change existing daily callers' fallback.
    normal = local_planner.analyze_question_for_local_plan("Question?", use_cache=False)
    assert normal.valid and not normal.supported
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        local_planner.analyze_question_for_local_plan("Question?", use_cache=False, strict_errors=True)


def test_malformed_planner_protocol_is_not_invalid_question(monkeypatch):
    import local_kb_question

    engine = providers._engine("us_statedle")
    monkeypatch.setattr(local_kb_question, "gemini_json", lambda *args, **kwargs: {"valid": "false"})
    with pytest.raises(RuntimeError):
        local_kb_question.analyze_question("Question?", engine.config, use_cache=False, strict_errors=True)


@pytest.mark.anyio
async def test_gemini_quota_failure_propagates_without_fabricating_an_answer(monkeypatch, gemini_http):

    engine = providers._engine("countrydle")
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entity = providers.list_entities("countrydle")[0]
    plan = QuestionPlan("Mountains?", True, False, "Mountains?", None, None)
    monkeypatch.setattr(providers, "_plan", lambda *args: plan)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def unavailable(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

    gemini_http(unavailable)
    with pytest.raises(RuntimeError) as failure:
        await providers.evaluate_question("countrydle", entity, "Mountains?")
    assert failure.value.__cause__.response.status_code == 429
    assert len(calls) == 1


@pytest.mark.anyio
async def test_missing_canonical_markdown_is_not_silently_replaced_with_empty_context(monkeypatch, tmp_path):
    from countrydle import utils as gemini

    engine = providers._engine("us_statedle")
    if not engine.db_path.exists():
        pytest.skip("Local canonical facts unavailable")
    entity = providers.list_entities("us_statedle")[0]
    plan = QuestionPlan("Mountains?", True, False, "Mountains?", None, None)
    monkeypatch.setattr(providers, "_plan", lambda *args: plan)
    monkeypatch.setattr(providers.local, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(gemini, "generate_gemini_json", lambda *args, **kwargs: pytest.fail("Missing context called Gemini"))
    with pytest.raises(FileNotFoundError):
        await providers.evaluate_question("us_statedle", entity, "Mountains?")


def test_missing_explanation_keeps_actual_recommendation():
    plan = QuestionPlan("Question?", True, False, "Question?", None, None)
    evidence = {"fallback": {"output": {"answer": False, "explanation": None}}}
    result = providers._result(False, None, "normal_fallback", plan, evidence)
    assert result["answer"] == "NO"
    assert result["explanation"] == ""
    assert result["evidence"]["explanation_missing"] is True
    assert result["evidence"]["fallback"]["output"]["explanation"] is None


def test_nontext_explanation_is_a_provider_protocol_failure():
    plan = QuestionPlan("Question?", True, False, "Question?", None, None)
    with pytest.raises(RuntimeError):
        providers._result(True, {"reasoning": "unexpected object"}, "normal_fallback", plan, {})
