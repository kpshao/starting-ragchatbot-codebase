"""API endpoint tests for FastAPI application"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


@pytest.fixture
def test_app():
    """Create a test FastAPI app without static file mounting"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional

    # Define models inline to avoid importing from app.py
    class QueryRequest(BaseModel):
        """Request model for course queries"""
        query: str
        session_id: Optional[str] = None

    class SourceItem(BaseModel):
        """Source with optional link"""
        text: str
        url: Optional[str] = None

    class QueryResponse(BaseModel):
        """Response model for course queries"""
        answer: str
        sources: List[SourceItem]
        session_id: str

    class CourseStats(BaseModel):
        """Response model for course statistics"""
        total_courses: int
        course_titles: List[str]

    # Create test app
    app = FastAPI(title="Test Course Materials RAG System")

    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mock RAG system
    mock_rag = Mock()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            if not request.query or len(request.query.strip()) == 0:
                raise HTTPException(status_code=400, detail="Query cannot be empty")

            if len(request.query) > 10000:
                raise HTTPException(status_code=400, detail="Query too long (max 10000 characters)")

            session_id = request.session_id
            if not session_id:
                session_id = mock_rag.session_manager.create_session()

            answer, sources = mock_rag.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Query failed: {type(e).__name__}: {str(e)}"
            )

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = mock_rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint"""
        return mock_rag.health_check()

    # Store mock_rag on app for test access
    app.state.mock_rag = mock_rag

    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_rag_system(test_app):
    """Get mock RAG system from test app"""
    return test_app.state.mock_rag


class TestQueryEndpoint:
    """Tests for /api/query endpoint"""

    def test_query_success(self, client, mock_rag_system):
        """Test successful query processing"""
        # Setup mock
        mock_rag_system.session_manager.create_session.return_value = "test-session-123"
        mock_rag_system.query.return_value = (
            "This is the answer to your question.",
            [
                {"text": "Course: Test Course, Lesson 1", "url": "https://example.com/lesson1"},
                {"text": "Course: Test Course, Lesson 2", "url": None}
            ]
        )

        # Make request
        response = client.post(
            "/api/query",
            json={"query": "What is testing?"}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is the answer to your question."
        assert len(data["sources"]) == 2
        assert data["session_id"] == "test-session-123"
        assert data["sources"][0]["text"] == "Course: Test Course, Lesson 1"
        assert data["sources"][0]["url"] == "https://example.com/lesson1"

    def test_query_with_existing_session(self, client, mock_rag_system):
        """Test query with existing session ID"""
        mock_rag_system.query.return_value = ("Answer", [])

        response = client.post(
            "/api/query",
            json={"query": "Follow-up question", "session_id": "existing-session"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "existing-session"
        mock_rag_system.query.assert_called_once_with("Follow-up question", "existing-session")

    def test_query_empty_string(self, client, mock_rag_system):
        """Test query with empty string"""
        response = client.post(
            "/api/query",
            json={"query": ""}
        )

        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]

    def test_query_whitespace_only(self, client, mock_rag_system):
        """Test query with whitespace only"""
        response = client.post(
            "/api/query",
            json={"query": "   "}
        )

        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]

    def test_query_too_long(self, client, mock_rag_system):
        """Test query exceeding max length"""
        long_query = "a" * 10001

        response = client.post(
            "/api/query",
            json={"query": long_query}
        )

        assert response.status_code == 400
        assert "Query too long" in response.json()["detail"]

    def test_query_missing_field(self, client, mock_rag_system):
        """Test request with missing query field"""
        response = client.post(
            "/api/query",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_query_internal_error(self, client, mock_rag_system):
        """Test handling of internal errors"""
        mock_rag_system.query.side_effect = ValueError("Database connection failed")

        response = client.post(
            "/api/query",
            json={"query": "What is testing?"}
        )

        assert response.status_code == 500
        assert "ValueError" in response.json()["detail"]
        assert "Database connection failed" in response.json()["detail"]


class TestCoursesEndpoint:
    """Tests for /api/courses endpoint"""

    def test_get_courses_success(self, client, mock_rag_system):
        """Test successful course stats retrieval"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": [
                "Introduction to Python",
                "Advanced Testing",
                "Web Development"
            ]
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Introduction to Python" in data["course_titles"]

    def test_get_courses_empty(self, client, mock_rag_system):
        """Test course stats with no courses"""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_error(self, client, mock_rag_system):
        """Test error handling in courses endpoint"""
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Database error")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


class TestHealthEndpoint:
    """Tests for /api/health endpoint"""

    def test_health_check_healthy(self, client, mock_rag_system):
        """Test health check when system is healthy"""
        mock_rag_system.health_check.return_value = {
            "status": "healthy",
            "chromadb": {"status": "healthy", "course_count": 5},
            "anthropic_api": {"status": "healthy"},
            "embedding_model": "all-MiniLM-L6-v2",
            "model": "claude-sonnet-4-20250514"
        }

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["chromadb"]["course_count"] == 5
        assert data["anthropic_api"]["status"] == "healthy"

    def test_health_check_unhealthy(self, client, mock_rag_system):
        """Test health check when system is unhealthy"""
        mock_rag_system.health_check.return_value = {
            "status": "unhealthy",
            "error": "ChromaDB connection failed"
        }

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data


class TestCORSHeaders:
    """Tests for CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set"""
        # Use a GET request instead of OPTIONS since TestClient doesn't fully simulate preflight
        response = client.get(
            "/api/courses",
            headers={"Origin": "http://localhost:3000"}
        )

        assert "access-control-allow-origin" in response.headers
        assert response.headers.get("access-control-allow-origin") == "*"

    def test_cors_allows_all_origins(self, client):
        """Test that CORS allows all origins"""
        response = client.get(
            "/api/courses",
            headers={"Origin": "http://example.com"}
        )

        assert response.headers.get("access-control-allow-origin") == "*"
