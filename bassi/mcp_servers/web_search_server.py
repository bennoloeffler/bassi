"""
Web Search MCP Server

Provides web search capability using Tavily API as an SDK MCP server
"""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


@tool(
    "search",
    "Search the web for current information using Tavily API",
    {"query": str, "max_results": int},
)
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search the web using Tavily API

    Args:
        query: The search query
        max_results: Maximum number of results (default 5)

    Returns:
        Search results with titles, URLs, and content snippets
    """
    query = args["query"]
    max_results = args.get("max_results", 5)

    try:
        from tavily import TavilyClient  # type: ignore

        from bassi.config import get_config_manager

        # Get API key
        config_manager = get_config_manager()
        api_key = config_manager.get_tavily_api_key()

        if not api_key:
            error_msg = (
                "Tavily API key not configured. "
                "Set TAVILY_API_KEY in .env or ~/.bassi/config.json"
            )
            return {
                "content": [{"type": "text", "text": f"ERROR: {error_msg}"}],
                "isError": True,
            }

        # Perform search
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)

        # Format results
        if not response.get("results"):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No results found for query: {query}",
                    }
                ]
            }

        results_text = f"Search Results for: {query}\n\n"
        for i, item in enumerate(response["results"], 1):
            title = item.get("title", "N/A")
            url = item.get("url", "N/A")
            content = item.get("content", "N/A")

            results_text += f"{i}. {title}\n"
            results_text += f"   URL: {url}\n"
            results_text += f"   {content}\n\n"

        return {"content": [{"type": "text", "text": results_text}]}

    except ImportError:
        error_msg = "Tavily package not installed. Run: uv add tavily-python"
        return {
            "content": [{"type": "text", "text": f"ERROR: {error_msg}"}],
            "isError": True,
        }

    except Exception as e:
        error_msg = f"Error performing web search: {str(e)}"
        return {
            "content": [{"type": "text", "text": f"ERROR: {error_msg}"}],
            "isError": True,
        }


def create_web_search_mcp_server():
    """Create and return the Web Search MCP server"""
    return create_sdk_mcp_server(
        name="web",
        version="1.0.0",
        tools=[web_search],
    )
