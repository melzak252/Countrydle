import time
from typing import List, Tuple, Any
from dataclasses import dataclass

from db.models import CountrydleDay
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
    GroupsResult,
    PointGroup,
    ScoredPoint,
)
from sqlalchemy.ext.asyncio import AsyncSession
import qdrant

from qdrant_client.models import PointStruct

from .vectorize import get_embedding, get_bulk_embedding


@dataclass
class Fragment:
    text: str


def split_document(content: str) -> List[Document]:
    # Use RecursiveCharacterTextSplitter to split the document into fragments per 300 tokens
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    fragments = text_splitter.create_documents([content])
    return fragments


def get_points(client: QdrantClient, collection_name: str, ids: list[int]):
    try:
        # Try to get the point by its ID
        points = client.retrieve(collection_name=collection_name, ids=ids)
        return points
    except UnexpectedResponse:
        return []


def search_matches(
    collection_name: str,
    query_vector: list,
    filter_key: str,
    filter_value: int,
    limit: int = 5,
) -> List[ScoredPoint]:
    search_result: GroupsResult = qdrant.client.query_points_groups(
        collection_name=collection_name,
        query=query_vector,  # Use the query vector to search for similar vectors
        group_by=filter_key,  # Group results by filter_key
        group_size=limit,  # Return up to 5 points per group
        limit=1,  # Limit to 3 groups (you can adjust as needed)
        query_filter=Filter(
            must=[
                FieldCondition(
                    key=filter_key,
                    match=MatchValue(value=filter_value),  # Strict match
                )
            ]
        ),
        with_payload=True,
    )
    if not search_result.groups:
        return []
    group, *_ = search_result.groups
    return group.hits


async def get_fragments_matching_question(
    question: str,
    filter_key: str,
    filter_value: int,
    collection_name: str,
    session: AsyncSession,
    limit: int = 3,
) -> Tuple[list[Fragment], List[float]]:
    query = question
    query_vector = get_embedding(query, qdrant.EMBEDDING_MODEL)

    points: List[ScoredPoint] = search_matches(
        collection_name=collection_name,
        query_vector=query_vector,
        filter_key=filter_key,
        filter_value=filter_value,
        limit=limit,
    )

    if not points:
        return [], query_vector

    # Collect all IDs to fetch (original and next)
    ids_to_fetch = set()
    for point in points:
        point_id = int(point.id)
        ids_to_fetch.add(point_id)
        ids_to_fetch.add(point_id + 1)

    # Fetch all these points from Qdrant
    all_points = get_points(qdrant.client, collection_name, list(ids_to_fetch))

    # Filter points to ensure they belong to the same entity and are valid
    valid_points = []
    for p in all_points:
        if p.payload and p.payload.get(filter_key) == filter_value:
            valid_points.append(p)

    # Sort by ID to maintain document order
    valid_points.sort(key=lambda x: int(x.id))

    fragments = []
    for point in valid_points:
        if point.payload:
            text = point.payload.get("fragment_text")
            if text:
                fragments.append(Fragment(text=text))

    return fragments, query_vector


async def add_question_to_qdrant(
    question: Any,
    vector: List[float],
    filter_key: str,
    filter_value: int,
    collection_name: str = "questions",
):
    print(f"Adding question ID {question.id} to collection '{collection_name}'...")
    point = PointStruct(
        id=question.id,
        vector=vector,
        payload={
            filter_key: filter_value,
            "question_text": question.question,
            "answer": question.answer,
            "explanation": question.explanation,
        },
    )
    qdrant.client.upsert(collection_name=collection_name, points=[point])
    print(f"Successfully added question ID {question.id} to '{collection_name}'.")


def upsert_in_batches(
    client: QdrantClient,
    collection_name: str,
    points: List[PointStruct],
    batch_size: int = 50,
    max_retries: int = 3,
):
    """
    Upserts points into Qdrant in batches with retry logic.
    """
    total_points = len(points)
    print(
        f"Starting upsert of {total_points} points into collection '{collection_name}' in batches of {batch_size}..."
    )

    for i in range(0, total_points, batch_size):
        batch = points[i : i + batch_size]
        current_batch_num = i // batch_size + 1
        total_batches = (total_points + batch_size - 1) // batch_size

        for attempt in range(max_retries):
            try:
                client.upsert(collection_name=collection_name, points=batch)
                print(
                    f"Successfully upserted batch {current_batch_num}/{total_batches} ({len(batch)} points) into '{collection_name}'."
                )
                break  # Success, move to next batch
            except Exception as e:
                print(
                    f"Upsert failed for batch {current_batch_num}/{total_batches} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    print(
                        f"Failed to upsert batch starting at index {i} after {max_retries} attempts."
                    )
                    # Optionally raise the exception if you want to stop the whole process
                    # raise e
                time.sleep(1)  # Wait a bit before retrying

    print(
        f"Completed upsert of {total_points} points into collection '{collection_name}'."
    )
