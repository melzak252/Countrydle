import asyncio
import time
from typing import Any, Callable

from qdrant.utils import get_fragments_matching_question
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
    evidence: dict | None = None,
) -> tuple[dict, str, list[float]]:
    """Retrieve fresh evidence and answer within one bounded daily request."""
    deadline = time.monotonic() + 60.0
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
                if time.monotonic() >= deadline:
                    raise TimeoutError("Daily fallback deadline exhausted") from exc
                print(f"Warning: Vector retrieval failed ({exc}); answering with general knowledge.")
    finally:
        if evidence is not None:
            evidence["retrieval_duration_ms"] = (time.perf_counter() - retrieval_started) * 1000

    context = "\n[ ... ]\n".join(fragment.text for fragment in fragments) if fragments else ""
    fallback_evidence = evidence.setdefault("fallback", {}) if evidence is not None else None
    fallback_started = time.perf_counter()
    try:
        async with asyncio.timeout(remaining_timeout(deadline)):
            answer = await asyncio.to_thread(
                answerer,
                question,
                entity_name,
                context,
                cache_scope=cache_scope,
                deadline=deadline,
                **({"evidence": fallback_evidence} if fallback_evidence is not None else {}),
            )
    finally:
        if fallback_evidence is not None:
            fallback_evidence["duration_ms"] = (time.perf_counter() - fallback_started) * 1000
    return answer, context, question_vector
