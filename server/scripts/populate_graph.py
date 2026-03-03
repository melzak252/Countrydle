import os
import json
import asyncio
import argparse
import warnings
import logging
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_neo4j import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Silence Pydantic serialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*PydanticSerializationUnexpectedValue.*")
logging.getLogger("pydantic").setLevel(logging.ERROR)

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini" 
CONCURRENCY_LIMIT = 5 # Number of entities to process in parallel

# Initialize Neo4j
print(f"Connecting to Neo4j at {NEO4J_URI}...")
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD
)

# Initialize LLM
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
transformer = LLMGraphTransformer(llm=llm)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)

GAME_CONFIG = {
    "countries": {"dir": "data/countries", "label": "Country", "node_label": "CountryNode"},
    "powiaty": {"dir": "data/counties", "label": "Powiat", "node_label": "PowiatNode"},
    "us_states": {"dir": "data/us_states", "label": "USState", "node_label": "USStateNode"},
    "wojewodztwa": {"dir": "data/voivodeships", "label": "Wojewodztwo", "node_label": "WojewodztwoNode"}
}

def export_to_json(game_key: str):
    game_label = GAME_CONFIG[game_key]["label"]
    output_file = f"{game_key}_graph_backup.json"
    print(f"\nExporting {game_label} graph to {output_file}...")
    
    query = """
    MATCH (n {game: $game})
    OPTIONAL MATCH (n)-[r {game: $game}]->(m)
    RETURN n, r, m
    """
    results = graph.query(query, {"game": game_label})
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

async def check_entity_exists(entity_name: str, game_label: str) -> bool:
    query = "MATCH (n:RootEntity {name: $name, game: $game}) RETURN count(n) > 0 as exists"
    result = await asyncio.to_thread(graph.query, query, {"name": entity_name, "game": game_label})
    return result[0]['exists'] if result else False

async def process_entity(file_path: str, entity_name: str, game_label: str, node_label: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        # Check if already exists
        if await check_entity_exists(entity_name, game_label):
            print(f"  Skipping {entity_name} (already exists in Neo4j)")
            return

        print(f"  Processing {entity_name}...")
        try:
            loader = UnstructuredMarkdownLoader(file_path)
            raw_docs = await asyncio.to_thread(loader.load)
            docs = text_splitter.split_documents(raw_docs)
            
            for doc in docs:
                doc.metadata["entity"] = entity_name
                doc.metadata["game"] = game_label
            
            batch_size = 5
            for i in range(0, len(docs), batch_size):
                batch = docs[i:i+batch_size]
                graph_docs = await asyncio.to_thread(transformer.convert_to_graph_documents, batch)
                
                for g_doc in graph_docs:
                    for node in g_doc.nodes:
                        original_id = node.id
                        node.id = f"{entity_name}:{original_id}"
                        node.properties["entity"] = entity_name
                        node.properties["game"] = game_label
                        node.properties["original_id"] = original_id
                        node.type = node_label
                    
                    for rel in g_doc.relationships:
                        rel.source.id = f"{entity_name}:{rel.source.id}"
                        rel.target.id = f"{entity_name}:{rel.target.id}"
                        rel.properties["entity"] = entity_name
                        rel.properties["game"] = game_label
                
                await asyncio.to_thread(graph.add_graph_documents, graph_docs, baseEntityLabel=node_label)
                
                link_query = f"""
                MATCH (n {{entity: $entity, game: $game}})
                WHERE n:{node_label} OR n:__Entity__
                MERGE (root:RootEntity {{name: $entity, game: $game}})
                SET root:{node_label}
                WITH n, root
                WHERE n <> root
                MERGE (root)-[:HAS_INFORMATION {{entity: $entity, game: $game}}]->(n)
                """
                await asyncio.to_thread(graph.query, link_query, {"entity": entity_name, "game": game_label})
            
            print(f"  Finished {entity_name}.")
        except Exception as e:
            print(f"  Error processing {entity_name}: {e}")

async def process_game(game_key: str, semaphore: asyncio.Semaphore):
    config = GAME_CONFIG[game_key]
    directory_path = config["dir"]
    game_label = config["label"]
    node_label = config["node_label"]

    print(f"\n--- Populating GraphRAG for: {game_label} ---")
    
    if not os.path.exists(directory_path):
        print(f"Directory {directory_path} does not exist. Skipping.")
        return

    files = [f for f in os.listdir(directory_path) if f.endswith(".md")]
    
    tasks = []
    for filename in files:
        file_path = os.path.join(directory_path, filename)
        entity_name = filename.replace(".md", "").replace("_", " ")
        tasks.append(process_entity(file_path, entity_name, game_label, node_label, semaphore))

    await asyncio.gather(*tasks)
    export_to_json(game_key)

async def main():
    parser = argparse.ArgumentParser(description="Populate Neo4j GraphRAG for Countrydle games.")
    parser.add_argument("--game", choices=["countries", "powiaty", "us_states", "wojewodztwa", "all"], default="all")
    parser.add_argument("--entities", nargs="+", help="Specific entities to process (e.g., Poland Germany)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY_LIMIT, help="Number of entities to process in parallel")
    args = parser.parse_args()

    semaphore = asyncio.Semaphore(args.concurrency)

    try:
        await asyncio.to_thread(graph.query, "RETURN 1")
    except Exception as e:
        print(f"Neo4j connection failed: {e}")
        return

    if args.game == "all":
        for game_key in GAME_CONFIG.keys():
            try:
                await process_game(game_key, semaphore)
            except Exception as e:
                print(f"Failed to process game {game_key}: {e}")
    else:
        if args.entities:
            config = GAME_CONFIG[args.game]
            directory_path = config["dir"]
            game_label = config["label"]
            node_label = config["node_label"]
            
            print(f"\n--- Populating GraphRAG for specific {game_label} entities ---")
            tasks = []
            for entity in args.entities:
                file_path = os.path.join(directory_path, f"{entity}.md")
                if os.path.exists(file_path):
                    tasks.append(process_entity(file_path, entity, game_label, node_label, semaphore))
                else:
                    print(f"File {file_path} not found.")
            await asyncio.gather(*tasks)
            export_to_json(args.game)
        else:
            await process_game(args.game, semaphore)
    
    print("\nNeo4j GraphRAG Population Complete!")

if __name__ == "__main__":
    asyncio.run(main())
