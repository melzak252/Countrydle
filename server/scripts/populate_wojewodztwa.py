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
import qdrant.utils as qutils
from db.models.wojewodztwo import Wojewodztwo
from db.models.fragment import WojewodztwoFragment
from db.repositories.wojewodztwo import WojewodztwoRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def populate_wojewodztwa(session: AsyncSession):
    w_rep = WojewodztwoRepository(session)
    wojewodztwa = await w_rep.get_all()

    # Check if fragments are already populated
    frag_count_res = await session.execute(select(func.count(WojewodztwoFragment.id)))
    frag_count = frag_count_res.scalar()

    if wojewodztwa and frag_count > 0:
        print("Wojewodztwa and fragments already populated in DB.")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    csv_file = os.path.join(data_dir, "wojewodztwa.csv")

    if not os.path.exists(csv_file):
        logging.error(f"{csv_file} not found!")
        return

    # Read all rows first to use tqdm
    rows = []
    with open(csv_file, "r", encoding="utf8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} wojewodztwa to process.")

    for row in tqdm(rows, desc="Populating Wojewodztwa"):
        nazwa = row.get("name")
        md_filename = row.get("md_file")

        if not nazwa or not md_filename:
            continue

        # Find or create wojewodztwo
        res = await session.execute(select(Wojewodztwo).where(Wojewodztwo.nazwa == nazwa))
        wojewodztwo = res.scalars().first()

        if not wojewodztwo:
            wojewodztwo = Wojewodztwo(nazwa=nazwa)
            session.add(wojewodztwo)
            await session.commit()
            await session.refresh(wojewodztwo)
        
        # Check if fragments exist for this wojewodztwo
        if frag_count > 0:
            f_res = await session.execute(select(func.count(WojewodztwoFragment.id)).where(WojewodztwoFragment.wojewodztwo_id == wojewodztwo.id))
            if f_res.scalar() > 0:
                continue

        # Read the markdown content
        md_rel_path = md_filename.replace("\\", "/")
        md_path = md_rel_path
        try:
            with open(md_path, encoding="utf8") as md_file:
                md_content = md_file.read()
        except FileNotFoundError:
            logging.warning(f"Markdown file not found for {wojewodztwo.nazwa}: {md_path}")
            continue

        doc_fragments = qutils.split_document(md_content)
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        
        fragment_texts = [fragment.page_content for fragment in doc_fragments]
        embeddings = qutils.get_bulk_embedding(fragment_texts, embedding_model)

        for i, fragment in enumerate(doc_fragments):
            # Save to Postgres
            db_fragment = WojewodztwoFragment(
                wojewodztwo_id=wojewodztwo.id,
                text=fragment.page_content,
                embedding=embeddings[i]
            )
            session.add(db_fragment)

        await session.commit()

    print("Wojewodztwa population finished.")


async def main():
    print("Starting wojewodztwa population...")
    async with AsyncSessionLocal() as session:
        try:
            await populate_wojewodztwa(session)
            print("Wojewodztwa population completed successfully.")
        except Exception as e:
            print(f"An error occurred during wojewodztwa population: {e}")


if __name__ == "__main__":
    asyncio.run(main())
