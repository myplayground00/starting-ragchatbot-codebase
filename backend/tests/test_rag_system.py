"""
Tests for the RAG system pipeline (rag_system.py + config.py integration).

Covers:
- MAX_RESULTS=0 in config causes ChromaDB to fail (the primary "query failed" bug)
- VectorStore.search() with n_results=0 raises / returns an error
- RAGSystem.query() surfaces the error instead of returning an answer
- With a valid MAX_RESULTS, the full pipeline returns a non-error answer
- VectorStore._build_filter() correctness
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Config bug: MAX_RESULTS = 0
# ---------------------------------------------------------------------------

class TestConfigMaxResults:

    def test_default_max_results_is_zero(self):
        """
        Reproduce the bug: config.MAX_RESULTS is 0, not the documented default of 5.
        ChromaDB will reject n_results=0 with a ValueError.
        This test FAILS until the bug is fixed.
        """
        from config import config
        assert config.MAX_RESULTS > 0, (
            f"BUG: config.MAX_RESULTS={config.MAX_RESULTS}. "
            "ChromaDB requires n_results >= 1. Set MAX_RESULTS to 5 (documented default)."
        )


# ---------------------------------------------------------------------------
# VectorStore.search() with n_results=0
# ---------------------------------------------------------------------------

class TestVectorStoreSearchWithZeroResults:
    """
    These tests use a real (in-memory) ChromaDB to prove that n_results=0
    causes an error in the search path.
    """

    def _make_vector_store(self, max_results: int):
        """Create a VectorStore backed by an in-memory ChromaDB."""
        import chromadb
        from chromadb.config import Settings
        from unittest.mock import patch

        with patch("vector_store.chromadb.PersistentClient") as mock_chroma:
            # Use in-memory client for tests
            real_client = chromadb.Client()  # ephemeral in-memory
            mock_chroma.return_value = real_client
            from vector_store import VectorStore
            store = VectorStore(
                chroma_path=":memory:",
                embedding_model="all-MiniLM-L6-v2",
                max_results=max_results,
            )
        return store

    def test_search_with_zero_n_results_returns_error(self):
        """
        VectorStore.search() should return SearchResults.error when n_results=0
        (ChromaDB raises an exception that search() catches and wraps).
        This test documents the bug: it currently results in an error, not results.
        """
        store = self._make_vector_store(max_results=0)
        results = store.search(query="What is RAG?")
        assert results.error is not None, (
            "BUG: search() with max_results=0 should return an error "
            "because ChromaDB requires n_results >= 1."
        )

    def test_search_with_valid_n_results_does_not_error_when_empty(self):
        """With max_results=5 and an empty collection, search returns empty results (no error)."""
        store = self._make_vector_store(max_results=5)
        results = store.search(query="What is RAG?")
        # Empty collection → empty results, but no error
        assert results.error is None or "n_results" not in (results.error or ""), (
            "Unexpected error with valid max_results=5"
        )


# ---------------------------------------------------------------------------
# RAGSystem.query() with mocked components
# ---------------------------------------------------------------------------

@dataclass
class FakeConfig:
    ANTHROPIC_API_KEY: str = "test-key"
    ANTHROPIC_MODEL: str = "claude-test"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 0  # Reproduce bug
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./chroma_db"


@dataclass
class FixedConfig:
    ANTHROPIC_API_KEY: str = "test-key"
    ANTHROPIC_MODEL: str = "claude-test"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5  # Fixed value
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = "./chroma_db"


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_name: str, tool_id: str, input_data: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = input_data
    return block


def _make_api_response(stop_reason: str, content: list) -> MagicMock:
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = content
    return r


class TestRAGSystemQuery:

    def _build_rag_system(self, config, search_results):
        """
        Build a RAGSystem with:
        - Real components but mocked Anthropic client and ChromaDB
        - Controlled search results injected via mock VectorStore.search()
        """
        with patch("ai_generator.anthropic.Anthropic"), \
             patch("vector_store.chromadb.PersistentClient"), \
             patch("vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):

            from rag_system import RAGSystem
            rag = RAGSystem(config)

        # Replace the vector store's search with a controlled mock
        rag.vector_store.search = MagicMock(return_value=search_results)
        return rag

    def test_query_fails_with_max_results_zero(self):
        """
        With MAX_RESULTS=0, the tool's search call fails and the error
        is returned as the tool result. The AI gets an error message instead
        of course content — demonstrating the root cause of 'query failed'.
        """
        from vector_store import SearchResults
        error_results = SearchResults.empty(
            "Search error: n_results must be a positive integer"
        )

        rag = self._build_rag_system(FakeConfig(), error_results)

        # Simulate Claude deciding to use the search tool
        tool_block = _make_tool_use_block(
            "search_course_content", "t1", {"query": "What is RAG?"}
        )
        first_response = _make_api_response("tool_use", [tool_block])
        final_response = _make_api_response(
            "end_turn", [_make_text_block("I couldn't find course content due to a search error.")]
        )
        rag.ai_generator.client.messages.create.side_effect = [first_response, final_response]

        answer, sources = rag.query("What is RAG?", session_id=None)

        # The tool received an error, and the AI should reflect that
        # Crucially: sources must be empty because the search failed
        assert sources == []

        # The error is propagated through the tool result to the AI
        tool_call_args = rag.ai_generator.client.messages.create.call_args_list
        # Check second call contains the error in tool results
        second_call_messages = tool_call_args[1].kwargs["messages"]
        tool_result_msg = next(
            m for m in second_call_messages
            if m["role"] == "user" and isinstance(m["content"], list)
        )
        tool_result_text = tool_result_msg["content"][0]["content"]
        assert "Search error" in tool_result_text, (
            f"Expected 'Search error' in tool result, got: {tool_result_text}"
        )

    def test_query_succeeds_with_valid_max_results(self):
        """
        With MAX_RESULTS=5, search returns content and the AI produces a real answer.
        """
        from vector_store import SearchResults
        good_results = SearchResults(
            documents=["RAG combines retrieval with generation."],
            metadata=[{"course_title": "Intro to RAG", "lesson_number": 1}],
            distances=[0.05],
        )

        rag = self._build_rag_system(FixedConfig(), good_results)
        rag.vector_store.get_lesson_link = MagicMock(return_value="https://example.com")

        tool_block = _make_tool_use_block(
            "search_course_content", "t2", {"query": "What is RAG?"}
        )
        first_response = _make_api_response("tool_use", [tool_block])
        final_response = _make_api_response(
            "end_turn",
            [_make_text_block("RAG combines retrieval with generation to answer questions.")]
        )
        rag.ai_generator.client.messages.create.side_effect = [first_response, final_response]

        answer, sources = rag.query("What is RAG?", session_id=None)

        assert "RAG" in answer
        assert len(sources) == 1
        assert sources[0]["label"] == "Intro to RAG - Lesson 1"

    def test_query_returns_direct_answer_for_general_questions(self):
        """
        For general (non-course-specific) questions, Claude should answer
        directly without using the search tool.
        """
        from vector_store import SearchResults
        rag = self._build_rag_system(FixedConfig(), SearchResults([], [], []))

        direct_response = _make_api_response(
            "end_turn", [_make_text_block("The capital of France is Paris.")]
        )
        rag.ai_generator.client.messages.create.return_value = direct_response

        answer, sources = rag.query("What is the capital of France?", session_id=None)

        assert "Paris" in answer
        assert sources == []
        # Search should NOT have been called for a general knowledge question
        rag.vector_store.search.assert_not_called()

    def test_session_history_is_saved(self):
        """Conversation history should be recorded in the session after a query."""
        from vector_store import SearchResults
        rag = self._build_rag_system(FixedConfig(), SearchResults([], [], []))

        direct_response = _make_api_response(
            "end_turn", [_make_text_block("Answer.")]
        )
        rag.ai_generator.client.messages.create.return_value = direct_response

        session_id = rag.session_manager.create_session()
        rag.query("My question", session_id=session_id)

        history = rag.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "My question" in history


# ---------------------------------------------------------------------------
# VectorStore._build_filter()
# ---------------------------------------------------------------------------

class TestBuildFilter:

    def _make_store(self):
        with patch("vector_store.chromadb.PersistentClient"), \
             patch("vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"):
            from vector_store import VectorStore
            return VectorStore(".", "all-MiniLM-L6-v2", max_results=5)

    def test_no_filters_returns_none(self):
        store = self._make_store()
        assert store._build_filter(None, None) is None

    def test_course_only_filter(self):
        store = self._make_store()
        f = store._build_filter("My Course", None)
        assert f == {"course_title": "My Course"}

    def test_lesson_only_filter(self):
        store = self._make_store()
        f = store._build_filter(None, 3)
        assert f == {"lesson_number": 3}

    def test_combined_filter(self):
        store = self._make_store()
        f = store._build_filter("My Course", 2)
        assert "$and" in f
        assert {"course_title": "My Course"} in f["$and"]
        assert {"lesson_number": 2} in f["$and"]
