"""Integration tests for the Andromeda agent graph."""

import pytest

from agent import graph
from langchain_core.messages import HumanMessage

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
async def test_agent_initialization() -> None:
    """Test that the agent graph is initialized correctly."""
    assert graph is not None
    assert graph.invoke is not None


@pytest.mark.langsmith
async def test_agent_with_simple_query() -> None:
    """Test agent with a simple chat query."""
    inputs = {
        "messages": [HumanMessage(content="Hello, what can you help me with?")],
        "user_input": "Hello, what can you help me with?",
    }
    result = await graph.ainvoke(inputs)
    assert result is not None
    assert "messages" in result
    assert len(result["messages"]) > 1


@pytest.mark.langsmith
async def test_agent_with_web_search() -> None:
    """Test agent routes web search when search is enabled."""
    inputs = {
        "messages": [HumanMessage(content="Search the web for Python programming")],
        "user_input": "Search the web for Python programming",
        "web_search_enabled": True,
    }
    result = await graph.ainvoke(inputs)
    assert result is not None
    assert result.get("agent_route") == "run_web_search"


@pytest.mark.langsmith
async def test_agent_with_file_search() -> None:
    """Test agent routes file search queries to run_file_search."""
    inputs = {
        "messages": [HumanMessage(content="Find all CSV files in current directory")],
        "user_input": "Find all CSV files in current directory",
    }
    result = await graph.ainvoke(inputs)
    assert result is not None
    assert result.get("agent_route") == "run_file_search"


@pytest.mark.langsmith
async def test_agent_routes_gmail_inbox(monkeypatch) -> None:
    """Test agent routes unread Gmail inbox requests to run_gmail_inbox."""
    import importlib

    from langchain_core.messages import AIMessage

    graph_module = importlib.import_module("agent.graph")
    monkeypatch.setattr(
        graph_module,
        "gmail_inbox_fallback_response",
        lambda _user_text: AIMessage(content="Gmail inbox auto-reply complete."),
    )

    inputs = {
        "messages": [
            HumanMessage(content="Process my unread emails in Gmail inbox")
        ],
        "user_input": "Process my unread emails in Gmail inbox",
    }
    result = await graph.ainvoke(inputs)
    assert result is not None
    assert result.get("agent_route") == "run_gmail_inbox"
