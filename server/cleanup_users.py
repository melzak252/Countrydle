import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Use internal docker DB URL
DB_URL = "postgresql+asyncpg://postgres:root@db:5432/guess_country"

async def main():
    print(f"Connecting to DB: {DB_URL}")
    try:
        engine = create_async_engine(DB_URL)
        async with engine.connect() as conn:
            patterns = ['test_%', 'pytest_%', 'guess_c_%', 'ask_q_%', 'guest_%']
            
            print("Cleaning up test users...")
            total_deleted = 0
            
            for p in patterns:
                # Count first
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM users WHERE username LIKE :pattern"),
                    {"pattern": p},
                )
                count = result.scalar()
                
                if count > 0:
                    print(f"Found {count} users matching pattern '{p}'")
                    # Delete
                    await conn.execute(
                        text("DELETE FROM users WHERE username LIKE :pattern"),
                        {"pattern": p},
                    )
                    await conn.commit()
                    print(f"Deleted users matching '{p}'")
                    total_deleted += count
                else:
                    print(f"No users found for pattern '{p}'")
            
            print(f"\nTotal users deleted: {total_deleted}")
                
        await engine.dispose()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
