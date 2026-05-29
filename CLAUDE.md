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

**Python version**: requires Python >=3.13 (set in `.python-version` and `pyproject.toml`).

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot for course materials. All backend code lives in `backend/`; the frontend is plain HTML/CSS/JS in `frontend/`. The FastAPI server in `backend/app.py` serves both the REST API and the static frontend.

### File Structure

```
backend/
  app.py               # FastAPI app: endpoints, startup document loading, static file serving
  config.py            # Config dataclass (all tunable settings); singleton exported as `config`
  rag_system.py        # RAGSystem: orchestrates doc processing, vector store, AI, sessions
  ai_generator.py      # AIGenerator: Anthropic API calls, two-turn tool-use pattern
  vector_store.py      # VectorStore: ChromaDB wrapper, two collections, semantic search
  search_tools.py      # Tool ABC, CourseSearchTool, ToolManager
  document_processor.py # DocumentProcessor: parses course .txt files, chunks text
  session_manager.py   # SessionManager: in-memory conversation history
  models.py            # Pydantic models: Course, Lesson, CourseChunk
  tests/
    test_ai_generator.py   # Unit tests for AIGenerator (direct + tool-use flows)
    test_search_tool.py    # Unit tests for CourseSearchTool and ToolManager
    test_rag_system.py     # Integration tests for RAGSystem pipeline
frontend/
  index.html           # Single-page UI with sidebar + chat area
  script.js            # Vanilla JS: API calls, session management, theme toggle
  style.css            # CSS with light/dark theme via data-theme attribute
  package.json         # Dev tooling: Prettier + ESLint
  .eslintrc.json       # ESLint config
  .prettierrc          # Prettier config
docs/
  course1_script.txt   # Sample course documents (plain text, required format below)
  ...
scripts/
  check-frontend-quality.sh  # Runs Prettier check + ESLint
  format-frontend.sh         # Auto-formats frontend with Prettier
.github/workflows/
  claude.yml             # Triggers Claude Code on @claude mentions in issues/PRs
  claude-code-review.yml # Auto code review on every PR
```

### Request Pipeline

A user query goes through this chain:

```
app.py (FastAPI) → RAGSystem.query() → AIGenerator.generate_response()
  → Claude API call #1 (with tool defs, tool_choice=auto)
    → if stop_reason == "tool_use":
        CourseSearchTool.execute()
          → VectorStore.search()
              → _resolve_course_name() [semantic fuzzy match on course_catalog]
              → course_content.query()  [top-N chunks by similarity]
        → Claude API call #2 (tool results as context, no tools)
    → final answer text + sources list
  → SessionManager.add_exchange()
→ JSON response { answer, sources, session_id }
```

### Key Design Decisions

- **Tool-based retrieval**: Claude decides whether to search — it is not auto-triggered on every query. The `search_course_content` tool accepts `query`, `course_name` (fuzzy), and `lesson_number` (optional filter).
- **Two ChromaDB collections**: `course_catalog` stores course-level metadata for fuzzy name resolution; `course_content` stores chunked lesson text for semantic search.
- **Conversation history**: Passed as plain text appended to the system prompt (not as messages), capped at `MAX_HISTORY=2` exchanges (configurable in `config.py`).
- **Session IDs**: Generated server-side as `session_1`, `session_2`, etc. (in-memory only — sessions are lost on server restart).
- **One search per query maximum**: The system prompt instructs Claude to make at most one tool call per user query.
- **No tools on the follow-up call**: `_handle_tool_execution()` deliberately omits tools from the second API call to prevent infinite tool-use loops.

### Configuration

All tunable parameters are in `backend/config.py`:

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | LLM used for generation |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for ChromaDB |
| `CHUNK_SIZE` | 800 | Max characters per content chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between chunks |
| `MAX_RESULTS` | 5 | Max chunks returned per search |
| `MAX_HISTORY` | 2 | Conversation exchanges retained per session |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence path (relative to `backend/`) |

`AIGenerator` is initialised with `temperature=0` and `max_tokens=800` (hardcoded in `base_params`).

### Document Format

