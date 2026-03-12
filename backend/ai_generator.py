from typing import Any

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
- **get_course_outline**: Use for questions about course structure, lesson lists, or what topics a course covers
- **search_course_content**: Use for questions about specific course content or detailed educational materials

Tool Usage Rules:
- **Up to 2 sequential tool calls allowed**
- Use multiple tool calls when you need information from one tool to inform the next
- Example: Use get_course_outline to find a lesson title, then search_course_content for that topic
- After gathering information through tool calls, provide your final answer synthesizing all results
- Choose the appropriate tool based on the question type:
  - Course structure/outline questions → use get_course_outline
  - Specific content questions → use search_course_content
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Multi-Step Query Strategy:
- Determine if you need information from one tool to use another
- Make first tool call to gather prerequisite information
- Use results to make a more targeted second tool call if needed
- Synthesize all results into a comprehensive answer
- If you cannot answer after 2 tool calls, provide the best answer possible with available information

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use appropriate tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "according to the outline"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str, base_url: str = ""):
        # Initialize client with optional base_url for proxy support
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: str | None = None,
        tools: list | None = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution with multi-round support
        if response.stop_reason == "tool_use" and tool_manager:
            return self._execute_tool_rounds(
                response, api_params, tool_manager, max_rounds=2
            )

        # Return direct response
        return self._extract_text_response(response)

    def _format_content_blocks(self, content_blocks) -> list[dict]:
        """Convert API response content blocks to message format"""
        formatted = []
        for block in content_blocks:
            if block.type == "text":
                formatted.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                formatted.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return formatted

    def _execute_all_tools(self, content_blocks, tool_manager) -> list[dict]:
        """Execute all tool calls and return formatted results"""
        tool_results = []
        for block in content_blocks:
            if block.type == "tool_use":
                try:
                    result = tool_manager.execute_tool(block.name, **block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
                except Exception as e:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Tool execution failed: {str(e)}",
                            "is_error": True,
                        }
                    )
        return tool_results

    def _extract_text_response(self, response) -> str:
        """Safely extract text from response"""
        if not response.content or len(response.content) == 0:
            return "I apologize, but I couldn't generate a response."

        text_parts = [block.text for block in response.content if block.type == "text"]
        return (
            "".join(text_parts)
            if text_parts
            else "I apologize, but I couldn't generate a response."
        )

    def _is_duplicate_call(self, tool_calls: list, history: list[tuple]) -> bool:
        """Check if any tool call is a duplicate to prevent infinite loops"""
        for tool_call in tool_calls:
            for prev_name, prev_input in history:
                if tool_call.name == prev_name:
                    # Normalize inputs for comparison
                    normalized_current = {
                        k: str(v).lower().strip() for k, v in tool_call.input.items()
                    }
                    normalized_prev = {
                        k: str(v).lower().strip() for k, v in prev_input.items()
                    }
                    if normalized_current == normalized_prev:
                        return True
        return False

    def _force_final_response(
        self, messages: list[dict], base_params: dict[str, Any], last_response
    ) -> str:
        """Generate final response when max rounds reached or error occurs"""
        # If last response has text, use it
        if last_response.stop_reason != "tool_use" and last_response.content:
            return self._extract_text_response(last_response)

        # If last response is tool_use, add it to messages and request final answer
        if last_response.stop_reason == "tool_use":
            messages.append(
                {
                    "role": "assistant",
                    "content": self._format_content_blocks(last_response.content),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": "You have reached the maximum number of tool calls. Please provide your final answer based on the information gathered.",
                }
            )

        # Make final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
            + "\n\nIMPORTANT: Provide your answer directly in plain text. Do not use any tools.",
            "max_tokens": 2000,
        }

        try:
            final_response = self.client.messages.create(**final_params)

            # Handle proxy bug (preserve existing logic)
            if (
                final_response.stop_reason == "stop_sequence"
                and hasattr(final_response, "stop_sequence")
                and "function_calls" in str(final_response.stop_sequence)
            ):
                # Use existing fallback mechanism - extract search results from messages
                search_content = ""
                for msg in messages:
                    if msg.get("role") == "user" and isinstance(
                        msg.get("content"), list
                    ):
                        for content_item in msg["content"]:
                            if (
                                isinstance(content_item, dict)
                                and content_item.get("type") == "tool_result"
                            ):
                                search_content += (
                                    content_item.get("content", "") + "\n\n"
                                )

                # Create a simple single-turn request with search results embedded
                fallback_query = f"{base_params['messages'][0]['content']}\n\nRelevant course information:\n{search_content}"

                fallback_response = self.client.messages.create(
                    **self.base_params,
                    messages=[{"role": "user", "content": fallback_query}],
                    system=base_params["system"],
                )

                if fallback_response.content and len(fallback_response.content) > 0:
                    return fallback_response.content[0].text
                else:
                    return "I apologize, but I couldn't generate a response. Please try again."

            return self._extract_text_response(final_response)
        except Exception as e:
            return f"Error generating final response: {str(e)}"

    def _execute_tool_rounds(
        self,
        initial_response,
        base_params: dict[str, Any],
        tool_manager,
        max_rounds: int = 2,
    ) -> str:
        """
        Execute tool calls across multiple rounds, supporting up to max_rounds sequential tool calls.

        Args:
            initial_response: The response containing initial tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            max_rounds: Maximum number of tool calling rounds (default: 2)

        Returns:
            Final response text after tool execution
        """
        messages = base_params["messages"].copy()
        current_response = initial_response
        round_count = 0
        tool_call_history = []  # Track for duplicate detection

        while round_count < max_rounds:
            # Termination: No tool use
            if current_response.stop_reason != "tool_use":
                return self._extract_text_response(current_response)

            # Termination: Empty content
            if not current_response.content or len(current_response.content) == 0:
                return "I apologize, but I couldn't generate a response."

            # Check for duplicate tool calls (infinite loop prevention)
            tool_calls = [
                block for block in current_response.content if block.type == "tool_use"
            ]
            if self._is_duplicate_call(tool_calls, tool_call_history):
                return self._force_final_response(
                    messages, base_params, current_response
                )

            # Add assistant's tool use to messages
            messages.append(
                {
                    "role": "assistant",
                    "content": self._format_content_blocks(current_response.content),
                }
            )

            # Execute all tools and collect results
            tool_results = self._execute_all_tools(
                current_response.content, tool_manager
            )

            # Termination: Tool execution failed
            if any(result.get("is_error") for result in tool_results):
                messages.append({"role": "user", "content": tool_results})
                return self._force_final_response(
                    messages, base_params, current_response
                )

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})

            # Track tool calls
            for block in current_response.content:
                if block.type == "tool_use":
                    tool_call_history.append((block.name, block.input))

            round_count += 1

            # Prepare next API call with tools still available
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params.get("tools"),  # Keep tools available
                "tool_choice": {"type": "auto"},
            }

            # Get next response
            try:
                current_response = self.client.messages.create(**next_params)
            except Exception as e:
                return f"Error during tool execution: {str(e)}"

        # Max rounds reached, force final response
        return self._force_final_response(messages, base_params, current_response)
