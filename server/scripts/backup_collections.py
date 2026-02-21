import sys
import os
from dotenv import load_dotenv
import qdrant_client

# Add the server directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from server directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

def create_backups():
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = qdrant_client.QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    collections = ["countries", "powiaty", "wojewodztwa", "us_states", "questions"]
    
    for collection in collections:
        try:
            print(f"Creating snapshot for collection: {collection}...")
            # Check if collection exists first
            if client.collection_exists(collection):
                snapshot = client.create_snapshot(collection_name=collection)
                print(f"Snapshot created successfully: {snapshot.name}")
            else:
                print(f"Collection {collection} does not exist.")
        except Exception as e:
            print(f"Failed to create snapshot for {collection}: {e}")

if __name__ == "__main__":
    create_backups()
