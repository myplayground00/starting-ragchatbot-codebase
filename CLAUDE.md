# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

**On Windows, use Git Bash** (not PowerShell or CMD) for shell commands.

```bash
# Set up environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Install dependencies
uv sync

# Start the server
bash run.sh

# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

Always use `uv` for all dependency management and execution — never `pip`, `pip install`, or bare `python`:

| Task | Command |
|---|---|
| Install all dependencies | `uv sync` |
| Add a new package | `uv add <package>` |
| Remove a package | `uv remove <package>` |
| Run a script or command | `uv run <cmd>` |

- Web UI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ChromaDB is persisted at `backend/chroma_db/` (created on first run)

## Architecture

This is a RAG (Retrieval-Augmented Generation) system. All backend code lives in `backend/`; the frontend is plain HTML/CSS/JS in `frontend/`. The server in `backend/app.py` serves both the API and the static frontend.

### Request pipeline

A user query goes through this chain:

```
app.py (FastAPI) → RAGSystem.query() → AIGenerator.generate_response()
  → Claude API call #1 (with tool defs, tool_choice=auto)
    → if stop_reason == "tool_use":
        CourseSearchTool.execute()
          → VectorStore.search()
              → _resolve_course_name() [semantic fuzzy match on course_catalog]
              → course_content.query()  [top-5 chunks by similarity]
        → Claude API call #2 (tool results as context, no tools)
    → final answer text + sources list
  → SessionManager.add_exchange()
→ JSON response { answer, sources, session_id }
```

### Key design decisions

- **Tool-based retrieval**: Claude decides whether to search — it is not auto-triggered on every query. The `search_course_content` tool accepts `query`, `course_name` (fuzzy), and `lesson_number` (optional filter).
- **Two ChromaDB collections**: `course_catalog` stores course-level metadata for fuzzy name resolution; `course_content` stores chunked lesson text for semantic search.
- **Conversation history**: Passed as plain text appended to the system prompt (not as messages), capped at `MAX_HISTORY=2` exchanges (configurable in `config.py`).
- **Session IDs**: Generated server-side as `session_1`, `session_2`, etc. (in-memory only — sessions are lost on server restart).

### Document format

Course documents in `docs/` must follow this structure for `DocumentProcessor` to parse them correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <lesson title>
...
```

Chunks are 800 characters with 100-character sentence-level overlap (configured in `config.py`). The first chunk of each lesson is prefixed with `"Lesson N content: "` for retrieval context.

### Configuration

All tunable parameters are in `backend/config.py`:

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | LLM used for generation |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for ChromaDB |
| `CHUNK_SIZE` | 800 | Max characters per content chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between chunks |
| `MAX_RESULTS` | 5 | Max chunks returned per search |
| `MAX_HISTORY` | 2 | Conversation exchanges retained per session |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence path (relative to `backend/`) |

### Adding a new tool

1. Create a class extending `Tool` (ABC in `search_tools.py`) implementing `get_tool_definition()` and `execute()`
2. Register it: `tool_manager.register_tool(your_tool)` in `RAGSystem.__init__()`
3. If it produces sources for the UI, add a `last_sources` list attribute — `ToolManager.get_last_sources()` checks all registered tools for this attribute
