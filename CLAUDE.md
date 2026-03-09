# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Course Materials RAG (Retrieval-Augmented Generation) system that enables intelligent Q&A over course documents using semantic search and Claude AI. The system uses a two-stage AI calling pattern with tool use, where Claude autonomously decides when to search the vector database.

## Development Commands

**IMPORTANT**: This project uses `uv` as the package manager.
- Always use `uv` to manage ALL dependencies
- Always use `uv run` to execute commands
- Do NOT use `pip install` or `python` directly
- All Python commands must be prefixed with `uv run`

### Setup
```bash
# Install uv package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (use uv sync, NOT pip install)
uv sync

# Create .env file with your Anthropic API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=your-key-here
# Optional: Add ANTHROPIC_BASE_URL=https://your-proxy-url.com/v1 if using a proxy
```

### Dependency Management
```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update dependencies
uv sync

# Remove a dependency
uv remove package-name

# NEVER use: pip install, pip uninstall, or python -m pip
```

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start from backend directory
cd backend
uv run uvicorn app:app --reload --port 8000

# Access points:
# - Web UI: http://localhost:8000
# - API docs: http://localhost:8000/docs
```

### Working with Documents
Documents are automatically loaded from `docs/` on startup. To add new course materials:
1. Place `.txt`, `.pdf`, or `.docx` files in the `docs/` directory
2. Restart the application
3. The system will skip already-processed courses (checks by title)

Expected document format:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: [lesson title]
Lesson Link: [url]
[lesson content...]
```

## Architecture

### Core Components Flow

```
User Query → FastAPI (app.py) → RAG System (rag_system.py) → AI Generator (ai_generator.py)
                                        ↓
                                  Tool Manager → Search Tool → Vector Store → ChromaDB
                                        ↓
                                  AI Generator (2nd call) → Response
```

### Key Architectural Patterns

**1. Two-Stage AI Calling with Tool Use**
- First API call: Claude decides whether to use the search tool based on query type
- Tool execution: If needed, searches vector database for relevant content
- Second API call: Claude generates final answer using search results
- This pattern avoids unnecessary searches for general knowledge questions

**2. Component Orchestration (rag_system.py)**
The RAG system is the central orchestrator that initializes and coordinates:
- `DocumentProcessor`: Chunks documents into 800-char segments with 100-char overlap
- `VectorStore`: Manages two ChromaDB collections (course_catalog for metadata, course_content for chunks)
- `AIGenerator`: Handles Claude API calls and tool execution flow
- `SessionManager`: Maintains conversation history (max 2 exchanges)
- `ToolManager`: Registers and executes tools (currently CourseSearchTool)

**3. Vector Search Strategy**
- Two-collection design: `course_catalog` for semantic course name matching, `course_content` for actual content
- Course name resolution: Partial names (e.g., "MCP") are matched to full titles via vector similarity
- Context preservation: Each chunk includes course and lesson metadata in the text itself
- Filtering: Supports filtering by course_title and lesson_number

**4. Document Processing Pipeline**
- Sentence-based chunking (not character-based) to preserve semantic boundaries
- Overlap mechanism ensures context continuity across chunks
- Metadata extraction from structured document headers
- Context augmentation: Chunks are prefixed with "Course [title] Lesson [num] content:"

### Configuration (backend/config.py)

All system parameters are centralized:
- `CHUNK_SIZE`: 800 chars (affects retrieval granularity)
- `CHUNK_OVERLAP`: 100 chars (affects context continuity)
- `MAX_RESULTS`: 5 (number of chunks returned per search)
- `MAX_HISTORY`: 2 (conversation turns to remember)
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2 (384-dim vectors)
- `CHROMA_PATH`: ./chroma_db (persistent storage location)

### Data Models (backend/models.py)

Three Pydantic models define the data structure:
- `Course`: title, course_link, instructor, lessons[]
- `Lesson`: lesson_number, title, lesson_link
- `CourseChunk`: content, course_title, lesson_number, chunk_index

### Frontend Architecture

Simple static frontend served by FastAPI:
- `index.html`: Main UI structure
- `script.js`: Handles API calls to `/api/query` and `/api/courses`
- `style.css`: Styling
- Uses marked.js for Markdown rendering of AI responses

## Important Implementation Details

### Vector Store Behavior
- `add_course_folder()` checks existing course titles to avoid duplicates
- Course titles serve as unique IDs in ChromaDB
- The `search()` method performs two queries: one for course name resolution, one for content
- Metadata is stored as JSON strings for complex structures (lessons array)

### AI Generator System Prompt
Located in `ai_generator.py`, the system prompt instructs Claude to:
- Use search tool ONLY for course-specific questions
- Limit to one search per query
- Provide direct answers without meta-commentary
- Not mention "based on search results"

### Session Management
- Sessions are created on first query if no session_id provided
- History format: "User: [query]\nAssistant: [response]\n\n"
- Limited to MAX_HISTORY exchanges to control token usage

### Tool Execution Flow
When Claude calls `search_course_content`:
1. `ToolManager.execute_tool()` routes to `CourseSearchTool.execute()`
2. Search tool calls `VectorStore.search()` with optional filters
3. Results are formatted with course/lesson headers
4. Sources are tracked in `last_sources` for UI display
5. Formatted results returned to AI for final response generation

## Common Modifications

### Adding New Tools
1. Create a class inheriting from `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` and `execute()`
3. Register in `RAGSystem.__init__()`: `self.tool_manager.register_tool(new_tool)`

### Changing Chunk Size
Modify `CHUNK_SIZE` in `config.py`, then rebuild the vector database:
- Delete `backend/chroma_db/` directory
- Restart application (will reprocess all documents)

### Adjusting Search Behavior
- Modify `MAX_RESULTS` in config.py for more/fewer chunks per search
- Edit `CourseSearchTool.get_tool_definition()` to change tool parameters
- Modify `VectorStore._build_filter()` to add new filter types

### Customizing AI Behavior
Edit the `SYSTEM_PROMPT` in `ai_generator.py`. Key sections:
- "Search Tool Usage" controls when Claude searches
- "Response Protocol" defines answer style
- Keep instructions concise to minimize token usage

## Database Management

ChromaDB stores data in `backend/chroma_db/`:
- Persistent across restarts
- To reset: delete the directory and restart
- To backup: copy the entire `chroma_db/` directory
- Collections are created automatically on first run

## Environment Variables

Required in `.env` file:
- `ANTHROPIC_API_KEY`: Your Claude API key (required)

Optional in `.env` file:
- `ANTHROPIC_BASE_URL`: Proxy/relay URL for accessing Anthropic API (optional)
  - Use this if you cannot directly access Anthropic's servers
  - Example: `ANTHROPIC_BASE_URL=https://your-proxy-url.com/v1`
  - Leave empty or omit to use the default Anthropic API endpoint

All other configuration is in `backend/config.py`.

## Troubleshooting

**Documents not loading**: Check that files are in `docs/` and follow the expected format (Course Title: on line 1)

**Search returns no results**: Verify ChromaDB is initialized (check `backend/chroma_db/` exists) and documents were processed on startup

**API key errors**: Ensure `.env` file exists in project root (not in backend/) and contains valid key

**Port conflicts**: Change port in run.sh or use `uv run uvicorn app:app --port 8001`

## Reference Documentation

- System flow diagram: `docs/query-flow-diagram.md` (detailed sequence diagrams)
- API documentation: Available at `/docs` when server is running
- Course document format: See example files in `docs/course*.txt`
