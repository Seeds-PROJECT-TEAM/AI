import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
URI  = os.getenv("AURA_URI")
USER = os.getenv("AURA_USER")
PASS = os.getenv("AURA_PASS")

driver = GraphDatabase.driver(URI, auth=(USER, PASS))  # TLS 자동

def run_cypher(query: str, params=None):
    with driver.session() as s:
        return s.run(query, params or {}).data()