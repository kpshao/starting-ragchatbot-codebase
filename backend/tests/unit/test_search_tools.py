"""Unit tests for CourseSearchTool.execute() method"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


@pytest.mark.unit
class TestCourseSearchToolExecute:
    """Test CourseSearchTool.execute() method output evaluation"""

    def test_execute_with_valid_query_returns_formatted_results(self):
        """Verify successful search returns formatted string with headers"""
        # Create mock vector store
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Content from lesson 0", "Content from lesson 1"],
            metadata=[
                {"course_title": "Test Course", "lesson_number": 0},
                {"course_title": "Test Course", "lesson_number": 1}
            ],
            distances=[0.3, 0.5]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson-0"

        # Create tool and execute
        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test query")

        # Verify format
        assert "[Test Course - Lesson 0]" in result
        assert "[Test Course - Lesson 1]" in result
        assert "Content from lesson 0" in result
        assert "Content from lesson 1" in result

    def test_execute_with_no_results_returns_helpful_message(self):
        """Verify empty results return 'No relevant content found'"""
        mock_store = Mock()
        mock_results = SearchResults(documents=[], metadata=[], distances=[])
        mock_store.search.return_value = mock_results

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="nonexistent query")

        assert "No relevant content found" in result

    def test_execute_with_course_filter_applies_filter(self):
        """Verify course_name parameter filters correctly"""
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["MCP content"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 0}],
            distances=[0.2]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = None

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test", course_name="MCP")

        # Verify search was called with course_name
        mock_store.search.assert_called_once_with(
            query="test",
            course_name="MCP",
            lesson_number=None
        )
        assert "[MCP Course - Lesson 0]" in result

    def test_execute_with_lesson_filter_applies_filter(self):
        """Verify lesson_number parameter filters correctly"""
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Lesson 2 content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 2}],
            distances=[0.1]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson-2"

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test", lesson_number=2)

        # Verify search was called with lesson_number
        mock_store.search.assert_called_once_with(
            query="test",
            course_name=None,
            lesson_number=2
        )
        assert "[Test Course - Lesson 2]" in result

    def test_execute_with_invalid_course_returns_error(self):
        """Verify non-existent course returns error message"""
        mock_store = Mock()
        mock_results = SearchResults.empty("No course found matching 'NonExistent'")
        mock_store.search.return_value = mock_results

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test", course_name="NonExistent")

        assert "No course found matching 'NonExistent'" in result

    def test_execute_stores_sources_in_last_sources(self):
        """Verify last_sources attribute is populated with source dicts"""
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 2}
            ],
            distances=[0.2, 0.4]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.side_effect = [
            "https://example.com/a/lesson-1",
            "https://example.com/b/lesson-2"
        ]

        tool = CourseSearchTool(mock_store)
        tool.execute(query="test")

        # Verify last_sources is populated
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["text"] == "Course A - Lesson 1"
        assert tool.last_sources[0]["url"] == "https://example.com/a/lesson-1"
        assert tool.last_sources[1]["text"] == "Course B - Lesson 2"
        assert tool.last_sources[1]["url"] == "https://example.com/b/lesson-2"

    def test_execute_with_vector_store_error_returns_error_string(self):
        """Verify VectorStore errors are caught and returned as strings"""
        mock_store = Mock()
        mock_results = SearchResults.empty("Search error: Database connection failed")
        mock_store.search.return_value = mock_results

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test")

        assert "Search error: Database connection failed" in result

    def test_execute_formats_results_with_lesson_links(self):
        """Verify lesson links are included in sources"""
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Content with link"],
            metadata=[{"course_title": "Test Course", "lesson_number": 5}],
            distances=[0.1]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson-5"

        tool = CourseSearchTool(mock_store)
        tool.execute(query="test")

        # Verify link is in sources
        assert tool.last_sources[0]["url"] == "https://example.com/lesson-5"

    def test_execute_with_no_lesson_number_in_metadata(self):
        """Verify handling when lesson_number is None in metadata"""
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["General course content"],
            metadata=[{"course_title": "Test Course", "lesson_number": None}],
            distances=[0.2]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = None

        tool = CourseSearchTool(mock_store)
        result = tool.execute(query="test")

        # Should not include "Lesson" in header when lesson_number is None
        assert "[Test Course]" in result
        assert "Lesson None" not in result


@pytest.mark.unit
class TestToolManager:
    """Test ToolManager functionality"""

    def test_register_tool_adds_tool(self):
        """Verify tools can be registered"""
        manager = ToolManager()
        mock_store = Mock()
        tool = CourseSearchTool(mock_store)

        manager.register_tool(tool)

        assert "search_course_content" in manager.tools

    def test_get_tool_definitions_returns_list(self):
        """Verify tool definitions are returned"""
        manager = ToolManager()
        mock_store = Mock()
        tool = CourseSearchTool(mock_store)
        manager.register_tool(tool)

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"

    def test_execute_tool_calls_correct_tool(self):
        """Verify execute_tool routes to correct tool"""
        manager = ToolManager()
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Test"],
            metadata=[{"course_title": "Test", "lesson_number": 0}],
            distances=[0.1]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = None

        tool = CourseSearchTool(mock_store)
        manager.register_tool(tool)

        result = manager.execute_tool("search_course_content", query="test")

        assert "[Test - Lesson 0]" in result

    def test_get_last_sources_retrieves_sources(self):
        """Verify last_sources can be retrieved from tools"""
        manager = ToolManager()
        mock_store = Mock()
        mock_results = SearchResults(
            documents=["Content"],
            metadata=[{"course_title": "Test", "lesson_number": 1}],
            distances=[0.1]
        )
        mock_store.search.return_value = mock_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson-1"

        tool = CourseSearchTool(mock_store)
        manager.register_tool(tool)
        manager.execute_tool("search_course_content", query="test")

        sources = manager.get_last_sources()

        assert len(sources) == 1
        assert sources[0]["text"] == "Test - Lesson 1"

    def test_reset_sources_clears_sources(self):
        """Verify reset_sources clears all tool sources"""
        manager = ToolManager()
        mock_store = Mock()
        tool = CourseSearchTool(mock_store)
        tool.last_sources = [{"text": "Test", "url": "http://test.com"}]
        manager.register_tool(tool)

        manager.reset_sources()

        assert len(tool.last_sources) == 0
