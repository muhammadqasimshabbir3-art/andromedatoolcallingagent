"""Intent detection and fallbacks for graph routing."""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from agent.custom_tools.calculator_tools import (
    _parse_problem_lines,
    _result_value,
    evaluate_casio_expression,
    extract_math_expressions,
    solve_math_batch,
)
from agent.custom_tools.location_tools import (
    location_fallback_response as _location_fallback,
)
from agent.custom_tools.location_tools import (
    wants_location as _wants_location,
)

EMAIL_KEYWORDS = (
    "email",
    "e-mail",
    "mail me",
    "send me",
    "send to",
    "send this",
    "via email",
    "send on email",
    "send via email",
    "share via email",
    "send these",
    "send the answers",
    "send answers",
    "gmail",
)

# Gmail API inbox auto-reply (OAuth) — checked before generic SMTP email routing.
GMAIL_INBOX_KEYWORDS = (
    "unread email",
    "unread emails",
    "unread message",
    "unread messages",
    "unread mail",
    "gmail inbox",
    "my inbox",
    "process inbox",
    "read inbox",
    "inbox reply",
    "inbox replies",
    "auto reply",
    "auto-reply",
    "auto reply to",
    "reply to unread",
    "reply to my emails",
    "reply to emails in",
    "gmail api",
    "oauth gmail",
)


def get_latest_user_text(messages: list[AnyMessage]) -> str:
    """Return the most recent human message text."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage) or getattr(message, "type", None) == "human":
            content = message.content
            if isinstance(content, str):
                return content
            return str(content)
    return ""


def is_math_query(text: str) -> bool:
    """Detect whether the user is asking for a calculation."""
    if not text.strip():
        return False

    if wants_location(text):
        return False

    lowered = text.lower()
    expressions = extract_math_expressions(text)
    if expressions:
        return True

    math_words = (
        "calculate",
        "evaluate",
        "factorial",
        "sqrt",
        "log(",
        "ln(",
        "sin",
        "cos",
        "tan",
        "iota",
        "complex",
    )
    if any(word in lowered for word in math_words):
        return True
    if re.search(r"(?i)\bsolve\b", text) and re.search(r"[0-9a-z]\s*=", text):
        return True
    if re.search(r"\d\s*[\+\-\*/\^\%]", text):
        return True
    if re.search(r"(?i)what is\s+.*\d", text):
        return True
    return False


def is_batch_math_query(text: str) -> bool:
    """Detect multiple math problems in one request."""
    expressions = extract_math_expressions(text)
    if len(expressions) >= 2:
        return True
    lines = _parse_problem_lines(text)
    return len(lines) >= 2 and is_math_query(text)


def wants_gmail_inbox_reply(text: str) -> bool:
    """Detect Gmail API inbox auto-reply intent (OAuth unread processing)."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in GMAIL_INBOX_KEYWORDS)


def wants_email(text: str) -> bool:
    """Detect whether the user wants results sent by email (SMTP outbound)."""
    if wants_gmail_inbox_reply(text):
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in EMAIL_KEYWORDS)


def wants_location(text: str) -> bool:
    """Detect whether the user wants location or nearby-place help."""
    return _wants_location(text)


def extract_math_expression(text: str) -> str:
    """Pull a single expression from natural-language math prompts."""
    lines = _parse_problem_lines(text)
    if lines:
        return lines[0]

    cleaned = re.sub(r"(?i)^(what is|calculate|evaluate|solve)\s*", "", text.strip())
    return cleaned.strip()


def is_empty_ai_message(response: AIMessage) -> bool:
    """Check if an AI message has no usable text content."""
    content = response.content
    if content is None or content == "":
        return True
    if isinstance(content, list):
        return len(content) == 0
    if isinstance(content, str):
        return not content.strip()
    return False


def pick_tool_choice(user_text: str) -> dict[str, object] | None:
    """Pick a forced tool when intent is clear."""
    if wants_location(user_text):
        return {"type": "function", "function": {"name": "get_live_location"}}

    if is_math_query(user_text):
        tool_name = (
            "solve_math_batch_tool"
            if is_batch_math_query(user_text)
            else "casio_calculator"
        )
        return {"type": "function", "function": {"name": tool_name}}

    if wants_gmail_inbox_reply(user_text):
        return {"type": "function", "function": {"name": "process_gmail_inbox"}}

    return None


