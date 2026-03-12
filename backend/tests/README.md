# Testing Framework

This directory contains the comprehensive test suite for the RAG chatbot backend.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_ai_generator.py
│   └── test_search_tools.py
├── integration/             # Integration tests for component interactions
│   ├── test_api_endpoints.py  # FastAPI endpoint tests
│   └── test_rag_system.py
├── diagnostic/              # System health and failure scenario tests
│   ├── test_failure_scenarios.py
│   └── test_system_health.py
├── test_data/              # Mock data and test fixtures
│   └── mock_responses.py
└── conftest.py             # Shared pytest fixtures
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest backend/tests/integration/test_api_endpoints.py

# Run with verbose output
uv run pytest -v

# Run tests by marker
uv run pytest -m unit
uv run pytest -m integration

# Run with coverage report
uv run pytest --cov=backend --cov-report=html
```

## Test Markers

Tests are organized with markers for selective execution:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for component interactions
- `@pytest.mark.diagnostic` - Diagnostic tests for system health
- `@pytest.mark.slow` - Tests that take longer to execute

## API Endpoint Tests

The `test_api_endpoints.py` file contains comprehensive tests for all FastAPI endpoints:

### `/api/query` Endpoint Tests
- Successful query processing
- Query with existing session
- Empty query validation
- Query length validation
- Missing field validation
- Internal error handling

### `/api/courses` Endpoint Tests
- Successful course stats retrieval
- Empty course list handling
- Error handling

### `/api/health` Endpoint Tests
- Healthy system status
- Unhealthy system status

### CORS Tests
- CORS headers presence
- Cross-origin request handling

## Shared Fixtures

The `conftest.py` file provides reusable fixtures:

- `sample_course_data` - Sample course and chunk data
- `temp_chroma_db` - Temporary ChromaDB instance
- `populated_vector_store` - VectorStore with test data
- `mock_anthropic_client` - Mock Anthropic API client
- `mock_search_results` - Mock search results
- `test_config` - Test configuration
- `mock_rag_system_full` - Fully mocked RAG system
- `sample_query_request` - Sample query request data
- `sample_query_response` - Sample query response data
- `sample_course_stats` - Sample course statistics

## Pytest Configuration

Configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--cov=backend",
    "--cov-report=term-missing",
    "--cov-report=html",
]
markers = [
    "unit: Unit tests for individual components",
    "integration: Integration tests for component interactions",
    "diagnostic: Diagnostic tests for system health and failure scenarios",
    "slow: Tests that take longer to execute",
]
asyncio_mode = "auto"
```

## Writing New Tests

### API Endpoint Tests

When adding new API endpoints, follow this pattern:

```python
def test_new_endpoint_success(client, mock_rag_system):
    """Test successful response from new endpoint"""
    # Setup mock
    mock_rag_system.method.return_value = expected_result

    # Make request
    response = client.get("/api/new-endpoint")

    # Assertions
    assert response.status_code == 200
    assert response.json()["key"] == "value"
```

### Using Fixtures

```python
def test_with_fixtures(sample_course_data, mock_anthropic_client):
    """Test using shared fixtures"""
    course = sample_course_data["course"]
    chunks = sample_course_data["chunks"]

    # Test logic here
```

## Coverage Reports

After running tests with coverage, view the HTML report:

```bash
open htmlcov/index.html
```

## Best Practices

1. **Isolation** - Each test should be independent and not rely on other tests
2. **Mocking** - Use mocks for external dependencies (API calls, database)
3. **Descriptive Names** - Test names should clearly describe what they test
4. **Arrange-Act-Assert** - Structure tests with clear setup, execution, and verification
5. **Edge Cases** - Test both happy paths and error conditions
6. **Fast Execution** - Keep tests fast by mocking expensive operations
