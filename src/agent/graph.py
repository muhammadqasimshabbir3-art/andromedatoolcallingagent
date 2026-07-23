"""Andromeda Agent - LangGraph agent with explicit decision-agent workflow nodes."""

from __future__ import annotations

import os
import uuid
from typing import Annotated, Any, Literal, NotRequired

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from agent.async_utils import run_in_thread
from agent.custom_tools.business_rag_tools import (
    answer_business_rag_sync,
    business_knowledge_rag,
    needs_business_rag,
)
from agent.custom_tools.calculator_tools import (
    casio_calculator,
    solve_math_batch_tool,
)
from agent.custom_tools.db_audit_log import log_db_security_event
from agent.custom_tools.db_safety_agent import (
    DbSafetyVerdict,
    db_guard_pass_summary,
    db_mutation_block_message,
    evaluate_read_only_guard,
    generate_readonly_guard_joke,
    is_db_mutation_request,
    needs_ai_db_intent_check,
    needs_semantic_db_intent_check,
)
from agent.custom_tools.database_tools import (
    SQL_GENERATOR_SYSTEM,
    ensure_store_sources_footer,
    extract_sql_from_text,
    load_store_schema,
    needs_store_analytics,
    needs_store_database,
    parse_store_query_tool_result,
    query_store_database,
    refresh_store_schema,
)
from agent.custom_tools.gmail_inbox_tools import (
    process_gmail_inbox,
    read_unread_gmail,
    reply_to_gmail_message,
)
from agent.custom_tools.location_tools import get_live_location
from agent.custom_tools.pdf_generator import generate_pdf_report, generate_table_report
from agent.pdf_analysis import pdf_analysis_response
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
    "For location and nearby-place requests, use the live location tools. "
    "For store / inventory / product / customer / order / sales totals questions: "
    "the database is PERMANENTLY READ-ONLY. YOU may only decide a single SELECT / "
    "WITH … SELECT, then MUST call query_store_database. Never invent tool results. "
    "Never claim data was inserted, updated, or deleted. If the tool returns "
    "success=false, explain the error — do not pretend a write succeeded. "
    "After the tool returns, answer only from that JSON/table. "
    "For business knowledge (policies, warranty, FAQ, SOP, shipping rules, product care): "
    "use business_knowledge_rag — retrieve semi-structured docs then answer from that context. "
    "Store schema (from solar_store_schema.sql):\n"
    "{store_schema}\n"
    "Use Gmail API tools only (no SMTP). "
    "You can read unread Gmail emails, summarize contents, and reply in-thread. "
    "File search and web search run through dedicated graph nodes when detected."
)

STORE_FORCE_PROMPT = (
    "This is a Solar Store READ-ONLY database question. "
    "You are the SQL QUERY WRITER: emit ONLY a single SELECT / WITH … SELECT. "
    f"{SQL_GENERATOR_SYSTEM}"
    "The schema in solar_store_schema.sql was just refreshed from Neon. "
    "Call query_store_database with that read SQL. "
    "Do not answer with product names until the tool runs. "
    "Never fabricate rows. Never claim a mutation succeeded."
)

STORE_ANALYTICS_PROMPT = (
    "This is a Solar Store BUSINESS ANALYTICS question (profit, revenue, stats, KPIs). "
    "The database is permanently read-only.\n"
    "Workflow you MUST follow:\n"
    "1) Call query_store_database with SELECT(s) that pull the relevant facts from Neon "
    "(orders, order_items, products cost/price, stores, customers) for the period asked "
    "(e.g. this month). Prefer aggregations: SUM, COUNT, AVG, GROUP BY store/category.\n"
    "2) After rows return, if you need ratios, margins, growth %, or totals of totals, "
    "call casio_calculator with ONLY a pure numeric expression using digits from the "
    "query result (example: '(15200-9800)/15200*100'). "
    "NEVER pass SQL, column names, or table.field (e.g. order_items.line_total) "
    "to casio_calculator.\n"
    "3) Final answer: explain insights for decision-making using ONLY tool results. "
    "Do not invent numbers. Do NOT write a Sources section — it is appended automatically. "
    "If a tool fails, explain the failure — never claim data was changed."
)

STORE_GROUNDING_PROMPT = (
    "CRITICAL GROUNDING RULE: Your previous query_store_database tool result is the "
    "ONLY source of truth (structured JSON with success/rows/row_count or error). "
    "If success is false, explain the error and do NOT invent rows or claim a write. "
    "List ONLY values that appear in that tool result. "
    "Do not add products, customers, or numbers that are not in the tool output. "
    "If asked for 'low stock', use the stock_qty values from the rows returned. "
    "For profit/analytics, you may use casio_calculator on numbers that already "
    "appeared in the tool output. "
    "Never claim INSERT/UPDATE/DELETE succeeded — this agent cannot mutate data. "
    "Do NOT write a Sources section yourself — sources are appended automatically."
)

