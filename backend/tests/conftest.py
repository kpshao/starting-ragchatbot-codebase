"""Shared pytest fixtures for all tests"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from models import Course, Lesson, CourseChunk
from vector_store import VectorStore, SearchResults
from tests.test_data.mock_responses import (
    create_tool_use_response,
    create_final_answer_response,
    create_empty_response,
    create_direct_answer_response
)


@pytest.fixture
def sample_course_data():
    """Create sample course data for testing"""
    course = Course(
        title="Test Course for RAG System",
        course_link="https://example.com/test-course",
        instructor="Test Instructor",
        lessons=[
            Lesson(
                lesson_number=0,
                title="Introduction to Testing",
                lesson_link="https://example.com/lesson-0"
            ),
            Lesson(
                lesson_number=1,
                title="Advanced Testing Techniques",
                lesson_link="https://example.com/lesson-1"
            )
        ]
    )

    chunks = [
        CourseChunk(
            content="This is the introduction lesson content. It covers basic testing concepts.",
            course_title="Test Course for RAG System",
            lesson_number=0,
            chunk_index=0
        ),
        CourseChunk(
            content="This lesson covers mocking, fixtures, and test isolation strategies.",
            course_title="Test Course for RAG System",
            lesson_number=1,
            chunk_index=0
        )
    ]

    return {"course": course, "chunks": chunks}


@pytest.fixture
def temp_chroma_db(tmp_path):
    """Create a temporary ChromaDB instance"""
    chroma_path = tmp_path / "test_chroma"
    chroma_path.mkdir()
    yield str(chroma_path)
    # Cleanup handled by tmp_path fixture


@pytest.fixture
def populated_vector_store(temp_chroma_db, sample_course_data):
    """Create a VectorStore with test data loaded"""
    # Mock config to use temp directory
    with patch('vector_store.config') as mock_config:
        mock_config.CHROMA_PATH = temp_chroma_db
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.MAX_RESULTS = 5

        store = VectorStore()

        # Add course metadata
        store.add_course_metadata(sample_course_data["course"])

        # Add course content
        for chunk in sample_course_data["chunks"]:
            store.add_course_content(chunk)

        return store


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    client = Mock()
    messages = Mock()
    client.messages = messages
    return client


@pytest.fixture
def mock_search_results():
    """Create mock search results"""
    return SearchResults(
        documents=["Test content from lesson 0", "Test content from lesson 1"],
        metadata=[
            {"course_title": "Test Course for RAG System", "lesson_number": 0},
            {"course_title": "Test Course for RAG System", "lesson_number": 1}
        ],
        distances=[0.3, 0.5]
    )


@pytest.fixture
def mock_empty_search_results():
    """Create empty search results"""
    return SearchResults.empty("No relevant content found")


@pytest.fixture
def test_config():
    """Create test configuration"""
    config = Mock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    return config