Course documents in `docs/` must follow this structure for `DocumentProcessor` to parse them correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <lesson title>
Lesson Link: <url>
<lesson content...>
```

Accepted file extensions: `.pdf`, `.docx`, `.txt`. Chunks are up to 800 characters with sentence-level overlap of 100 characters (configured in `config.py`).

**Chunk context prefix**: The first chunk of each non-final lesson is prefixed with `"Lesson N content: "`. All chunks of the final lesson are prefixed with `"Course <title> Lesson N content: "`. This is a current inconsistency in `document_processor.py`.

On startup, `app.py` calls `rag_system.add_course_folder("../docs", clear_existing=False)`, which skips courses whose title already exists in ChromaDB, so re-running the server does not duplicate data.

### VectorStore Internals

- **`course_catalog` collection**: One document per course. The document text is the course title. Metadata includes `title`, `instructor`, `course_link`, `lesson_count`, and `lessons_json` (a JSON-serialised list of lesson objects with `lesson_number`, `lesson_title`, `lesson_link`). The ChromaDB ID equals the course title.
- **`course_content` collection**: One document per chunk. Metadata includes `course_title`, `lesson_number`, `chunk_index`. IDs are `<course_title_underscored>_<chunk_index>`.
- **`_resolve_course_name()`**: Runs a vector similarity query against `course_catalog` to support fuzzy/partial course name matching.

### Frontend Features

- **Dark/light theme**: Toggled by the button in the top-right corner; preference stored in `localStorage`.
- **Markdown rendering**: Assistant responses are parsed with `marked.js` (loaded from CDN in `index.html`).
- **Collapsible sources**: Sources returned by the API render as a `<details>` block below the assistant message. Links open in a new tab.
- **Suggested questions**: Pre-defined question buttons in the sidebar inject text into the input.
- **Session continuity**: `currentSessionId` is sent with every subsequent request so conversation history is maintained within a browser session.

## Running Tests

Run from the project root:

```bash
cd backend && uv run pytest tests/ -v
```

Tests use `unittest.mock` to patch `anthropic.Anthropic` and `chromadb.PersistentClient`, so no real API key or database is needed. Three test modules:

- `test_ai_generator.py` — covers direct responses, tool-use two-turn flow, fallback messages.
- `test_search_tool.py` — covers `CourseSearchTool.execute()` and `ToolManager`.
- `test_rag_system.py` — integration tests for the full `RAGSystem.query()` pipeline and `VectorStore._build_filter()`.

## Frontend Quality Checks

Run from the project root (requires Node.js and `npm install` inside `frontend/`):

```bash
# Install frontend dev dependencies (one-time)
cd frontend && npm install

# Check formatting and linting
bash scripts/check-frontend-quality.sh

# Auto-format
bash scripts/format-frontend.sh
```

The CI does not automatically run these; trigger them manually before committing frontend changes.

## GitHub Actions

Two workflows live in `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `claude.yml` | `@claude` mention in issue/PR comment or review | Runs Claude Code to fulfill the request |
| `claude-code-review.yml` | PR opened, synced, or reopened | Posts an automated code review via the `code-review` plugin |

Both use `CLAUDE_CODE_OAUTH_TOKEN` stored as a repository secret.

## Adding a New Tool

1. Create a class extending `Tool` (ABC in `search_tools.py`) implementing `get_tool_definition()` and `execute()`.
2. Register it: `tool_manager.register_tool(your_tool)` in `RAGSystem.__init__()`.
3. If it produces sources for the UI, add a `last_sources` list attribute — `ToolManager.get_last_sources()` checks all registered tools for this attribute.
4. `ToolManager.reset_sources()` iterates all tools with `last_sources` and clears them after each query.

## Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| `anthropic` | 0.58.2 | Claude API client |
| `chromadb` | 1.0.15 | Vector database |
| `sentence-transformers` | 5.0.0 | Local embedding model |
| `fastapi` | 0.116.1 | Web framework |
| `uvicorn` | 0.35.0 | ASGI server |
| `python-dotenv` | 1.1.1 | `.env` loading |
| `pytest` | >=9.0.2 | Test runner (dev) |
