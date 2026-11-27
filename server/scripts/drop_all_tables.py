import asyncio
import os
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Add the server directory to sys.path to allow imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

async def drop_all_tables():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Dropping all tables...")
        metadata = MetaData()
        await conn.run_sync(metadata.reflect)
        await conn.run_sync(metadata.drop_all)
        print("All tables dropped.")

if __name__ == "__main__":
    asyncio.run(drop_all_tables())
