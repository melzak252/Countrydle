import asyncio
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)
FALLBACK_DEADLINE_SECONDS = float(os.getenv("FALLBACK_DEADLINE_SECONDS", "15.0"))
from qdrant.utils import get_fragments_matching_question
from db.repositories import fallback_answers as answer_cache
from utils.ai_clients import get_gemini_model
from utils.request_budget import remaining_timeout


async def retrieve_and_answer(
    question: Any,
    entity_name: str,
    *,
    cache_scope: tuple[str, int] | None,
    filter_key: str,
    filter_value: int,
    collection_name: str,
    context_limit: int,
    session: Any,
    answerer: Callable[..., dict],
    prompt_builder: Callable[..., tuple[str, str]],
    evidence: dict | None = None,
    game_date: date | None = None,
) -> tuple[dict, str, list[float]]:
    """Retrieve fresh evidence and answer within one bounded daily request."""
    deadline = time.monotonic() + FALLBACK_DEADLINE_SECONDS
    fragments = []
    question_vector: list[float] = []
    retrieval_started = time.perf_counter()
    try:
        async with asyncio.timeout(remaining_timeout(deadline)):
            try:
                fragments, question_vector = await get_fragments_matching_question(
                    question.question or question.original_question,
                    filter_key,
                    filter_value,
                    collection_name,
                    session,
                    limit=context_limit,
                    deadline=deadline,
                )
            except Exception as exc:
                if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or time.monotonic() >= deadline:
                    raise TimeoutError("Daily fallback deadline exhausted") from exc
                logger.warning("Vector retrieval failed (%s); answering with general knowledge.", exc)
    finally:
        if evidence is not None:
            evidence["retrieval_duration_ms"] = (time.perf_counter() - retrieval_started) * 1000

    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments) if fragments else ""
    fallback_evidence = evidence.setdefault("fallback", {}) if evidence is not None else None
    model = get_gemini_model()
    if fallback_evidence is not None:
        fallback_evidence.update(provider="gemini", model=model, cache_hit=False)
        fallback_evidence.setdefault("attempts", [])
        fallback_evidence.setdefault("provider_attempts", 0)
    fallback_started = time.perf_counter()
    try:
        async with asyncio.timeout(remaining_timeout(deadline)):
            identity = None
            if cache_scope is not None and context:
                system_prompt, question_prompt = prompt_builder(question, entity_name, context)
                identity = answer_cache.make_identity(
                    mode=cache_scope[0], entity_id=cache_scope[1], entity_name=entity_name,
                    original_question=question.original_question, question=question.question,
                    context=context, system_prompt=system_prompt, question_prompt=question_prompt,
                    model=model,
                    game_date=game_date if game_date is not None else datetime.now(timezone.utc).date(),
                )
                cached = await answer_cache.lookup(session, identity)
                await session.commit()
                remaining_timeout(deadline)
                if cached is not None:
                    if fallback_evidence is not None:
                        for field in ("usage", "response_id", "model_version", "messages",
                                      "temperature", "max_output_tokens", "attempts"):
                            fallback_evidence.pop(field, None)
                        fallback_evidence.update(provider="answer_cache", model=model,
                                                 cache_hit=True, attempts=[], provider_attempts=0)
                    return cached, context, question_vector
            else:
                await session.commit()
            # No database transaction spans the blocking provider call.
            answer = await asyncio.to_thread(
                answerer, question, entity_name, context, model=model, deadline=deadline,
                **({"evidence": fallback_evidence} if fallback_evidence is not None else {}),
            )
            remaining_timeout(deadline)
            if identity is not None and type(answer["answer"]) is bool:
                await answer_cache.store(session, identity, answer["answer"], answer["explanation"])
                remaining_timeout(deadline)
                await session.commit()
    finally:
        if fallback_evidence is not None:
            fallback_evidence["duration_ms"] = (time.perf_counter() - fallback_started) * 1000
    return answer, context, question_vector
