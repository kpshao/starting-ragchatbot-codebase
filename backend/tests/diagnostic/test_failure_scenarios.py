"""Diagnostic tests to reproduce 'query failed' error scenarios"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


@pytest.mark.diagnostic
class TestFailureScenarios:
    """Test specific failure modes that could cause 'query failed'"""

    def test_empty_chromadb_causes_no_results(self):
        """Empty database → 'No relevant content found'"""
        from vector_store import VectorStore

        with patch("vector_store.config") as mock_config:
            mock_config.CHROMA_PATH = "/tmp/empty_chroma"
            mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
            mock_config.MAX_RESULTS = 5

            # Create empty vector store
            with patch("chromadb.PersistentClient") as mock_client:
                mock_collection = Mock()
                mock_collection.query.return_value = {
                    "documents": [[]],
                    "metadatas": [[]],
                    "distances": [[]],
                }
                mock_client_instance = Mock()
                mock_client_instance.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_client.return_value = mock_client_instance

                store = VectorStore()
                results = store.search("test query")

                # Should return empty results, not crash
                assert results.is_empty()

    def test_invalid_api_key_causes_exception(self):
        """Invalid key → Exception that becomes HTTPException 500"""
        from ai_generator import AIGenerator

        # Use obviously invalid key
        generator = AIGenerator(
            api_key="invalid_key_12345", model="claude-sonnet-4-20250514"
        )

        with pytest.raises(Exception):
            # This should raise an authentication error
            generator.generate_response(query="Test")

    def test_empty_ai_response_returns_fallback(self):
        """Empty content → 'I apologize, but I couldn't generate a response'"""
        from ai_generator import AIGenerator
        from test_data.mock_responses import (
            create_empty_response,
            create_tool_use_response,
        )

        mock_client = Mock()
        tool_response = create_tool_use_response()
        empty_response = create_empty_response()
        mock_client.messages.create.side_effect = [tool_response, empty_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch("ai_generator.anthropic.Anthropic", return_value=mock_client):
            generator = AIGenerator(
                api_key="test-key", model="claude-sonnet-4-20250514"
            )
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test", tools=tools, tool_manager=mock_tool_manager
            )

            # Should return fallback message
            assert "I apologize, but I couldn't generate a response" in result

    def test_tool_execution_error_returns_error_string(self):
        """Tool error → error message in tool result"""
        from search_tools import CourseSearchTool
        from vector_store import SearchResults

        mock_store = Mock()
        mock_store.search.return_value = SearchResults.empty(
            "Search error: Connection failed"
        )

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test")

        # Should return error string, not raise exception
        assert "Search error: Connection failed" in result

    def test_course_name_resolution_failure(self):
        """Non-existent course → error message"""
        from search_tools import CourseSearchTool
        from vector_store import SearchResults

        mock_store = Mock()
        mock_store.search.return_value = SearchResults.empty(
            "No course found matching 'NonExistent'"
        )

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test", course_name="NonExistent")

        assert "No course found" in result

    def test_network_error_to_anthropic_api(self):
        """Network failure → exception propagated"""
        from ai_generator import AIGenerator

        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception(
            "Network error: Connection timeout"
        )

        with patch("ai_generator.anthropic.Anthropic", return_value=mock_client):
            generator = AIGenerator(
                api_key="test-key", model="claude-sonnet-4-20250514"
            )
            generator.client = mock_client

            with pytest.raises(Exception) as exc_info:
                generator.generate_response(query="Test")

            assert "Network error" in str(exc_info.value)

    def test_chromadb_query_exception(self):
        """ChromaDB query error → search error returned"""
        from vector_store import VectorStore

        with patch("vector_store.config") as mock_config:
            mock_config.CHROMA_PATH = "/tmp/test_chroma"
            mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
            mock_config.MAX_RESULTS = 5

            with patch("chromadb.PersistentClient") as mock_client:
                mock_collection = Mock()
                mock_collection.query.side_effect = Exception("Database corrupted")
                mock_client_instance = Mock()
                mock_client_instance.get_or_create_collection.return_value = (
                    mock_collection
                )
                mock_client.return_value = mock_client_instance

                store = VectorStore()
                results = store.search("test")

                # Should return error in SearchResults, not crash
                assert results.error is not None
                assert "Database corrupted" in results.error

    def test_rate_limit_error(self):
        """Rate limit → API exception"""
        import anthropic
        from ai_generator import AIGenerator

        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            "Rate limit exceeded"
        )

        with patch("ai_generator.anthropic.Anthropic", return_value=mock_client):
            generator = AIGenerator(
                api_key="test-key", model="claude-sonnet-4-20250514"
            )
            generator.client = mock_client

            with pytest.raises(anthropic.RateLimitError):
                generator.generate_response(query="Test")

    def test_full_pipeline_with_empty_database(self):
        """Integration test: empty database through full pipeline"""
        from rag_system import RAGSystem

        with (
            patch("rag_system.VectorStore") as mock_vs,
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            # Mock empty vector store
            mock_vs_instance = Mock()
            mock_vs_instance.get_existing_course_titles.return_value = []
            mock_vs.return_value = mock_vs_instance

            # Mock AI returning "no results" message
            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = (
                "No relevant content found"
            )
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            response, sources = rag.query("What is MCP?")

            # Should handle gracefully
            assert "No relevant content found" in response
            assert len(sources) == 0

    def test_full_pipeline_with_api_error(self):
        """Integration test: API error through full pipeline"""
        from rag_system import RAGSystem

        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            # Mock AI raising exception
            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.side_effect = Exception(
                "API Error: Invalid key"
            )
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()

            # Should propagate exception (caught by app.py)
            with pytest.raises(Exception) as exc_info:
                rag.query("Test")

            assert "API Error" in str(exc_info.value)

    def test_missing_env_variable(self):
        """Missing ANTHROPIC_API_KEY → should be caught by system health test"""
        import os

        # Temporarily remove API key
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        if original_key:
            del os.environ["ANTHROPIC_API_KEY"]

        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            assert api_key is None, "API key should be None when not set"
        finally:
            # Restore original key
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key
