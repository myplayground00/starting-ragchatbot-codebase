"""
Tests for AIGenerator in ai_generator.py

Covers:
- Direct text response (no tool use)
- Tool-use flow: Claude requests a tool → execute → second Claude call → final answer
- tool_manager.execute_tool() is actually called when stop_reason == "tool_use"
- Tool results are included in the follow-up API call
- Empty content blocks return the fallback message
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


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


def _make_response(stop_reason: str, content: list) -> MagicMock:
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content
    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_generator() -> tuple[AIGenerator, MagicMock]:
    """Return (AIGenerator, mock_anthropic_client)."""
    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        gen = AIGenerator(api_key="test-key", model="claude-test")
    gen.client = mock_client  # ensure the mock is bound
    return gen, mock_client


# ---------------------------------------------------------------------------
# Direct (no-tool) responses
# ---------------------------------------------------------------------------

class TestDirectResponse:

    def test_returns_text_on_end_turn(self):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("Here is your answer.")]
        )

        result = gen.generate_response(query="What is AI?")

        assert result == "Here is your answer."

    def test_fallback_message_when_no_text_block(self):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = _make_response("end_turn", [])

        result = gen.generate_response(query="What is AI?")

        assert "couldn't generate" in result.lower()

    def test_api_called_with_user_query(self):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("ok")]
        )

        gen.generate_response(query="hello")

        create_call = mock_client.messages.create.call_args
        messages = create_call.kwargs.get("messages") or create_call[1].get("messages") or create_call[0][0]
        # find messages param regardless of call style
        kwargs = create_call[1] if create_call[1] else {}
        args = create_call[0] if create_call[0] else ()
        all_kwargs = {**kwargs}
        if args:
            all_kwargs["positional"] = args
        # Simpler: just check the call_args directly
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"][0]["content"] == "hello"
        assert call_kwargs["messages"][0]["role"] == "user"

    def test_conversation_history_appended_to_system(self):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("ok")]
        )

        gen.generate_response(query="q", conversation_history="User: hi\nAssistant: hello")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "Previous conversation" in call_kwargs["system"]
        assert "User: hi" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Tool-use flow
# ---------------------------------------------------------------------------

class TestToolUseFlow:

    def _setup_tool_use(self, tool_result: str = "search results text"):
        """Set up generator + mocks for a tool-use interaction."""
        gen, mock_client = make_generator()

        tool_block = _make_tool_use_block(
            "search_course_content", "tool_123", {"query": "RAG definition"}
        )
        first_response = _make_response("tool_use", [tool_block])

        second_response = _make_response(
            "end_turn", [_make_text_block("Final answer using tool results.")]
        )

        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = tool_result

        tools = [{"name": "search_course_content", "description": "search", "input_schema": {}}]
        return gen, mock_client, tool_manager, tools

    def test_tool_manager_execute_is_called(self):
        """When stop_reason == 'tool_use', execute_tool() must be called."""
        gen, mock_client, tool_manager, tools = self._setup_tool_use()

        gen.generate_response(query="What is RAG?", tools=tools, tool_manager=tool_manager)

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="RAG definition"
        )

    def test_final_answer_is_returned(self):
        """The text from the second API call should be the return value."""
        gen, mock_client, tool_manager, tools = self._setup_tool_use()

        result = gen.generate_response(query="What is RAG?", tools=tools, tool_manager=tool_manager)

        assert result == "Final answer using tool results."

    def test_two_api_calls_are_made(self):
        """There should be exactly two messages.create calls: initial + follow-up."""
        gen, mock_client, tool_manager, tools = self._setup_tool_use()

        gen.generate_response(query="What is RAG?", tools=tools, tool_manager=tool_manager)

        assert mock_client.messages.create.call_count == 2

    def test_tool_result_included_in_second_call(self):
        """The follow-up API call must include the tool result as a user message."""
        gen, mock_client, tool_manager, tools = self._setup_tool_use("search results text")

        gen.generate_response(query="What is RAG?", tools=tools, tool_manager=tool_manager)

        second_call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = second_call_kwargs["messages"]
        # Last user message should contain tool results
        tool_result_messages = [
            m for m in messages
            if m["role"] == "user" and isinstance(m["content"], list)
        ]
        assert len(tool_result_messages) == 1
        tool_result_content = tool_result_messages[0]["content"]
        assert any(
            item.get("type") == "tool_result" and "search results text" in item.get("content", "")
            for item in tool_result_content
        )

    def test_tools_not_passed_in_second_call(self):
        """The follow-up call should NOT include tools (prevents infinite loop)."""
        gen, mock_client, tool_manager, tools = self._setup_tool_use()

        gen.generate_response(query="What is RAG?", tools=tools, tool_manager=tool_manager)

        second_call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" not in second_call_kwargs

    def test_fallback_when_second_response_has_no_text(self):
        """Fallback message returned when second API response has no text block."""
        gen, mock_client = make_generator()
        tool_block = _make_tool_use_block("search_course_content", "tid", {"query": "x"})
        first_response = _make_response("tool_use", [tool_block])
        second_response = _make_response("end_turn", [])
        mock_client.messages.create.side_effect = [first_response, second_response]

        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some result"
        tools = [{"name": "search_course_content"}]

        result = gen.generate_response(query="q", tools=tools, tool_manager=tool_manager)

        assert "couldn't generate" in result.lower() or "course content" in result.lower()

    def test_no_tool_call_when_tool_manager_absent(self):
        """If tool_manager is None, stop_reason=='tool_use' should not crash."""
        gen, mock_client = make_generator()
        tool_block = _make_tool_use_block("search_course_content", "tid", {"query": "x"})
        # Claude returns tool_use but no tool_manager provided — should fall through
        # to direct-response path (no text blocks → fallback message)
        response = _make_response("tool_use", [tool_block])
        mock_client.messages.create.return_value = response

        # Should not raise; falls through to direct text extraction
        result = gen.generate_response(query="q")
        # tool_block has type "tool_use", not "text", so text_blocks is empty → fallback
        assert "couldn't generate" in result.lower()
