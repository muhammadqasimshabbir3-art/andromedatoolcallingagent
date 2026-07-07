"""Andromeda Agent - LangGraph agent with explicit decision-agent workflow nodes."""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal, NotRequired

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from agent.async_utils import run_in_thread
from agent.custom_tools.calculator_tools import (
    casio_calculator,
    solve_math_batch_tool,
)
from agent.custom_tools.gmail_inbox_tools import (
    process_gmail_inbox,
    read_unread_gmail,
    reply_to_gmail_message,
)
from agent.custom_tools.pdf_generator import generate_pdf_report, generate_table_report
from agent.routing import (
    file_search_response,
    get_latest_user_text,
    gmail_inbox_fallback_response,
    is_empty_ai_message,
    is_math_query,
    location_response,
    math_fallback_response,
    wants_email,
    wants_gmail_inbox_reply,
    web_search_response,
)
from agent.task_planner import (
    needs_file_search,
    needs_location,
    plan_tasks,
    should_use_web_search,
)
from agent.workflow_executor import execute_task_plan

load_dotenv()

SYSTEM_PROMPT = (
    "You are Solar, a helpful multi-tool assistant. "
    "Your name is Solar. "
    "You have access to the full conversation history — use prior messages for context "
    "when the user refers to earlier results (e.g. 'email that', 'explain that', 'what did I ask'). "
    "For math, use calculator tools. For PDFs use generate_pdf_report. "
    "Use Gmail API tools only (no SMTP). "
    "You can read unread Gmail emails, summarize contents, and reply in-thread. "
    "File search and web search run through dedicated graph nodes when detected."
)

GRAPH_RUN_CONFIG = {"recursion_limit": 100}

AgentRoute = Literal[
    "execute_workflow",
    "run_calculator",
    "run_email",
    "run_gmail_inbox",
    "math_and_email",
    "run_web_search",
    "run_file_search",
    "run_location",
    "call_model",
]


class State(TypedDict):
    """State for the Andromeda agent graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    user_input: NotRequired[str]
    web_search_enabled: NotRequired[bool]
    task_plan_summary: NotRequired[str]
    agent_route: NotRequired[AgentRoute]
    user_latitude: NotRequired[float]
    user_longitude: NotRequired[float]


_model_instance = None


def _init_model():
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")

    _model_instance = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=api_key,
    )
    return _model_instance


def get_model():
    return _init_model()


# Tools used only by call_model → tools loop.
llm_tools = [
    casio_calculator,
    solve_math_batch_tool,
    generate_pdf_report,
    generate_table_report,
    read_unread_gmail,
    reply_to_gmail_message,
    process_gmail_inbox,
]

tool_node = ToolNode(llm_tools)


def _is_fresh_user_turn(messages: list[AnyMessage]) -> bool:
    if not messages:
        return False
    last_message = messages[-1]
    return isinstance(last_message, HumanMessage) or getattr(
        last_message, "type", None
    ) == "human"


def _prepare_messages(state: State) -> tuple[list[AnyMessage], list[AnyMessage]]:
    """Build conversation messages and any new messages to append to state."""
    existing_messages = list(state.get("messages") or [])
    state_updates: list[AnyMessage] = []

    if existing_messages:
        return existing_messages, state_updates

    user_input = state.get("user_input", "")
    if not user_input:
        raise ValueError(
            "No input provided. Pass messages and/or user_input in graph state."
        )

    human_message = HumanMessage(content=user_input)
    state_updates.append(human_message)
    return [human_message], state_updates


def _pick_route(
    user_text: str,
    messages: list[AnyMessage],
    web_search_enabled: bool = False,
) -> AgentRoute:
    """Decide which graph branch should handle the request."""
    if not _is_fresh_user_turn(messages):
        return "call_model"

    # Prioritize Gmail inbox auto-reply intent before generic workflow planning.
    if wants_gmail_inbox_reply(user_text):
        return "run_gmail_inbox"

    task_plan = plan_tasks(user_text, web_search_enabled)
    if task_plan.is_multi_task:
        return "execute_workflow"

    if is_math_query(user_text) and wants_email(user_text):
        return "math_and_email"

    if is_math_query(user_text):
        return "run_calculator"

    if wants_email(user_text):
        return "run_email"

    if should_use_web_search(user_text, web_search_enabled):
        return "run_web_search"

    if needs_location(user_text):
        return "run_location"

    if needs_file_search(user_text):
        return "run_file_search"

    return "call_model"


async def prepare_input(state: State) -> dict[str, Any]:
    """Normalize input into conversation messages."""
    _, state_updates = _prepare_messages(state)
    if state_updates:
        return {"messages": state_updates}
    return {}


async def decision_agent(state: State) -> dict[str, Any]:
    """Analyze the user query and choose the execution path."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    web_search_enabled = bool(state.get("web_search_enabled", False))
    task_plan = plan_tasks(user_text, web_search_enabled)
    route = _pick_route(user_text, messages, web_search_enabled)

    if task_plan.use_web_search or task_plan.use_file_search or task_plan.tasks:
        summary = task_plan.summary()
    else:
        summary = "General conversation"

    return {
        "task_plan_summary": summary,
        "agent_route": route,
    }


async def execute_workflow(state: State) -> dict[str, Any]:
    """Run multi-task workflow: intro → research/math → PDF → email."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    web_search_enabled = bool(state.get("web_search_enabled", False))
    task_plan = plan_tasks(user_text, web_search_enabled)
    response = await run_in_thread(execute_task_plan, task_plan)
    return {"messages": [response]}


async def run_calculator(state: State) -> dict[str, Any]:
    """Direct calculator path for single or batch math."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    response = await run_in_thread(math_fallback_response, user_text)
    return {"messages": [response]}


