"""Diagnostic tests to validate system health and environment"""

import os
import sys
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))


@pytest.mark.diagnostic
class TestSystemHealth:
    """Tests to validate the system environment and prerequisites"""

    def test_anthropic_api_key_is_set(self):
        """Verify ANTHROPIC_API_KEY is set in environment"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        assert (
            api_key is not None
        ), "ANTHROPIC_API_KEY not found in environment. Check .env file."
        assert len(api_key) > 0, "ANTHROPIC_API_KEY is empty"

    def test_anthropic_api_key_is_valid(self):
        """Verify API key works with a simple API call"""
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        try:
            client = anthropic.Anthropic(api_key=api_key)
            # Make a minimal API call to verify the key works
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            assert response is not None
            assert len(response.content) > 0
        except anthropic.AuthenticationError:
            pytest.fail("ANTHROPIC_API_KEY is invalid or expired")
        except Exception as e:
            pytest.fail(f"API call failed: {str(e)}")

    def test_chromadb_directory_exists(self):
        """Verify chroma_db directory exists"""
        chroma_path = backend_path / "chroma_db"
        assert (
            chroma_path.exists()
        ), f"ChromaDB directory not found at {chroma_path}. Run the application once to initialize."

    def test_chromadb_has_collections(self):
        """Verify ChromaDB collections exist"""
        import chromadb

        chroma_path = backend_path / "chroma_db"
        if not chroma_path.exists():
            pytest.skip("ChromaDB directory doesn't exist")

        try:
            client = chromadb.PersistentClient(path=str(chroma_path))
            collections = client.list_collections()
            collection_names = [c.name for c in collections]

            assert (
                "course_catalog" in collection_names
            ), "course_catalog collection not found"
            assert (
                "course_content" in collection_names
            ), "course_content collection not found"
        except Exception as e:
            pytest.fail(f"Failed to access ChromaDB: {str(e)}")

    def test_chromadb_has_data(self):
        """Verify ChromaDB collections have documents"""
        import chromadb

        chroma_path = backend_path / "chroma_db"
        if not chroma_path.exists():
            pytest.skip("ChromaDB directory doesn't exist")

        try:
            client = chromadb.PersistentClient(path=str(chroma_path))

            # Check course_catalog
            catalog = client.get_collection("course_catalog")
            catalog_count = catalog.count()
            assert (
                catalog_count > 0
            ), "course_catalog collection is empty. Load course documents."

            # Check course_content
            content = client.get_collection("course_content")
            content_count = content.count()
            assert (
                content_count > 0
            ), "course_content collection is empty. Load course documents."

            print(f"\nCourse catalog has {catalog_count} courses")
            print(f"Course content has {content_count} chunks")
        except Exception as e:
            pytest.fail(f"Failed to check ChromaDB data: {str(e)}")

    def test_embedding_model_loads(self):
        """Verify sentence-transformers model loads successfully"""
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            # Test embedding generation
            embedding = model.encode("test")
            assert len(embedding) == 384, "Embedding dimension mismatch"
        except Exception as e:
            pytest.fail(f"Failed to load embedding model: {str(e)}")

    def test_docs_directory_exists(self):
        """Verify docs/ directory exists"""
        docs_path = backend_path.parent / "docs"
        assert docs_path.exists(), f"docs/ directory not found at {docs_path}"

    def test_docs_directory_has_files(self):
        """Verify docs/ directory has course files"""
        docs_path = backend_path.parent / "docs"
        if not docs_path.exists():
            pytest.skip("docs/ directory doesn't exist")

        files = (
            list(docs_path.glob("*.txt"))
            + list(docs_path.glob("*.pdf"))
            + list(docs_path.glob("*.docx"))
        )
        assert len(files) > 0, "No course documents found in docs/ directory"
        print(f"\nFound {len(files)} course documents")
