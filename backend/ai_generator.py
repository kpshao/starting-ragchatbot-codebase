import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
- **get_course_outline**: Use for questions about course structure, lesson lists, or what topics a course covers
- **search_course_content**: Use for questions about specific course content or detailed educational materials

Tool Usage Rules:
- **One tool call per query maximum**
- Choose the appropriate tool based on the question type:
  - Course structure/outline questions → use get_course_outline
  - Specific content questions → use search_course_content
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

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
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
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
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Convert content blocks to proper format
        content_blocks = []
        for block in initial_response.content:
            if block.type == "text":
                content_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": content_blocks})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, 
                    **content_block.input
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Prepare final API call without tools
        final_system = base_params["system"] + "\n\nIMPORTANT: Provide your answer directly in plain text. Do not use any XML tags or special formatting."

        final_params = {
            **self.base_params,
            "messages": messages,
            "system": final_system,
            "max_tokens": 2000
        }

        # Get final response
        final_response = self.client.messages.create(**final_params)

        # Handle proxy bug: if response is truncated by function_calls stop sequence
        if (final_response.stop_reason == "stop_sequence" and
            hasattr(final_response, 'stop_sequence') and
            'function_calls' in str(final_response.stop_sequence)):


            # Extract search results from tool_results
            search_content = ""
            if tool_results:
                search_content = tool_results[0].get("content", "")

            # Create a simple single-turn request with search results embedded
            fallback_query = f"{base_params['messages'][0]['content']}\n\nRelevant course information:\n{search_content}"

            fallback_response = self.client.messages.create(
                **self.base_params,
                messages=[{"role": "user", "content": fallback_query}],
                system=base_params["system"]
            )

            if fallback_response.content and len(fallback_response.content) > 0:
                return fallback_response.content[0].text
            else:
                return "I apologize, but I couldn't generate a response. Please try again."

        # Handle normal response
        if not final_response.content or len(final_response.content) == 0:
            return "I apologize, but I couldn't generate a response. Please try again."

        return final_response.content[0].text