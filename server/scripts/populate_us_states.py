import asyncio
import sys
import os
import csv
import logging
import uuid
from dotenv import load_dotenv
from tqdm import tqdm
from sqlalchemy import select, func

# Add the server directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from server directory
load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

from db import AsyncSessionLocal
import qdrant
import qdrant.utils as qutils
from db.models.us_state import USState
from db.models.fragment import USStateFragment
from db.repositories.us_state import USStateRepository
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client.models import PointStruct


async def populate_us_states(session: AsyncSession):
    s_rep = USStateRepository(session)
    states = await s_rep.get_all()

    # Check if fragments are already populated
    frag_count_res = await session.execute(select(func.count(USStateFragment.id)))
    frag_count = frag_count_res.scalar()

    if states and frag_count > 0:
        print("US States and fragments already populated in DB.")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    csv_file = os.path.join(data_dir, "us_states.csv")

    if not os.path.exists(csv_file):
        logging.error(f"{csv_file} not found!")
        return

    # Read all rows first to use tqdm
    rows = []
    with open(csv_file, "r", encoding="utf8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} US States to process.")

    for row in tqdm(rows, desc="Populating US States"):
        name = row.get("name")
        md_filename = row.get("md_file")

        if not name or not md_filename:
            continue

        # Find or create state
        res = await session.execute(select(USState).where(USState.name == name))
        state = res.scalars().first()

        if not state:
            state = USState(name=name, code=None)
            session.add(state)
            await session.commit()
            await session.refresh(state)
        
        # Check if fragments exist for this state
        if frag_count > 0:
            f_res = await session.execute(select(func.count(USStateFragment.id)).where(USStateFragment.us_state_id == state.id))
            if f_res.scalar() > 0:
                continue

        # Read the markdown content
        md_rel_path = md_filename.replace("\\", "/")
        md_path = md_rel_path
        try:
            with open(md_path, encoding="utf8") as md_file:
                md_content = md_file.read()
        except FileNotFoundError:
            logging.warning(f"Markdown file not found for {state.name}: {md_path}")
            continue

        doc_fragments = qutils.split_document(md_content)
        embedding_model = qdrant.EMBEDDING_MODEL
        
        fragment_texts = [fragment.page_content for fragment in doc_fragments]
        embeddings = qutils.get_bulk_embedding(fragment_texts, embedding_model)

        points = []
        for i, fragment in enumerate(doc_fragments):
            # Save to Postgres
            db_fragment = USStateFragment(
                us_state_id=state.id,
                text=fragment.page_content,
                embedding=embeddings[i]
            )
            session.add(db_fragment)

            # Prepare for Qdrant
            point_id = str(uuid.uuid4())
            point = PointStruct(
                id=point_id,
                vector=embeddings[i],
                payload={
                    "us_state_id": state.id,
                    "us_state_name": state.name,
                    "fragment_text": fragment.page_content,
                },
            )
            points.append(point)

        await session.commit()

        if points:
            qutils.upsert_in_batches(
                client=qdrant.client,
                collection_name="us_states",
                points=points,
                batch_size=50,
                max_retries=3
            )

    print("US States population finished.")


async def main():
    print("Starting US States population...")
    async with AsyncSessionLocal() as session:
        await qdrant.init_qdrant(session)
        try:
            await populate_us_states(session)
            print("US States population completed successfully.")
        except Exception as e:
            print(f"An error occurred during US States population: {e}")


if __name__ == "__main__":
    asyncio.run(main())