# Cap tool↔model ping-pong for one user turn (schema fetch + retries used to explode).
MAX_TOOL_ROUNDS_PER_TURN = 2

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
    "run_store_database",
    "run_business_rag",
    "run_pdf_analysis",
    "reject_db_mutation",
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
    pdf_data_base64: NotRequired[str]
    pdf_filename: NotRequired[str]
    pdf_summarize_only: NotRequired[bool]
    generated_pdf_path: NotRequired[str]
    generated_pdf_filename: NotRequired[str]
    db_guard_blocked: NotRequired[bool]
    db_guard_detail: NotRequired[str]
    db_guard_layer: NotRequired[str]


_model_instance = None
_creative_model_instance = None


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


def _init_creative_model():
    """Higher-temperature Groq model so refusal jokes change every time."""
    global _creative_model_instance
    if _creative_model_instance is not None:
        return _creative_model_instance

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")

    _creative_model_instance = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.95,
        api_key=api_key,
    )
    return _creative_model_instance


def get_model():
    """Return the shared chat model instance."""
    return _init_model()


# Tools used only by call_model → tools loop.
# Store schema is in SYSTEM_PROMPT — only query_store_database is bound (fewer hops).
llm_tools = [
    casio_calculator,
    solve_math_batch_tool,
    get_live_location,
    generate_pdf_report,
    generate_table_report,
    read_unread_gmail,
    reply_to_gmail_message,
    process_gmail_inbox,
    query_store_database,
    business_knowledge_rag,
]

tool_node = ToolNode(llm_tools)


def _messages_since_last_human(messages: list[AnyMessage]) -> list[AnyMessage]:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, HumanMessage) or getattr(message, "type", None) == "human":
            return messages[index + 1 :]
    return list(messages)


def _tool_rounds_this_turn(messages: list[AnyMessage]) -> int:
    """Count AI messages that requested tools since the latest human message."""
    return sum(
        1
        for message in _messages_since_last_human(messages)
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None)
    )


def _latest_store_query_tool_content(messages: list[AnyMessage]) -> str | None:
    """Return the latest successful query_store_database tool payload, if any."""
    for message in reversed(_messages_since_last_human(messages)):
        if not isinstance(message, ToolMessage):
            continue
        if (getattr(message, "name", "") or "") != "query_store_database":
            continue
        content = str(message.content)
        parsed = parse_store_query_tool_result(content)
        if parsed.get("success") is False:
            return None
        failed = (
            content.startswith("Database query error:")
            or "Query rejected:" in content
            or "Only SELECT statements are allowed" in content
            or "Connection failed:" in content
        )
        if failed:
            return None
        return content
    return None


def _has_successful_store_query(messages: list[AnyMessage]) -> bool:
    return _latest_store_query_tool_content(messages) is not None


def _has_calculator_tool_result(messages: list[AnyMessage]) -> bool:
    for message in reversed(_messages_since_last_human(messages)):
        if not isinstance(message, ToolMessage):
            continue
        name = (getattr(message, "name", "") or "")
        if name in {"casio_calculator", "solve_math_batch_tool"}:
            content = str(message.content)
            if content and "Calculator error" not in content:
                return True
    return False


