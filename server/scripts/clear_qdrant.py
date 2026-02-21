import sys
import os
from dotenv import load_dotenv
import qdrant_client

# Add the server directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from server directory
load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))


def clear_qdrant():
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)

    collections = [
        "countries", "powiaty", "wojewodztwa", "us_states",
        "countries_questions", "powiaty_questions", "wojewodztwa_questions", "us_states_questions",
        "questions"
    ]

    for collection in collections:
        try:
            if client.collection_exists(collection):
                print(f"Deleting collection: {collection}...")
                client.delete_collection(collection_name=collection)
                print(f"Collection {collection} deleted.")
            else:
                print(f"Collection {collection} does not exist.")
        except Exception as e:
            print(f"Failed to delete collection {collection}: {e}")


if __name__ == "__main__":
    clear_qdrant()
