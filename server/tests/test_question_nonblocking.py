import asyncio
import importlib
import threading
import time
from types import SimpleNamespace

import pytest


MODES = [
    ("countrydle", "CountryRepository", "country_id", "name"),
    ("us_statedle", "USStateRepository", "us_state_id", "name"),
    ("powiatdle", "PowiatRepository", "powiat_id", "nazwa"),
    ("wojewodztwodle", "WojewodztwoRepository", "wojewodztwo_id", "nazwa"),
]


class BlockingCall:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def __call__(self):
        self.entered.set()
        try:
            if not self.release.wait(timeout=5):
                raise RuntimeError("Event loop did not release the synchronous call")
        finally:
            self.finished.set()


async def while_loop_progresses(operation, blocking):
    task = asyncio.create_task(operation)
    try:
        deadline = time.monotonic() + 3
        while not blocking.entered.is_set() and not task.done():
            assert time.monotonic() < deadline, "Synchronous call never started"
            await asyncio.sleep(0.001)
        assert blocking.entered.is_set()
        # This independent coroutine must run while the synchronous call is blocked.
        assert not blocking.finished.is_set(), "Synchronous work blocked the event loop"
        assert not task.done()
    finally:
        blocking.release.set()
        result = await task
    return result


def mode_context(monkeypatch, mode, repository, id_field, name_field):
    module = importlib.import_module(f"{mode}.utils")
    loop_thread = threading.get_ident()

    class Session:
        def __init__(self):
            self.commits = 0

        async def commit(self):
            assert threading.get_ident() == loop_thread
            self.commits += 1

    session = Session()

    class Repository:
        def __init__(self, supplied_session):
            assert threading.get_ident() == loop_thread
            assert supplied_session is session

        async def get(self, entity_id):
            assert threading.get_ident() == loop_thread
            assert entity_id == 7
            return SimpleNamespace(**{name_field: "Test entity"})

    monkeypatch.setattr(module, repository, Repository)
    return module, SimpleNamespace(id=11, **{id_field: 7}), session


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES)
async def test_daily_planner_allows_other_coroutines_and_keeps_database_on_loop(
    monkeypatch, mode, repository, id_field, name_field,
):
    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)
    blocking = BlockingCall()
    plan = SimpleNamespace(valid=True, supported=False, plan=None)

    def planner(*args, evidence=None, **kwargs):
        assert session.commits == 1
        blocking()
        if evidence is not None:
            evidence.update(provider="gemini", cache_hit=False)
        return plan

    planner_name = "analyze_question_for_local_plan" if mode == "countrydle" else "analyze_question"
    monkeypatch.setattr(module, planner_name, planner)
    if mode != "countrydle":
        monkeypatch.setattr(module, "execute_plan", lambda *args: None)
    evidence = {}
    result = await while_loop_progresses(
        module.analyze_and_answer_locally("Is it coastal?", day, None, session, evidence=evidence),
        blocking,
    )
    assert result == (None, plan)
    assert evidence["planner"]["provider"] == "gemini"
    assert evidence["planner"]["cache_hit"] is False
    assert evidence["planner"]["duration_ms"] > 0


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES)
async def test_daily_fallback_allows_other_coroutines_and_preserves_false_answers(
    monkeypatch, mode, repository, id_field, name_field,
):
    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)
    blocking = BlockingCall()

    async def unavailable_retrieval(*args, **kwargs):
        raise RuntimeError("Retrieval unavailable")

    def answer(*args, evidence=None):
        assert session.commits == 1
        blocking()
        if evidence is not None:
            evidence.update(provider="test-provider", usage={"input_tokens": 12, "output_tokens": 3})
        return {"answer": False, "explanation": "It is inland."}

    monkeypatch.setattr(module, "get_fragments_matching_question", unavailable_retrieval)
    monkeypatch.setattr(module, "answer_question_for_entity", answer)
    question = SimpleNamespace(original_question="Is it coastal?", question="Is it coastal?", valid=True)
    evidence = {}
    result, vector = await while_loop_progresses(
        module.ask_question(question, day, None, session, evidence=evidence), blocking,
    )
    assert result.valid is True
    assert result.answer is False
    assert result.context == ""
    assert vector == []
    assert evidence["retrieval_duration_ms"] >= 0
    assert evidence["fallback"]["duration_ms"] > 0
    assert evidence["fallback"]["provider"] == "test-provider"
    assert evidence["fallback"]["usage"] == {"input_tokens": 12, "output_tokens": 3}


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES)
async def test_daily_fallback_rejects_string_answers_instead_of_charging_a_turn(
    monkeypatch, mode, repository, id_field, name_field,
):
    from pydantic import ValidationError

    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)

    async def retrieve(*args, **kwargs):
        return [], []

    monkeypatch.setattr(module, "get_fragments_matching_question", retrieve)
    monkeypatch.setattr(module, "answer_question_for_entity", lambda *args, **kwargs: {
        "answer": "false", "explanation": "Malformed provider response",
    })
    question = SimpleNamespace(original_question="Is it coastal?", question="Is it coastal?", valid=True)
    with pytest.raises(ValidationError):
        await module.ask_question(question, day, None, session)