async def run_email(state: State) -> dict[str, Any]:
    """Legacy email route now mapped to Gmail API inbox flow."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    response = await run_in_thread(gmail_inbox_fallback_response, user_text)
    return {"messages": [response]}


async def run_gmail_inbox(state: State) -> dict[str, Any]:
    """Process unread Gmail inbox messages via OAuth and Ollama auto-replies."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    response = await run_in_thread(gmail_inbox_fallback_response, user_text)
    return {"messages": [response]}


async def math_and_email(state: State) -> dict[str, Any]:
    """Calculate math then process Gmail inbox action."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    math_response = await run_in_thread(math_fallback_response, user_text)
    email_response = await run_in_thread(
        gmail_inbox_fallback_response,
        user_text,
    )
    combined = AIMessage(
        content=f"{math_response.content}\n\n---\n\n{email_response.content}"
    )
    return {"messages": [combined]}


async def run_web_search(state: State) -> dict[str, Any]:
    """Web search when the user enabled search and the query needs it."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)

    if not state.get("web_search_enabled", False):
        response = AIMessage(
            content=(
                "Web search is turned off. Enable the 🔍 search toggle in the "
                "input bar to search the web."
            )
        )
        return {"messages": [response]}

    response = await run_in_thread(web_search_response, user_text)
    return {"messages": [response]}


async def run_file_search(state: State) -> dict[str, Any]:
    """Search local files when the decision agent detects a file-search request."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    response = await run_in_thread(file_search_response, user_text)
    return {"messages": [response]}


async def run_location(state: State) -> dict[str, Any]:
    """Reverse-geocode coordinates and search nearby places."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    latitude = float(state.get("user_latitude", 0.0) or 0.0)
    longitude = float(state.get("user_longitude", 0.0) or 0.0)
    response = await run_in_thread(location_response, user_text, latitude, longitude)
    return {"messages": [response]}


async def call_model(state: State) -> dict[str, Any]:
    """LLM path for general chat and dynamic tool selection."""
    messages, _ = _prepare_messages(state)

    has_system_message = any(
        getattr(message, "type", None) == "system" for message in messages
    )
    llm_messages = (
        [SystemMessage(content=SYSTEM_PROMPT), *messages]
        if not has_system_message
        else messages
    )

    user_text = get_latest_user_text(llm_messages)
    model_with_tools = get_model().bind_tools(llm_tools)
    response = await model_with_tools.ainvoke(llm_messages)

    if (
        isinstance(response, AIMessage)
        and not response.tool_calls
        and is_empty_ai_message(response)
        and is_math_query(user_text)
    ):
        response = await run_in_thread(math_fallback_response, user_text)
    elif isinstance(response, AIMessage) and is_empty_ai_message(response):
        if response.tool_calls:
            tool_names = ", ".join(
                tc.get("name", "tool") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                for tc in response.tool_calls
            )
            response.content = f"Calling tools: {tool_names}"
        else:
            response.content = "I could not generate a response. Please try again."

    return {"messages": [response]}


def route_after_decision(state: State) -> AgentRoute:
    """Route from decision_agent to the chosen execution node."""
    return state.get("agent_route", "call_model")


def route_after_model(state: State) -> Literal["tools", END]:
    """Route from call_model to tools or end."""
    messages = state.get("messages") or []
    if not messages:
        return END

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


# ---------------------------------------------------------------------------
# Graph: visible workflow in LangGraph Studio
#
#   START → prepare_input → decision_agent →
#       execute_workflow | run_calculator | run_email | run_gmail_inbox |
#       math_and_email | run_web_search | run_file_search | call_model → tools ↺ → END
# ---------------------------------------------------------------------------

graph_builder = StateGraph(State)

graph_builder.add_node("prepare_input", prepare_input)
graph_builder.add_node("decision_agent", decision_agent)
graph_builder.add_node("execute_workflow", execute_workflow)
graph_builder.add_node("run_calculator", run_calculator)
graph_builder.add_node("run_email", run_email)
graph_builder.add_node("run_gmail_inbox", run_gmail_inbox)
graph_builder.add_node("math_and_email", math_and_email)
graph_builder.add_node("run_web_search", run_web_search)
graph_builder.add_node("run_file_search", run_file_search)
graph_builder.add_node("run_location", run_location)
graph_builder.add_node("call_model", call_model)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "prepare_input")
graph_builder.add_edge("prepare_input", "decision_agent")
graph_builder.add_conditional_edges(
    "decision_agent",
    route_after_decision,
    {
        "execute_workflow": "execute_workflow",
        "run_calculator": "run_calculator",
        "run_email": "run_email",
        "run_gmail_inbox": "run_gmail_inbox",
        "math_and_email": "math_and_email",
        "run_web_search": "run_web_search",
        "run_file_search": "run_file_search",
        "run_location": "run_location",
        "call_model": "call_model",
    },
)
graph_builder.add_edge("execute_workflow", END)
graph_builder.add_edge("run_calculator", END)
graph_builder.add_edge("run_email", END)
graph_builder.add_edge("run_gmail_inbox", END)
graph_builder.add_edge("math_and_email", END)
graph_builder.add_edge("run_web_search", END)
graph_builder.add_edge("run_file_search", END)
graph_builder.add_edge("run_location", END)
graph_builder.add_conditional_edges("call_model", route_after_model)
graph_builder.add_edge("tools", "call_model")

graph = graph_builder.compile(name="Andromeda Agent")