def build_email_body_from_history(messages: list[AnyMessage], user_text: str) -> str:
    """Collect calculator/report answers from the conversation for email."""
    sections: list[str] = [
        "Hello,",
        "",
        "Here are the results you requested from Andromeda:",
        "",
    ]

    for message in messages:
        if not isinstance(message, AIMessage) and getattr(message, "type", None) != "ai":
            continue
        content = message.content
        text = content if isinstance(content, str) else str(content)
        if text and not text.startswith("Calling tools:"):
            sections.append(text)
            sections.append("")

    if user_text:
        sections.extend(["Request:", user_text, ""])

    sections.extend(["Regards,", "Andromeda Agent"])
    return "\n".join(sections).strip()


def email_fallback_response(messages: list[AnyMessage], user_text: str) -> AIMessage:
    """Send email directly when the user asks to share results."""
    if wants_gmail_inbox_reply(user_text):
        return gmail_inbox_fallback_response(user_text)

    from agent.custom_tools.email_tools import send_smtp_email

    subject = "Andromeda Agent — Your Results"
    body = build_email_body_from_history(messages, user_text)
    result = send_smtp_email(subject=subject, body=body)
    return AIMessage(content=result)


def gmail_inbox_fallback_response(user_text: str) -> AIMessage:
    """Read/reply Gmail inbox messages via OAuth (no SMTP)."""
    from agent.custom_tools.gmail_inbox_tools import (
        extract_gmail_inbox_limit,
        process_gmail_inbox_sync,
        read_unread_gmail_sync,
        reply_to_gmail_message_sync,
    )

    lowered = user_text.lower()
    msg_match = re.search(r"(?:message[_\s-]?id[:\s]+)([A-Za-z0-9_-]+)", user_text)
    if "reply" in lowered and msg_match:
        result = reply_to_gmail_message_sync(message_id=msg_match.group(1))
        return AIMessage(content=result)

    if "read" in lowered and "reply" not in lowered:
        limit = extract_gmail_inbox_limit(user_text) or 5
        result = read_unread_gmail_sync(limit=limit)
        return AIMessage(content=result)

    limit = extract_gmail_inbox_limit(user_text)
    result = process_gmail_inbox_sync(limit=limit)
    return AIMessage(content=result)


def web_search_response(user_text: str) -> AIMessage:
    """Run web search and return formatted results."""
    from agent.custom_tools.web_search_tools import web_search_sync

    result = web_search_sync(user_text)
    return AIMessage(content=result)


def file_search_response(user_text: str) -> AIMessage:
    """Search local files and return formatted results."""
    from agent.custom_tools.file_search_tools import _search_files_sync
    from agent.task_planner import extract_file_search_query

    query = extract_file_search_query(user_text)
    extensions = None
    if query.startswith("."):
        extensions = [query]

    result = _search_files_sync(query=query, file_extensions=extensions)
    return AIMessage(content=result)


def math_fallback_response(user_text: str) -> AIMessage:
    """Direct calculator answer when the LLM fails to call tools."""
    expressions = extract_math_expressions(user_text)
    if len(expressions) >= 2:
        lines = [f"Solved {len(expressions)} problem(s) (angle mode: DEG):", ""]
        for index, expression in enumerate(expressions, start=1):
            value = _result_value(expression, "DEG")
            lines.append(f"{index}. {expression}")
            lines.append(f"   = {value}")
            lines.append("")
        summary = "Here are your calculator results:\n\n" + "\n".join(lines).strip()
    elif len(expressions) == 1:
        expression = expressions[0]
        body = evaluate_casio_expression(expression)
        result_line = body.split("Result: ", 1)[-1].strip() if "Result: " in body else body
        summary = f"{expression} = {result_line}"
    elif is_batch_math_query(user_text):
        body = solve_math_batch(user_text)
        summary = "Here are your calculator results:\n\n" + body
    else:
        expression = extract_math_expression(user_text)
        body = evaluate_casio_expression(expression)
        result_line = body.split("Result: ", 1)[-1].strip() if "Result: " in body else body
        summary = f"{expression} = {result_line}"

    return AIMessage(content=summary)


def location_response(
    user_text: str,
    latitude: float = 0.0,
    longitude: float = 0.0,
) -> AIMessage:
    """Return reverse-geocoded address and nearby places."""
    result = _location_fallback(user_text, latitude, longitude)
    return AIMessage(content=result)
