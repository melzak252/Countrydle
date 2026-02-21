import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import List

from db.models import Country
from db.models.fragment import CountryFragment, PowiatFragment, WojewodztwoFragment, USStateFragment
from db.repositories.country import CountryRepository
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import Distance, PointStruct, VectorParams, IntegerIndexParams
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .utils import get_points, upsert_in_batches

load_dotenv()

EMBEDDING_SIZE = int(os.getenv("EMBEDDING_SIZE", "1536"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Collection names
COLLECTIONS = {
    "countries": "countries",
    "powiaty": "powiaty",
    "wojewodztwa": "wojewodztwa",
    "us_states": "us_states",
    "countries_questions": "countries_questions",
    "powiaty_questions": "powiaty_questions",
    "wojewodztwa_questions": "wojewodztwa_questions",
    "us_states_questions": "us_states_questions",
}

client: QdrantClient = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


async def sync_from_postgres(session: AsyncSession, collection_name: str):
    """Syncs data from Postgres to Qdrant if collection is empty."""
    try:
        info = client.get_collection(collection_name)
        if info.points_count > 0:
            return
    except Exception as e:
        logging.error(f"Error checking collection {collection_name}: {e}")
        return

    logging.info(f"Collection {collection_name} is empty. Syncing from Postgres...")
    
    points = []
    if collection_name == "countries":
        res = await session.execute(select(CountryFragment))
        fragments = res.scalars().all()
        for f in fragments:
            points.append(PointStruct(id=str(uuid.uuid4()), vector=f.embedding, payload={"country_id": f.country_id, "fragment_text": f.text}))
    elif collection_name == "powiaty":
        res = await session.execute(select(PowiatFragment))
        fragments = res.scalars().all()
        for f in fragments:
            points.append(PointStruct(id=str(uuid.uuid4()), vector=f.embedding, payload={"powiat_id": f.powiat_id, "fragment_text": f.text}))
    elif collection_name == "wojewodztwa":
        res = await session.execute(select(WojewodztwoFragment))
        fragments = res.scalars().all()
        for f in fragments:
            points.append(PointStruct(id=str(uuid.uuid4()), vector=f.embedding, payload={"wojewodztwo_id": f.wojewodztwo_id, "fragment_text": f.text}))
    elif collection_name == "us_states":
        res = await session.execute(select(USStateFragment))
        fragments = res.scalars().all()
        for f in fragments:
            points.append(PointStruct(id=str(uuid.uuid4()), vector=f.embedding, payload={"us_state_id": f.us_state_id, "fragment_text": f.text}))

    if points:
        upsert_in_batches(client, collection_name, points, batch_size=100)
        logging.info(f"Successfully synced {len(points)} points to {collection_name}")


async def init_qdrant(session: AsyncSession):
    logging.info("Initializing Qdrant collections...")
    for name in COLLECTIONS.values():
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
            )
            
            # Add payload indexes
            field_name = ""
            if name.endswith("_questions"):
                if name.startswith("countries"): field_name = "country_id"
                elif name.startswith("powiaty"): field_name = "powiat_id"
                elif name.startswith("wojewodztwa"): field_name = "wojewodztwo_id"
                elif name.startswith("us_states"): field_name = "us_state_id"
                
                if field_name:
                    client.create_payload_index(collection_name=name, field_name=field_name, field_schema="integer")
            else:
                if name == "countries": field_name = "country_id"
                elif name == "powiaty": field_name = "powiat_id"
                elif name == "wojewodztwa": field_name = "wojewodztwo_id"
                elif name == "us_states": field_name = "us_state_id"

                if field_name:
                    client.create_payload_index(
                        collection_name=name,
                        field_name=field_name,
                        field_schema=IntegerIndexParams(type="integer", is_principal=True, lookup=True, range=False),
                    )
        
        # Sync data if needed (only for main fragment collections)
        if name in ["countries", "powiaty", "wojewodztwa", "us_states"]:
            await sync_from_postgres(session, name)

    if not client.collection_exists("questions"):
        client.create_collection(
            collection_name="questions",
            vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
        )


def get_qdrant_client():
    return client


def close_qdrant_client():
    global client
    if client:
        client.close()