@pytest.mark.anyio
@pytest.mark.parametrize("blocked_phase", ["embedding", "search", "retrieve"])
async def test_retrieval_allows_other_coroutines_through_every_sync_phase(monkeypatch, blocked_phase):
    import qdrant
    from qdrant import utils

    blocking = BlockingCall()
    point = SimpleNamespace(id=3, payload={"country_id": 7, "fragment_text": "It is inland."})

    def embedding(*args, **kwargs):
        if blocked_phase == "embedding":
            blocking()
        return [0.25, 0.75]

    def search(**kwargs):
        if blocked_phase == "search":
            blocking()
        return SimpleNamespace(groups=[SimpleNamespace(hits=[point])])

    def retrieve(**kwargs):
        if blocked_phase == "retrieve":
            blocking()
        return [point]

    monkeypatch.setattr(utils, "get_embedding", embedding)
    monkeypatch.setattr(qdrant, "client", SimpleNamespace(query_points_groups=search, retrieve=retrieve))
    fragments, vector = await while_loop_progresses(
        utils.get_fragments_matching_question("Is it coastal?", "country_id", 7, "countries", object()),
        blocking,
    )
    assert [fragment.text for fragment in fragments] == ["It is inland."]
    assert vector == [0.25, 0.75]


@pytest.mark.anyio
async def test_question_upsert_allows_other_coroutines(monkeypatch):
    import qdrant
    from qdrant import utils

    blocking = BlockingCall()
    monkeypatch.setattr(qdrant, "client", SimpleNamespace(upsert=lambda **kwargs: blocking()))
    question = SimpleNamespace(id=5, question="Is it coastal?", answer=False, explanation="It is inland.")
    await while_loop_progresses(
        utils.add_question_to_qdrant(question, [0.25, 0.75], "country_id", 7), blocking,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES[1:])
@pytest.mark.parametrize("strict_errors", [False, True])
async def test_local_execution_error_preserves_strict_mode(
    monkeypatch, mode, repository, id_field, name_field, strict_errors,
):
    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)
    plan = SimpleNamespace(valid=True, supported=False, plan=None)
    monkeypatch.setattr(module, "analyze_question", lambda *args, **kwargs: plan)

    def failed_local_execution(*args):
        raise ValueError("Broken local facts")

    monkeypatch.setattr(module, "execute_plan", failed_local_execution)
    evidence = {}
    operation = module.analyze_and_answer_locally(
        "Is it coastal?", day, None, session, strict_errors=strict_errors, evidence=evidence,
    )
    if strict_errors:
        with pytest.raises(ValueError, match="Broken local facts"):
            await operation
    else:
        assert await operation == (None, plan)
    assert evidence["local_duration_ms"] >= 0


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES)
async def test_local_fact_execution_does_not_block_loop(
    monkeypatch, mode, repository, id_field, name_field,
):
    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)
    blocking = BlockingCall()
    plan = SimpleNamespace(
        valid=True, supported=True, plan={"operator": "test"},
        improved_question="Is it coastal?", explanation="Coastline check",
    )
    local_answer = SimpleNamespace(
        question="Is it coastal?", answer=False, explanation="It is inland.",
        relation="coast", relations=["coast"],
    )

    def execute(*args, **kwargs):
        blocking()
        return local_answer

    planner_name = "analyze_question_for_local_plan" if mode == "countrydle" else "analyze_question"
    execute_name = "execute_local_plan" if mode == "countrydle" else "execute_plan"
    monkeypatch.setattr(module, planner_name, lambda *args, **kwargs: plan)
    monkeypatch.setattr(module, execute_name, execute)
    evidence = {}
    result, returned_plan = await while_loop_progresses(
        module.analyze_and_answer_locally("Is it coastal?", day, None, session, evidence=evidence),
        blocking,
    )
    assert result.answer is False
    assert result.context == "local_kb:coast"
    assert returned_plan is plan
    assert evidence["local_duration_ms"] > 0


@pytest.mark.anyio
@pytest.mark.parametrize("mode,repository,id_field,name_field", MODES[1:])
@pytest.mark.parametrize("openai_unavailable", [False, True])
async def test_real_answer_helper_keeps_provider_fallback_nonblocking_and_reports_usage(
    monkeypatch, mode, repository, id_field, name_field, openai_unavailable,
):
    module, day, session = mode_context(monkeypatch, mode, repository, id_field, name_field)
    blocking = BlockingCall()

    async def no_fragments(*args, **kwargs):
        return [], []

    def completion(**kwargs):
        if openai_unavailable:
            raise RuntimeError("OpenAI unavailable")
        blocking()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"answer": false, "explanation": "It is inland."}',
            ))],
            model="configured-test-model", id="response-test", system_fingerprint=None,
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15),
        )

    def gemini(*args, evidence=None, **kwargs):
        blocking()
        if evidence is not None:
            evidence.update(provider="gemini", model="test-gemini")
        return {"answer": False, "explanation": "It is inland."}

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    monkeypatch.setattr(module, "get_openai_client", lambda **kwargs: client)
    monkeypatch.setattr(module, "get_fragments_matching_question", no_fragments)
    monkeypatch.setattr("countrydle.utils.gemini_json", gemini)
    question = SimpleNamespace(
        original_question="Is it coastal?", question="Is it coastal?", valid=True,
        intent="Coastline check", required_info="Coastline",
    )
    evidence = {}
    result, _ = await while_loop_progresses(
        module.ask_question(question, day, None, session, evidence=evidence), blocking,
    )
    assert result.answer is False
    assert evidence["fallback"]["duration_ms"] > 0
    if openai_unavailable:
        assert evidence["fallback"]["provider"] == "gemini"
    else:
        assert evidence["fallback"]["provider"] == "openai"
        assert evidence["fallback"]["usage"] == {
            "input_tokens": 12, "output_tokens": 3, "total_tokens": 15,
        }
