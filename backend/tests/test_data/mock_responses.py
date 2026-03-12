"""Mock API responses for testing"""

from unittest.mock import Mock


def create_tool_use_response(tool_name="search_course_content", tool_input=None):
    """Create a mock response with tool use"""
    if tool_input is None:
        tool_input = {"query": "test query", "course_name": "Test Course"}

    response = Mock()
    response.stop_reason = "tool_use"

    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_test123"
    tool_block.name = tool_name
    tool_block.input = tool_input

    response.content = [tool_block]
    return response


def create_final_answer_response(
    text="This is the final answer based on the search results.",
):
    """Create a mock response with final text answer"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = text

    response.content = [text_block]
    return response


def create_empty_response():
    """Create a mock response with empty content (failure case)"""
    response = Mock()
    response.stop_reason = "end_turn"
    response.content = []
    return response


def create_direct_answer_response(text="This is a direct answer without tool use."):
    """Create a mock response for general knowledge questions"""
    response = Mock()
    response.stop_reason = "end_turn"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = text

    response.content = [text_block]
    return response


def create_proxy_bug_response():
    """Create a mock response that triggers the proxy bug fallback"""
    response = Mock()
    response.stop_reason = "stop_sequence"
    response.stop_sequence = "function_calls"

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "Partial response"

    response.content = [text_block]
    return response
