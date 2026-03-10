"""Unit tests for AIGenerator tool calling functionality"""

import pytest
from unittest.mock import Mock, patch, call
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from ai_generator import AIGenerator
from tests.test_data.mock_responses import (
    create_tool_use_response,
    create_final_answer_response,
    create_empty_response,
    create_direct_answer_response,
    create_proxy_bug_response
)


@pytest.mark.unit
class TestAIGeneratorToolCalling:
    """Test AIGenerator correctly calls CourseSearchTool"""

    def test_generate_response_calls_tool_when_needed(self):
        """Verify tool_manager.execute_tool() is called when AI requests tool use"""
        # Create mock client that returns tool use, then final answer
        mock_client = Mock()
        tool_response = create_tool_use_response()
        final_response = create_final_answer_response()
        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Create mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results here"

        # Create AI generator with mock client
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content", "description": "Search tool"}]
            result = generator.generate_response(
                query="What is MCP?",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Verify tool was executed
            mock_tool_manager.execute_tool.assert_called_once()
            assert result == "This is the final answer based on the search results."

    def test_generate_response_two_stage_calling(self):
        """Verify two-stage calling: tool use → tool result → final answer"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        final_response = create_final_answer_response("Final answer after tool use")
        mock_client.messages.create.side_effect = [tool_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool execution result"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Verify two API calls were made
            assert mock_client.messages.create.call_count == 2
            assert result == "Final answer after tool use"

    def test_generate_response_handles_empty_content(self):
        """Test line 182-183: empty content returns fallback message"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        empty_response = create_empty_response()
        mock_client.messages.create.side_effect = [tool_response, empty_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Should return fallback message
            assert "I apologize, but I couldn't generate a response" in result

    def test_generate_response_without_tools_returns_direct_answer(self):
        """Verify general knowledge questions don't use tools"""
        mock_client = Mock()
        direct_response = create_direct_answer_response("Python is a programming language")
        mock_client.messages.create.return_value = direct_response

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            # No tools provided
            result = generator.generate_response(query="What is Python?")

            # Should return direct answer without tool use
            assert result == "Python is a programming language"
            assert mock_client.messages.create.call_count == 1

    def test_generate_response_with_api_error_raises_exception(self):
        """Verify Anthropic API errors are propagated"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error: Rate limit exceeded")

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            with pytest.raises(Exception) as exc_info:
                generator.generate_response(query="Test")

            assert "API Error" in str(exc_info.value)

    def test_handle_tool_execution_formats_messages_correctly(self):
        """Verify message format for tool results"""
        mock_client = Mock()
        tool_response = create_tool_use_response(
            tool_input={"query": "test", "course_name": "MCP"}
        )
        final_response = create_final_answer_response()
        mock_client.messages.create.side_effect = [tool_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            generator.generate_response(
                query="What is MCP?",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Check second API call (after tool execution)
            second_call = mock_client.messages.create.call_args_list[1]
            messages = second_call[1]["messages"]

            # Should have 3 messages: user query, assistant tool use, user tool result
            assert len(messages) == 3
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"
            assert messages[2]["role"] == "user"

            # Tool result should be in last message
            tool_results = messages[2]["content"]
            assert tool_results[0]["type"] == "tool_result"
            assert tool_results[0]["content"] == "Search results"

    def test_proxy_bug_fallback_triggers_correctly(self):
        """Test proxy bug detection and fallback in _force_final_response"""
        mock_client = Mock()
        # Two tool use responses to reach max rounds
        tool_response_1 = create_tool_use_response()
        tool_response_2 = create_tool_use_response()
        # Third response triggers proxy bug
        proxy_bug_response = create_proxy_bug_response()
        fallback_response = create_final_answer_response("Fallback answer")

        mock_client.messages.create.side_effect = [
            tool_response_1,
            tool_response_2,
            proxy_bug_response,  # This is the forced final response that has proxy bug
            fallback_response
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Should trigger fallback and make 4 API calls
            # (2 tool rounds, 1 proxy bug response, 1 fallback)
            assert mock_client.messages.create.call_count == 4
            assert result == "Fallback answer"

    def test_conversation_history_included_in_system_prompt(self):
        """Verify history is appended to system prompt"""
        mock_client = Mock()
        direct_response = create_direct_answer_response()
        mock_client.messages.create.return_value = direct_response

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            history = "User: Previous question\nAssistant: Previous answer\n\n"
            generator.generate_response(
                query="New question",
                conversation_history=history
            )

            # Check system prompt includes history
            call_args = mock_client.messages.create.call_args
            system_prompt = call_args[1]["system"]
            assert "Previous conversation:" in system_prompt
            assert "Previous question" in system_prompt
            assert "Previous answer" in system_prompt

    def test_generate_response_with_base_url(self):
        """Verify base_url is used when provided (proxy support)"""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(
                api_key="test-key",
                model="claude-sonnet-4-20250514",
                base_url="https://proxy.example.com/v1"
            )

            # Verify Anthropic was initialized with base_url
            mock_anthropic.assert_called_once_with(
                api_key="test-key",
                base_url="https://proxy.example.com/v1"
            )

    def test_generate_response_without_base_url(self):
        """Verify default Anthropic client when no base_url"""
        with patch('ai_generator.anthropic.Anthropic') as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            generator = AIGenerator(
                api_key="test-key",
                model="claude-sonnet-4-20250514"
            )

            # Verify Anthropic was initialized without base_url
            mock_anthropic.assert_called_once_with(api_key="test-key")

    def test_sequential_two_rounds(self):
        """Test sequential tool calling with 2 rounds (happy path)"""
        mock_client = Mock()
        # Round 1: get_course_outline tool use
        tool_response_1 = create_tool_use_response(
            tool_name="get_course_outline",
            tool_input={"course_name": "MCP"}
        )
        # Round 2: search_course_content tool use
        tool_response_2 = create_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "Prompt Engineering"}
        )
        # Final: text response
        final_response = create_final_answer_response("Found courses about Prompt Engineering")

        mock_client.messages.create.side_effect = [
            tool_response_1,
            tool_response_2,
            final_response
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Lesson 4: Prompt Engineering Basics",
            "Course: Advanced AI - covers Prompt Engineering"
        ]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [
                {"name": "get_course_outline"},
                {"name": "search_course_content"}
            ]
            result = generator.generate_response(
                query="Find courses about same topic as lesson 4 of MCP",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Verify 2 tool calls were made
            assert mock_tool_manager.execute_tool.call_count == 2
            # Verify 3 API calls (2 tool rounds + 1 final)
            assert mock_client.messages.create.call_count == 3
            assert result == "Found courses about Prompt Engineering"

    def test_early_termination_one_round(self):
        """Test that Claude can stop after 1 tool call if answer is complete"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        # Second response is text (no more tool use)
        final_response = create_final_answer_response("Answer after one tool call")

        mock_client.messages.create.side_effect = [tool_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Complete search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Only 1 tool call
            assert mock_tool_manager.execute_tool.call_count == 1
            # 2 API calls (1 tool round + 1 final)
            assert mock_client.messages.create.call_count == 2
            assert result == "Answer after one tool call"

    def test_max_rounds_enforced(self):
        """Test that max 2 rounds are enforced"""
        mock_client = Mock()
        # All 3 responses are tool use (Claude keeps trying)
        tool_response_1 = create_tool_use_response(tool_name="get_course_outline")
        tool_response_2 = create_tool_use_response(tool_name="search_course_content")
        tool_response_3 = create_tool_use_response(tool_name="get_course_outline")  # 3rd attempt
        final_response = create_final_answer_response("Forced final answer")

        mock_client.messages.create.side_effect = [
            tool_response_1,
            tool_response_2,
            tool_response_3,  # This triggers max rounds
            final_response
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "get_course_outline"}, {"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Only 2 tool calls (max rounds)
            assert mock_tool_manager.execute_tool.call_count == 2
            # 4 API calls (2 tool rounds + 1 for 3rd attempt + 1 forced final)
            assert mock_client.messages.create.call_count == 4
            assert "Forced final answer" in result

    def test_tool_execution_error_handling(self):
        """Test graceful handling of tool execution errors"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        final_response = create_final_answer_response("Answer despite error")

        mock_client.messages.create.side_effect = [tool_response, final_response]

        mock_tool_manager = Mock()
        # Tool execution raises exception
        mock_tool_manager.execute_tool.side_effect = Exception("Database connection failed")

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Should handle error gracefully and return final response
            assert mock_client.messages.create.call_count == 2
            assert "Answer despite error" in result

    def test_duplicate_call_prevention(self):
        """Test that duplicate tool calls are detected and prevented"""
        mock_client = Mock()
        # Same tool call twice
        tool_response_1 = create_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test", "course_name": "MCP"}
        )
        tool_response_2 = create_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test", "course_name": "MCP"}  # Duplicate
        )
        final_response = create_final_answer_response("Forced answer after duplicate")

        mock_client.messages.create.side_effect = [
            tool_response_1,
            tool_response_2,
            final_response
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Only 1 tool call (duplicate prevented)
            assert mock_tool_manager.execute_tool.call_count == 1
            # Should force final response after detecting duplicate
            assert "Forced answer after duplicate" in result

    def test_empty_response_handling(self):
        """Test handling of empty response content during tool rounds"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        empty_response = create_empty_response()

        mock_client.messages.create.side_effect = [tool_response, empty_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Should return fallback message
            assert "I apologize, but I couldn't generate a response" in result

    def test_final_response_always_text(self):
        """Test that final response is always text, never tool_use"""
        mock_client = Mock()
        tool_response_1 = create_tool_use_response()
        tool_response_2 = create_tool_use_response()
        # After max rounds, force final text response
        final_response = create_final_answer_response("Final text answer")

        mock_client.messages.create.side_effect = [
            tool_response_1,
            tool_response_2,
            final_response
        ]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="Test query",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Final result should be text
            assert isinstance(result, str)
            assert "Final text answer" in result

    def test_backward_compatibility_single_call(self):
        """Test that existing single tool call behavior still works"""
        mock_client = Mock()
        tool_response = create_tool_use_response()
        final_response = create_final_answer_response("Single call answer")

        mock_client.messages.create.side_effect = [tool_response, final_response]

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results"

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

            tools = [{"name": "search_course_content"}]
            result = generator.generate_response(
                query="What is MCP?",
                tools=tools,
                tool_manager=mock_tool_manager
            )

            # Should work exactly as before
            assert mock_tool_manager.execute_tool.call_count == 1
            assert mock_client.messages.create.call_count == 2
            assert result == "Single call answer"
