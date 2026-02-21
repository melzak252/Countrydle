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
from db.models.powiat import Powiat
from db.models.fragment import PowiatFragment
from db.repositories.powiatdle import PowiatRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def populate_powiaty(session: AsyncSession):
    p_rep = PowiatRepository(session)
    powiaty = await p_rep.get_all()

    # Check if fragments are already populated
    frag_count_res = await session.execute(select(func.count(PowiatFragment.id)))
    frag_count = frag_count_res.scalar()

    if powiaty and frag_count > 0:
        print("Powiaty and fragments already populated in DB.")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    csv_file = os.path.join(data_dir, "powiaty.csv")

    if not os.path.exists(csv_file):
        logging.error(f"{csv_file} not found!")
        return

    # Read all rows first to use tqdm
    rows = []
    with open(csv_file, "r", encoding="utf8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} powiaty to process.")

    for row in tqdm(rows, desc="Populating Powiaty"):
        nazwa = row.get("name")
        md_filename = row.get("md_file")

        if not nazwa or not md_filename:
            continue

        # Find or create powiat
        res = await session.execute(select(Powiat).where(Powiat.nazwa == nazwa))
        powiat = res.scalars().first()

        if not powiat:
            powiat = Powiat(nazwa=nazwa)
            session.add(powiat)
            await session.commit()
            await session.refresh(powiat)
        
        # Check if fragments exist for this powiat
        f_res = await session.execute(select(func.count(PowiatFragment.id)).where(PowiatFragment.powiat_id == powiat.id))
        if f_res.scalar() > 0:
            continue

        # Read the markdown content
        md_rel_path = md_filename.replace("\\", "/")
        md_path = md_rel_path
        try:
            with open(md_path, encoding="utf8") as md_file:
                md_content = md_file.read()
        except FileNotFoundError:
            logging.warning(f"Markdown file not found for {powiat.nazwa}: {md_path}")
            continue

        doc_fragments = qutils.split_document(md_content)
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        
        fragment_texts = [fragment.page_content for fragment in doc_fragments]
        embeddings = qutils.get_bulk_embedding(fragment_texts, embedding_model)

        for i, fragment in enumerate(doc_fragments):
            # Save to Postgres
            db_fragment = PowiatFragment(
                powiat_id=powiat.id,
                text=fragment.page_content,
                embedding=embeddings[i]
            )
            session.add(db_fragment)

        await session.commit()

    print("Powiaty population finished.")


async def main():
    print("Starting powiaty population...")
    async with AsyncSessionLocal() as session:
        try:
            await populate_powiaty(session)
            print("Powiaty population completed successfully.")
        except Exception as e:
            print(f"An error occurred during powiaty population: {e}")


if __name__ == "__main__":
    asyncio.run(main())
