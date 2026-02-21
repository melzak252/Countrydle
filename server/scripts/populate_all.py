import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the server directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from server directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from db import AsyncSessionLocal

# Import from sibling scripts
try:
    from populate_countries import populate_countries
    from populate_powiaty import populate_powiaty
    from populate_wojewodztwa import populate_wojewodztwa
    from populate_us_states import populate_us_states
except ImportError:
    # Fallback for when running as a module or different context
    from scripts.populate_countries import populate_countries
    from scripts.populate_powiaty import populate_powiaty
    from scripts.populate_wojewodztwa import populate_wojewodztwa
    from scripts.populate_us_states import populate_us_states

async def main():
    print("Starting full database population (Postgres only)...")
    async with AsyncSessionLocal() as session:
        try:
            print("Populating countries...")
            await populate_countries(session)
            print("Countries populated.")
            
            print("Populating powiaty...")
            await populate_powiaty(session)
            print("Powiaty populated.")
 
            print("Populating wojewodztwa...")
            await populate_wojewodztwa(session)
            print("Wojewodztwa populated.")

            print("Populating US States...")
            await populate_us_states(session)
            print("US States populated.")
            
            print("Full database population completed successfully.")
        except Exception as e:
            print(f"An error occurred during population: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