def _should_force_final_answer(
    messages: list[AnyMessage],
    *,
    user_text: str = "",
) -> bool:
    """Stop tool ping-pong after enough evidence (or too many tool rounds)."""
    if _tool_rounds_this_turn(messages) >= MAX_TOOL_ROUNDS_PER_TURN:
        return True
    if needs_store_analytics(user_text):
        # Analytics: allow SQL then optional calculator before forcing prose.
        if not _has_successful_store_query(messages):
            return False
        if _has_calculator_tool_result(messages):
            return True
        # One free hop after SQL for casio_calculator; force after that.
        return _tool_rounds_this_turn(messages) >= 2
    return _has_successful_store_query(messages)


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

    # Read-Only Guard final decision lives in decision_agent (rules + AI).
    # Keep _pick_route free of LLM so unit tests stay sync/fast.

    # Prioritize Gmail inbox auto-reply intent before generic workflow planning.
    if wants_gmail_inbox_reply(user_text):
        return "run_gmail_inbox"

    task_plan = plan_tasks(user_text, web_search_enabled)
    if task_plan.is_multi_task:
        return "execute_workflow"

    if needs_location(user_text):
        return "run_location"

    # Knowledge / policy questions → retrieve semi-structured docs + RAG.
    if needs_business_rag(user_text):
        return "run_business_rag"

    # Store Q&A: LLM decides SQL and must call query_store_database (tools node).
    if needs_store_database(user_text):
        return "call_model"

    if is_math_query(user_text) and wants_email(user_text):
        return "math_and_email"

    if is_math_query(user_text):
        return "run_calculator"

    if wants_email(user_text):
        return "run_email"

    if should_use_web_search(user_text, web_search_enabled):
        return "run_web_search"

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

    guard_verdict: DbSafetyVerdict | None = None
    # Semantic READ/WRITE guard before any SQL path (defense in depth).
    if _is_fresh_user_turn(messages) and needs_semantic_db_intent_check(user_text):
        guard_verdict = await run_in_thread(
            evaluate_read_only_guard,
            user_text,
            _plain_llm_invoke,
        )
        log_db_security_event(
            event="intent_classification",
            user_prompt=user_text,
            intent=guard_verdict.intent,
            confidence=guard_verdict.confidence,
            layer=guard_verdict.layer,
            blocked=guard_verdict.blocked,
            extra={"reason": guard_verdict.reason, "mutation": guard_verdict.mutation_kind},
        )

    if guard_verdict is not None and guard_verdict.blocked:
        route: AgentRoute = "reject_db_mutation"
    elif state.get("pdf_data_base64"):
        route = "run_pdf_analysis"
    else:
        route = _pick_route(user_text, messages, web_search_enabled)

    if route == "reject_db_mutation" and guard_verdict is not None:
        summary = db_guard_pass_summary(guard_verdict)
    elif guard_verdict is not None and not guard_verdict.blocked:
        # Allowed after AI review — continue with normal route summary.
        if needs_business_rag(user_text):
            summary = (
                f"{db_guard_pass_summary(guard_verdict)} → "
                "Business RAG trust layer"
            )
        elif needs_store_database(user_text):
            summary = (
                f"{db_guard_pass_summary(guard_verdict)} → "
                "LLM → query_store_database"
            )
        elif task_plan.use_web_search or task_plan.use_file_search or task_plan.tasks:
            summary = f"{db_guard_pass_summary(guard_verdict)} → {task_plan.summary()}"
        else:
            summary = db_guard_pass_summary(guard_verdict)
    elif task_plan.use_web_search or task_plan.use_file_search or task_plan.tasks:
        summary = task_plan.summary()
    elif needs_business_rag(user_text):
        summary = "Business RAG trust layer: retrieve → analyze sources → answer"
    elif needs_store_database(user_text):
        if needs_store_analytics(user_text):
            summary = (
                "Business analytics: Neon SQL → optional calculator → insights"
            )
        else:
            summary = "LLM → query_store_database tool → answer"
    else:
        summary = "General conversation"

    payload: dict[str, Any] = {
        "task_plan_summary": summary,
        "agent_route": route,
    }
    if guard_verdict is not None:
        payload["db_guard_blocked"] = guard_verdict.blocked
        payload["db_guard_layer"] = guard_verdict.layer
        payload["db_guard_detail"] = db_guard_pass_summary(guard_verdict)
    return payload


async def reject_db_mutation(state: State) -> dict[str, Any]:
    """Refuse write intents — never invoke SQL generation or the SQL tool."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    verdict = await run_in_thread(
        evaluate_read_only_guard,
        user_text,
        _plain_llm_invoke,
    )
    joke = await run_in_thread(
        generate_readonly_guard_joke,
        user_text,
        _creative_llm_invoke,
    )
    content = db_mutation_block_message(user_text, verdict, joke=joke)
    log_db_security_event(
        event="final_response",
        user_prompt=user_text,
        intent=verdict.intent,
        confidence=verdict.confidence,
        layer=verdict.layer,
        blocked=True,
        generated_sql="",
        final_response=content,
    )
    return {
        "messages": [AIMessage(content=content)],
        "agent_route": "reject_db_mutation",
        "db_guard_blocked": True,
        "db_guard_layer": verdict.layer,
        "db_guard_detail": db_guard_pass_summary(verdict),
        "task_plan_summary": db_guard_pass_summary(verdict),
    }


async def execute_workflow(state: State) -> dict[str, Any]:
    """Run multi-task workflow: intro → research/math → PDF → email."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    web_search_enabled = bool(state.get("web_search_enabled", False))
    task_plan = plan_tasks(user_text, web_search_enabled)
    result = await run_in_thread(execute_task_plan, task_plan)
    payload: dict[str, Any] = {"messages": [result.message]}
    if result.pdf_path:
        payload["generated_pdf_path"] = result.pdf_path
    if result.pdf_filename:
        payload["generated_pdf_filename"] = result.pdf_filename
    return payload


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


