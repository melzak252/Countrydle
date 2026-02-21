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
from db.models import Country, CountryFragment
from db.repositories.country import CountryRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def populate_countries(session: AsyncSession):
    c_rep = CountryRepository(session)
    countries = await c_rep.get_all_countries()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    csv_file = os.path.join(data_dir, "countries.csv")

    if not os.path.exists(csv_file):
        logging.error(f"{csv_file} not found!")
        return

    # Read all rows first to use tqdm
    rows = []
    with open(csv_file, "r", encoding="utf8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} countries to process.")

    for row in tqdm(rows, desc="Populating Countries"):
        name = row.get("name")
        md_filename = row.get("md_file")

        if not name or not md_filename:
            continue

        # Find or create country
        res = await session.execute(select(Country).where(Country.name == name))
        country = res.scalars().first()

        if not country:
            md_rel_path = md_filename.replace("\\", "/")
            country = Country(
                name=name,
                official_name=name,
                wiki="",
                md_file=md_rel_path,
            )
            session.add(country)
            await session.commit()
            await session.refresh(country)
        
        # Check if fragments exist for this country
        f_res = await session.execute(select(func.count(CountryFragment.id)).where(CountryFragment.country_id == country.id))
        if f_res.scalar() > 0:
            continue

        print(f"Processing fragments for {name}...")


        # Find or create country
        res = await session.execute(select(Country).where(Country.name == name))
        country = res.scalars().first()

        if not country:
            md_rel_path = md_filename.replace("\\", "/")
            country = Country(
                name=name,
                official_name=name,
                wiki="",
                md_file=md_rel_path,
            )
            session.add(country)
            await session.commit()
            await session.refresh(country)
        
        # Check if fragments exist for this country
        f_res = await session.execute(select(func.count(CountryFragment.id)).where(CountryFragment.country_id == country.id))
        if f_res.scalar() > 0:
            continue

        # Read the markdown content
        md_path = country.md_file
        try:
            with open(md_path, encoding="utf8") as md_file:
                md_content = md_file.read()
        except FileNotFoundError:
            logging.warning(f"Markdown file not found for {country.name}: {md_path}")
            continue

        doc_fragments = qutils.split_document(md_content)
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        
        fragment_texts = [fragment.page_content for fragment in doc_fragments]
        embeddings = qutils.get_bulk_embedding(fragment_texts, embedding_model)

        for i, fragment in enumerate(doc_fragments):
            # Save to Postgres
            db_fragment = CountryFragment(
                country_id=country.id,
                text=fragment.page_content,
                embedding=embeddings[i]
            )
            session.add(db_fragment)

        await session.commit()

    print("Countries population finished.")


async def main():
    print("Starting database population...")
    async with AsyncSessionLocal() as session:
        try:
            await populate_countries(session)
            print("Database population completed successfully.")
        except Exception as e:
            print(f"An error occurred during database population: {e}")


if __name__ == "__main__":
    asyncio.run(main())
