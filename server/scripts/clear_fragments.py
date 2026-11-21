import asyncio
import sys
import os
from dotenv import load_dotenv
from sqlalchemy import text

# Add the server directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from server directory
load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

from db import AsyncSessionLocal
import qdrant

async def clear_fragments():
    print("Starting fragment cleanup...")
    
    # 1. Clear Postgres tables
    async with AsyncSessionLocal() as session:
        truncate_statements = {
            "country_fragments": text("TRUNCATE TABLE country_fragments CASCADE"),
            "powiat_fragments": text("TRUNCATE TABLE powiat_fragments CASCADE"),
            "wojewodztwo_fragments": text("TRUNCATE TABLE wojewodztwo_fragments CASCADE"),
            "us_state_fragments": text("TRUNCATE TABLE us_state_fragments CASCADE"),
        }

        for table, stmt in truncate_statements.items():
            print(f"Clearing Postgres table: {table}...")
            try:
                await session.execute(stmt)
                await session.commit()
                print(f"Successfully cleared {table}.")
            except Exception as e:
                print(f"Error clearing {table}: {e}")
                await session.rollback()

    # 2. Clear Qdrant collections
    print("Clearing Qdrant collections...")
    collections = [
        "countries",
        "powiaty",
        "wojewodztwa",
        "us_states"
    ]
    
    for collection in collections:
        print(f"Deleting and recreating Qdrant collection: {collection}...")
        try:
            if qdrant.client.collection_exists(collection):
                qdrant.client.delete_collection(collection)
                print(f"Deleted {collection}.")
            
            # Recreate with correct vector size (1536 for text-embedding-3-small)
            qdrant.client.create_collection(
                collection_name=collection,
                vectors_config=qdrant.VectorParams(
                    size=1536, 
                    distance=qdrant.Distance.COSINE
                ),
            )
            print(f"Recreated {collection}.")
        except Exception as e:
            print(f"Error handling Qdrant collection {collection}: {e}")

    print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(clear_fragments())
