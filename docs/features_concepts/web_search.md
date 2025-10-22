# Web Search Feature

## Purpose
Enable the bassi agent to search the web for current information, facts, and real-time data that may not be available in the AI model's training data.

## Implementation

### Technology: Tavily API
- **Service**: Tavily Search API (https://www.tavily.com/)
- **Pricing**: 1,000 free searches per month (sufficient for personal use)
- **Quality**: AI-optimized search results designed specifically for LLM agents
- **Python SDK**: `tavily-python` package

### Key Features
- Real-time web search capability
- AI-optimized results (factual, relevant, concise)
- Easy integration with existing tool architecture
- Graceful error handling

## Configuration

### API Key Setup
1. Sign up at https://www.tavily.com/
2. Get your API key from the dashboard
3. Configure in bassi:
   - Stored in `~/.bel-personal-assi/config.json`
   - Key: `tavily_api_key`

## Usage

The agent can use the web search tool when it needs to:
- Find current information (news, events, prices)
- Look up facts not in its training data
- Research topics in real-time
- Verify information from the web

### Example Queries
- "What's the current weather in Berlin?"
- "What are the latest Python 3.12 features?"
- "Find recent news about AI developments"

## Tool Interface

### Function: `web_search_tool`
```python
def web_search_tool(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Search the web using Tavily API

    Args:
        query: Search query string
        max_results: Maximum number of results (default 5)

    Returns:
        Dictionary with:
        - success: bool
        - results: list of dicts with title, url, content
        - error: str (if failed)
    """
```

### Tool Metadata
Registered with Anthropic API as "web_search" tool with appropriate schema.

## Integration with Agent
- Added to tool registry in `bassi/agent.py`
- System prompt updated to inform agent of web search capability
- Status bar shows "🔍 SEARCHING WEB: {query}" during execution

## Iteration
Part of **Iteration 2** in the vision roadmap.

## Testing
- Unit tests with mocked API responses
- Error handling tests (missing API key, API failures)
- Result formatting validation

## Future Enhancements
- Cache recent searches to avoid duplicate API calls
- Add search filters (date, domain, language)
- Implement rate limiting awareness
- Add search result summarization
