import os
import json
import glob
import argparse
from openai import OpenAI
from .kuzu_client import get_connection
from .schema import init_schema

client = OpenAI()

def extract_data_from_md(content, entity_type):
    """
    Uses LLM to extract structured data from markdown content.
    """
    system_prompt = f"""
    You are a data extractor for a geography graph database.
    Extract structured information from the following markdown content about a {entity_type}.
    
    Extract:
    1. Basic properties: capital, population (INT64), area (DOUBLE).
    2. Neighbors: A list of names of other {entity_type}s that border this one.
    3. Concepts: A comprehensive list of identifying features and relationships. 
       Look for EVERYTHING that could be used to distinguish or group this {entity_type} with others:
       - Geographic: Continents, Regions, Sub-regions, Time Zones, Climate Zones.
       - Physical: Shared Rivers, Lakes, Seas, Oceans, Mountain Ranges, Deserts.
       - Political: Organizations (UN, EU, NATO, G7, ASEAN, AU, etc.), Trading Blocs, Government Type.
       - Cultural: Official Languages, Common Languages, Major Religions, Ethnic Groups.
       - Economic: Currencies, Major Exports, Income Level (World Bank).
       - Infrastructure: Driving Side (Left/Right), Calling Code, Internet TLD.
       - Historical: Former Empires, Colonial History, Independence Year.
       - Landmarks: World Heritage Sites, Famous Natural or Man-made Landmarks.
       
       For each concept, provide:
       - name: The specific name (e.g., "UTC+1", "Atlantic Ocean", "Roman Catholicism", "Right-hand traffic").
       - category: The broad category (e.g., "Time Zone", "Ocean", "Religion", "Driving Side").
       - relationship: A descriptive verb phrase (e.g., "Located In", "Borders", "Practices", "Drives On", "Member Of").

    Output format: JSON
    {{
        "name": "Name of the {entity_type}",
        "properties": {{
            "capital": "...",
            "population": 123456,
            "area": 123.45
        }},
        "neighbors": ["Neighbor 1", "Neighbor 2"],
        "concepts": [
            {{"name": "...", "category": "...", "relationship": "..."}}
        ]
    }}
    """
    
    model = os.getenv("QUIZ_MODEL", "gpt-4-turbo-preview")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content[:10000]} # Limit content length for LLM
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def populate_from_folder(folder_path, entity_type):
    """
    Processes a folder of .md files and populates KuzuDB.
    """
    conn = get_connection()
    files = glob.glob(os.path.join(folder_path, "*.md"))
    
    if not files:
        print(f"No .md files found in {folder_path}")
        return

    all_data = []
    
    print(f"Processing {len(files)} files...")
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = extract_data_from_md(content, entity_type)
                all_data.append(data)
                print(f"Extracted data for {data.get('name', 'Unknown')}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Pass 1: Create Nodes
    print("Creating nodes...")
    for data in all_data:
        name = data.get('name', '').replace("'", "''")
        if not name: continue
        
        props = data.get('properties', {})
        capital = props.get('capital', '').replace("'", "''")
        pop = props.get('population', 0)
        # Ensure pop is int
        try: pop = int(pop)
        except: pop = 0
        
        area = props.get('area', 0.0)
        # Ensure area is float
        try: area = float(area)
        except: area = 0.0
        
        # Create Country/Entity node
        try:
            conn.execute(f"MERGE (n:{entity_type} {{name: '{name}'}}) ON CREATE SET n.capital = '{capital}', n.population = {pop}, n.area = {area}")
        except Exception as e:
            print(f"Error creating node {name}: {e}")
        
        # Create Concept nodes
        for concept in data.get('concepts', []):
            c_name = concept.get('name', '').replace("'", "''")
            c_cat = concept.get('category', '').replace("'", "''")
            if not c_name: continue
            try:
                conn.execute(f"MERGE (c:Concept {{name: '{c_name}'}}) ON CREATE SET c.category = '{c_cat}'")
            except Exception as e:
                print(f"Error creating concept {c_name}: {e}")

    # Pass 2: Create Relationships
    print("Creating relationships...")
    for data in all_data:
        name = data.get('name', '').replace("'", "''")
        if not name: continue
        
        # Borders
        for neighbor in data.get('neighbors', []):
            n_name = neighbor.replace("'", "''")
            try:
                # Note: BORDERS is the table name in our schema
                conn.execute(f"MATCH (a:{entity_type} {{name: '{name}'}}), (b:{entity_type} {{name: '{n_name}'}}) MERGE (a)-[:BORDERS]->(b)")
            except Exception as e:
                # Neighbor might not exist yet or other error
                pass

        # Concepts
        for concept in data.get('concepts', []):
            c_name = concept.get('name', '').replace("'", "''")
            rel_desc = concept.get('relationship', '').replace("'", "''")
            if not c_name: continue
            try:
                conn.execute(f"MATCH (a:{entity_type} {{name: '{name}'}}), (c:Concept {{name: '{c_name}'}}) MERGE (a)-[:HAS_CONCEPT {{relationship: '{rel_desc}'}}]->(c)")
            except Exception as e:
                print(f"Error creating rel between {name} and {c_name}: {e}")

    print("Population complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate KuzuDB from markdown files.")
    parser.add_argument("folder", help="Path to the folder containing .md files")
    parser.add_argument("--type", default="Country", help="Entity type (Country, USState, etc.)")
    parser.add_argument("--init", action="store_true", help="Initialize schema before population")
    
    args = parser.parse_args()
    
    if args.init:
        init_schema()
        
    populate_from_folder(args.folder, args.type)
