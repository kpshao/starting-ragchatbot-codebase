import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

from config import config
from rag_system import RAGSystem

# Initialize FastAPI app
app = FastAPI(title="Course Materials RAG System", root_path="")

# Add trusted host middleware for proxy
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Enable CORS with proper settings for proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize RAG system
rag_system = RAGSystem(config)

# Pydantic models for request/response
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

# API Endpoints

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Process a query and return response with sources"""
    try:
        # Validate query
        if not request.query or len(request.query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        if len(request.query) > 10000:
            raise HTTPException(status_code=400, detail="Query too long (max 10000 characters)")

        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()

        # Process query using RAG system
        answer, sources = rag_system.query(request.query, session_id)

        return QueryResponse(
            answer=answer,
            sources=sources,
            session_id=session_id
        )
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        # Log detailed error information
        import traceback
        error_type = type(e).__name__
        error_msg = str(e)
        error_traceback = traceback.format_exc()

        print(f"\n{'='*80}")
        print(f"ERROR in /api/query endpoint")
        print(f"{'='*80}")
        print(f"Error Type: {error_type}")
        print(f"Error Message: {error_msg}")
        print(f"Query: {request.query[:100]}...")  # First 100 chars
        print(f"Session ID: {request.session_id}")
        print(f"\nFull Traceback:")
        print(error_traceback)
        print(f"{'='*80}\n")

        # Return detailed error to client
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {error_type}: {error_msg}"
        )

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """Get course analytics and statistics"""
    try:
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify system status"""
    try:
        # Check ChromaDB
        course_titles = rag_system.vector_store.get_existing_course_titles()
        course_count = len(course_titles)

        # Check if we can make a simple AI call
        try:
            test_response = rag_system.ai_generator.client.messages.create(
                model=rag_system.config.ANTHROPIC_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            api_status = "healthy"
        except Exception as api_error:
            api_status = f"unhealthy: {str(api_error)}"

        return {
            "status": "healthy",
            "chromadb": {
                "status": "healthy",
                "course_count": course_count
            },
            "anthropic_api": {
                "status": api_status
            },
            "embedding_model": config.EMBEDDING_MODEL,
            "model": config.ANTHROPIC_MODEL
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": f"{type(e).__name__}: {str(e)}"
        }

@app.on_event("startup")
async def startup_event():
    """Load initial documents on startup"""
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            print(f"Error loading documents: {e}")

# Custom static file handler with no-cache headers for development
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Add no-cache headers for development
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")