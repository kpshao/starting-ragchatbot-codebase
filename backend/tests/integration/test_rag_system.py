"""Integration tests for RAG system handling content-query questions"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from rag_system import RAGSystem


@pytest.mark.integration
class TestRAGSystemQuery:
    """Test how RAG system handles content-query questions"""

    def test_query_with_course_question_uses_search_tool(self):
        """Verify course-specific questions trigger search tool"""
        with (
            patch("rag_system.VectorStore") as mock_vs,
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            # Setup mocks
            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer about MCP"
            mock_ai.return_value = mock_ai_instance

            # Create RAG system
            rag = RAGSystem()

            # Mock tool manager to track if search was used
            rag.tool_manager.get_last_sources = Mock(
                return_value=[
                    {"text": "MCP Course - Lesson 1", "url": "http://example.com"}
                ]
            )

            # Execute query
            response, sources = rag.query("What is MCP?")

            # Verify AI generator was called with tools
            call_args = mock_ai_instance.generate_response.call_args
            assert call_args[1]["tools"] is not None
            assert call_args[1]["tool_manager"] is not None
            assert len(sources) > 0

    def test_query_with_general_question_skips_search(self):
        """Verify general knowledge questions can skip search"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = (
                "Python is a programming language"
            )
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            response, sources = rag.query("What is Python?")

            # AI should still be called with tools available
            # (AI decides whether to use them)
            assert response == "Python is a programming language"
            assert len(sources) == 0

    def test_query_returns_sources_from_tool(self):
        """Verify sources are extracted from tool_manager"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer"
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()

            # Mock sources
            expected_sources = [
                {"text": "Course A - Lesson 1", "url": "http://a.com"},
                {"text": "Course B - Lesson 2", "url": "http://b.com"},
            ]
            rag.tool_manager.get_last_sources = Mock(return_value=expected_sources)

            response, sources = rag.query("Test query")

            assert sources == expected_sources

    def test_query_updates_session_history(self):
        """Verify conversation history is updated"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager") as mock_sm,
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer"
            mock_ai.return_value = mock_ai_instance

            mock_session_manager = Mock()
            mock_sm.return_value = mock_session_manager

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            response, sources = rag.query("Test question", session_id="session123")

            # Verify history was updated
            mock_session_manager.update_history.assert_called_once_with(
                "session123", "Test question", "Answer"
            )

    def test_query_with_no_session_creates_session(self):
        """Verify new session created when session_id is None"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager") as mock_sm,
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer"
            mock_ai.return_value = mock_ai_instance

            mock_session_manager = Mock()
            mock_session_manager.create_session.return_value = "new_session_id"
            mock_sm.return_value = mock_session_manager

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            response, sources = rag.query("Test question", session_id=None)

            # Verify new session was created
            mock_session_manager.create_session.assert_called_once()

    def test_query_resets_sources_after_retrieval(self):
        """Verify sources are reset to avoid leakage"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer"
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[{"text": "Source"}])
            rag.tool_manager.reset_sources = Mock()

            response, sources = rag.query("Test")

            # Verify sources were reset after retrieval
            rag.tool_manager.reset_sources.assert_called_once()

    def test_query_with_tool_execution_error_handles_gracefully(self):
        """Verify tool execution errors handled gracefully"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            # AI generator returns error message from tool
            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = (
                "Search error: Database unavailable"
            )
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            # Should not raise exception
            response, sources = rag.query("Test")

            assert "Search error" in response

    def test_query_passes_conversation_history_to_ai(self):
        """Verify conversation history is passed to AI generator"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager") as mock_sm,
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = "Answer"
            mock_ai.return_value = mock_ai_instance

            mock_session_manager = Mock()
            mock_session_manager.get_history.return_value = (
                "User: Previous\nAssistant: Response\n\n"
            )
            mock_sm.return_value = mock_session_manager

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            response, sources = rag.query("Follow-up question", session_id="session123")

            # Verify history was passed to AI
            call_args = mock_ai_instance.generate_response.call_args
            assert (
                call_args[1]["conversation_history"]
                == "User: Previous\nAssistant: Response\n\n"
            )

    def test_query_with_empty_query_string(self):
        """Verify handling of empty query string"""
        with (
            patch("rag_system.VectorStore"),
            patch("rag_system.AIGenerator") as mock_ai,
            patch("rag_system.DocumentProcessor"),
            patch("rag_system.SessionManager"),
        ):

            mock_ai_instance = Mock()
            mock_ai_instance.generate_response.return_value = (
                "Please provide a question"
            )
            mock_ai.return_value = mock_ai_instance

            rag = RAGSystem()
            rag.tool_manager.get_last_sources = Mock(return_value=[])

            # Should handle empty query without crashing
            response, sources = rag.query("")

            assert response is not None
