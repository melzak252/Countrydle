import os
from typing import List, Dict, Any
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GAME_NODE_LABELS = {
    "countries": "CountryNode",
    "powiaty": "PowiatNode",
    "us_states": "USStateNode",
    "wojewodztwa": "WojewodztwoNode"
}

class GraphRAGManager:
    def __init__(self):
        self.graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def get_qa_chain(self, entity_name: str, game_key: str):
        """
        Returns a Cypher QA chain strictly filtered by the game type and entity.
        """
        node_label = GAME_NODE_LABELS.get(game_key, "RootEntity")
        
        # Use a regular string and .format() or just manual replacement to avoid brace hell
        entity_filter_template = """
        You are an expert at generating Neo4j Cypher queries for the Countrydle game suite.
        The user is asking a question about a specific entity named '{entity_name}' in the '{game_key}' game.
        
        CRITICAL RULES:
        1. You MUST only query nodes with the label '{node_label}'.
        2. You MUST only query nodes and relationships where the 'entity' property is EXACTLY '{entity_name}'.
        3. Every MATCH clause should include a filter for the entity property.
        4. Use the 'original_id' property of nodes to match names/values (e.g., n.original_id = 'Central Europe').
        
        Example:
        MATCH (n:{node_label} {{entity: '{entity_name}'}})-[r {{entity: '{entity_name}'}}]->(m:{node_label} {{entity: '{entity_name}'}})
        WHERE m.original_id CONTAINS 'Warsaw'
        RETURN m.original_id
        
        Schema:
        {schema}
        
        Question: {question}
        Cypher Query:
        """.replace("{entity_name}", entity_name).replace("{game_key}", game_key).replace("{node_label}", node_label)
        
        prompt = PromptTemplate(
            template=entity_filter_template,
            input_variables=["schema", "question"]
        )
        
        print(f"Schema for {game_key}: {self.graph.schema}")
        
        return GraphCypherQAChain.from_llm(
            llm=self.llm,
            graph=self.graph,
            verbose=True,
            allow_dangerous_requests=True,
            cypher_prompt=prompt
        )

    def query_graph(self, question: str, entity_name: str, game_key: str) -> str:
        """
        Queries the isolated GraphRAG for a specific game and entity.
        """
        try:
            chain = self.get_qa_chain(entity_name, game_key)
            full_question = f"Regarding the entity '{entity_name}', {question}"
            
            response = chain.invoke({"query": full_question})
            return response.get("result", "I couldn't find that information in the knowledge graph.")
        except Exception as e:
            print(f"GraphRAG Error for {game_key}/{entity_name}: {e}")
            return "Error querying the knowledge graph."

graph_manager = GraphRAGManager()