def _plain_llm_invoke(messages: list[dict[str, str]]) -> str:
    """Invoke Groq without tools; return text content."""
    lc_messages: list[AnyMessage] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    response = get_model().invoke(lc_messages)
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def _creative_llm_invoke(messages: list[dict[str, str]]) -> str:
    """Invoke a high-temperature Groq model (for fresh jokes each time)."""
    lc_messages: list[AnyMessage] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    response = _init_creative_model().invoke(lc_messages)
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def _synthesize_store_tool_call(user_text: str) -> AIMessage:
    """Ask the LLM for SQL (no tools), then wrap it as a real tool_call.

    Groq often fails when tool_choice is forced. This still uses the official
    query_store_database tool via the LangGraph tools node — the LLM decides
    the SQL; the tool executes it. Write intents must never reach this helper.
    """
    # Belt: refuse writes even if routing slipped.
    from agent.custom_tools.db_safety_agent import classify_db_access_intent

    rules = classify_db_access_intent(user_text)
    if rules.blocked:
        return AIMessage(content=db_mutation_block_message(user_text, rules))

    schema = refresh_store_schema()
    sql_prompt = (
        f"{SQL_GENERATOR_SYSTEM}\n"
        f"{schema}\n\n"
        "Return ONLY one read-only SELECT or WITH ... SELECT. "
        "No markdown, no explanation, no comments. "
        "If the user asks to change data, reply with REFUSE_WRITE only. "
        "For low stock, ORDER BY stock_qty ASC. Prefer LIMIT 10."
    )
    try:
        sql_raw = _plain_llm_invoke(
            [
                {"role": "system", "content": sql_prompt},
                {"role": "user", "content": user_text},
            ]
        )
        if "REFUSE_WRITE" in str(sql_raw).upper() and "SELECT" not in str(sql_raw).upper():
            return AIMessage(
                content=(
                    "This database is permanently read-only. I cannot change stored data.\n"
                    "Ask a read question instead (for example: which products are low in stock?)."
                )
            )
        sql = extract_sql_from_text(sql_raw)
        log_db_security_event(
            event="sql_generated",
            user_prompt=user_text,
            intent="read",
            generated_sql=sql,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the graph on bad SQL
        log_db_security_event(
            event="sql_generated",
            user_prompt=user_text,
            generated_sql="",
            tool_success=False,
            tool_error=str(exc),
        )
        return AIMessage(
            content=(
                "I could not build a safe read-only SQL query for that request.\n"
                f"Details: {exc}\n\n"
                "If you need return / replace / refund / warranty guidance, ask as a "
                "policy question (for example: “what is our return and refund policy?”). "
                "For live stock or orders, ask a data question (for example: "
                "“which products are low in stock?”)."
            )
        )
    return AIMessage(
        content="Calling tools: query_store_database",
        tool_calls=[
            {
                "name": "query_store_database",
                "args": {"sql": sql},
                "id": f"store_{uuid.uuid4().hex[:12]}",
                "type": "tool_call",
            }
        ],
    )


async def run_store_database(state: State) -> dict[str, Any]:
    """Legacy node: emit a tool call so query_store_database still runs."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    try:
        response = await run_in_thread(_synthesize_store_tool_call, user_text)
    except Exception as exc:  # noqa: BLE001
        response = AIMessage(
            content=f"I could not prepare a store database tool call.\nError: {exc}"
        )
    return {"messages": [response]}


async def run_business_rag(state: State) -> dict[str, Any]:
    """Retrieve semi-structured business docs from Neon, then RAG-answer."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    try:
        answer = await run_in_thread(
            answer_business_rag_sync,
            user_text,
            _plain_llm_invoke,
        )
    except Exception as exc:  # noqa: BLE001
        answer = (
            "I could not run business knowledge RAG.\n"
            f"Error: {exc}\n"
            "Tip: seed docs with `python scripts/seed_business_rag.py`."
        )
    return {"messages": [AIMessage(content=answer)]}


async def run_pdf_analysis(state: State) -> dict[str, Any]:
    """Analyze the uploaded PDF, then answer PDF-grounded questions."""
    messages, _ = _prepare_messages(state)
    user_text = get_latest_user_text(messages)
    response = await pdf_analysis_response(
        question=user_text,
        pdf_data_base64=state.get("pdf_data_base64", ""),
        pdf_filename=state.get("pdf_filename", "uploaded.pdf"),
        summarize_only=bool(state.get("pdf_summarize_only", False)),
    )
    return {"messages": [response]}


async def call_model(state: State) -> dict[str, Any]:
    """LLM path for general chat and dynamic tool selection."""
    messages, _ = _prepare_messages(state)

    has_system_message = any(
        getattr(message, "type", None) == "system" for message in messages
    )
    user_text_preview = get_latest_user_text(messages)
    schema_text = (
        refresh_store_schema()
        if needs_store_database(user_text_preview)
        else load_store_schema()
    )
    llm_messages: list[AnyMessage] = (
        [
            SystemMessage(content=SYSTEM_PROMPT.format(store_schema=schema_text)),
            *messages,
        ]
        if not has_system_message
        else list(messages)
    )

    user_text = get_latest_user_text(llm_messages)
    store_question = needs_store_database(user_text)
    analytics_question = needs_store_analytics(user_text)
    has_store_rows = _has_successful_store_query(messages)
    force_final = _should_force_final_answer(messages, user_text=user_text)
    needs_store_tool = store_question and not has_store_rows and not force_final

    # After enough tool evidence (or too many rounds), produce the final answer.
    if force_final:
        if has_store_rows:
            llm_messages = [*llm_messages, SystemMessage(content=STORE_GROUNDING_PROMPT)]
        model_with_tools = get_model().bind_tools(llm_tools, tool_choice="none")
    elif has_store_rows and analytics_question and not _has_calculator_tool_result(messages):
        # Data is in — allow one calculator pass for margins / ratios / totals.
        llm_messages = [
            *llm_messages,
            SystemMessage(content=STORE_GROUNDING_PROMPT),
            SystemMessage(
                content=(
                    "You already have Neon query rows. If useful for profit/KPI math, "
                    "call casio_calculator with numbers from those rows only. "
                    "Otherwise write the final analysis now."
                )
            ),
        ]
        model_with_tools = get_model().bind_tools([casio_calculator])
    elif needs_store_tool:
        # Do NOT force tool_choice (Groq crashes). Analytics may also use calculator later.
        if analytics_question:
            llm_messages = [*llm_messages, SystemMessage(content=STORE_ANALYTICS_PROMPT)]
            model_with_tools = get_model().bind_tools(
                [query_store_database, casio_calculator]
            )
        else:
            llm_messages = [*llm_messages, SystemMessage(content=STORE_FORCE_PROMPT)]
            model_with_tools = get_model().bind_tools([query_store_database])
    else:
        model_with_tools = get_model().bind_tools(llm_tools)

    response: AIMessage | Any
    try:
        response = await model_with_tools.ainvoke(llm_messages)
    except Exception:  # noqa: BLE001 — Groq invalid function-call payloads
        if needs_store_tool:
            # LLM still decides SQL; we wrap it as a real tool_call for ToolNode.
            response = await run_in_thread(_synthesize_store_tool_call, user_text)
        else:
            response = AIMessage(
                content="I hit a model error while answering. Please try again."
            )

    if (
        isinstance(response, AIMessage)
        and needs_store_tool
        and not response.tool_calls
    ):
        # Model answered in prose instead of calling the tool — still force the tool path.
        response = await run_in_thread(_synthesize_store_tool_call, user_text)

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

    # Always attach database Sources for final store answers (SQL path).
    if (
        isinstance(response, AIMessage)
        and not response.tool_calls
        and not is_empty_ai_message(response)
    ):
        tool_content = _latest_store_query_tool_content(messages)
        if tool_content:
            response.content = ensure_store_sources_footer(
                str(response.content), tool_content
            )

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
graph_builder.add_node("run_store_database", run_store_database)
graph_builder.add_node("run_business_rag", run_business_rag)
graph_builder.add_node("reject_db_mutation", reject_db_mutation)
graph_builder.add_node("run_pdf_analysis", run_pdf_analysis)
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
        "run_store_database": "run_store_database",
        "run_business_rag": "run_business_rag",
        "reject_db_mutation": "reject_db_mutation",
        "run_pdf_analysis": "run_pdf_analysis",
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
graph_builder.add_conditional_edges("run_store_database", route_after_model)
graph_builder.add_edge("run_business_rag", END)
graph_builder.add_edge("reject_db_mutation", END)
graph_builder.add_edge("run_pdf_analysis", END)
graph_builder.add_conditional_edges("call_model", route_after_model)
graph_builder.add_edge("tools", "call_model")

graph = graph_builder.compile(name="Andromeda Agent")
