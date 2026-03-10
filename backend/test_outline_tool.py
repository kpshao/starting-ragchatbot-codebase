#!/usr/bin/env python3
"""
Test script for the new CourseOutlineTool functionality.
Demonstrates the tool's ability to retrieve course outlines with fuzzy matching.
"""

from rag_system import RAGSystem
from config import Config


def test_outline_tool():
    """Test the course outline tool with various queries."""
    config = Config()
    rag = RAGSystem(config)

    print("=" * 70)
    print("COURSE OUTLINE TOOL TEST")
    print("=" * 70)
    print()

    # Test cases
    test_queries = [
        "What lessons are in the MCP course?",
        "Show me the course outline for MCP",
        "What topics does the MCP course cover?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"Test {i}: {query}")
        print("-" * 70)

        response, sources = rag.query(query, session_id=f'test_{i}')

        print("Response:")
        print(response)
        print()

        if sources:
            print("Sources:")
            for source in sources:
                print(f"  - {source['text']}")
                if source.get('url'):
                    print(f"    URL: {source['url']}")
        else:
            print("No sources returned")

        print()
        print()


if __name__ == "__main__":
    test_outline_tool()
