"""Quick diagnostic script to test the actual system"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from config import config
from rag_system import RAGSystem

def test_real_query():
    """Test a real query against the system"""
    try:
        print("Initializing RAG system...")
        rag = RAGSystem(config)

        print("\nTesting query: 'What is MCP?'")
        response, sources = rag.query("What is MCP?")

        print(f"\nResponse: {response}")
        print(f"\nSources: {sources}")
        print("\n✓ Query succeeded!")

    except Exception as e:
        print(f"\n✗ Query failed with error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_query()
