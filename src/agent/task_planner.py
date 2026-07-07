"""Decision agent: plan which tasks to run from a user query."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent.custom_tools.calculator_tools import extract_math_expressions
from agent.report_planning import extract_report_topic, infer_report_aspects
from agent.routing import is_math_query, wants_gmail_inbox_reply, wants_location

INTRO_KEYWORDS = (
    "introduce yourself",
    "introduction",
    "who are you",
    "first task",
    "tell me about yourself",
)

PDF_KEYWORDS = (
    "pdf",
    "pdf file",
    "report file",
    "save these",
    "save the",
    "create a report",
    "create a pdf",
    "create pdf",
    "generate a report",
    "generate a pdf",
    "stylized",
    "stylized pdf",
)

EXPLICIT_WEB_IN_REPORT = (
    "search internet",
    "search the internet",
    "search the web",
    "search online",
    "you can search",
    "look up online",
    "find on the internet",
    "search for information",
    "search for design",
    "search for colours",
    "search for colors",
    "search for formatting",
)

WEB_SEARCH_KEYWORDS = (
    "search the web",
    "search online",
    "search google",
    "google search",
    "look up online",
    "find on the internet",
    "latest news",
    "current news",
    "what is happening",
    "who won",
    "recent developments",
)


FILE_SEARCH_KEYWORDS = (
    "find file",
    "find files",
    "find all",
    "search file",
    "search files",
    "search for file",
    "search for files",
    "list files",
    "locate file",
    "files in",
    "files matching",
    "file named",
    "files named",
    "show me files",
    "csv files",
    "pdf files",
    ".csv",
    ".pdf",
    ".txt",
    ".py",
)


@dataclass
class TaskPlan:
    """Ordered list of tasks the agent should perform."""

    tasks: list[str] = field(default_factory=list)
    math_expressions: list[str] = field(default_factory=list)
    user_text: str = ""
    report_topic: str = ""
    report_aspects: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = field(
        default_factory=list
    )
    web_search_enabled: bool = False
    use_web_search: bool = False
    use_file_search: bool = False
    search_query: str = ""
    file_search_query: str = ""

    @property
    def is_multi_task(self) -> bool:
        workflow_tasks = [t for t in self.tasks if t != "web_search"]
        return len(workflow_tasks) >= 2

    def summary(self) -> str:
        labels = {
            "introduce": "Introduce myself",
            "calculate_math": f"Calculate {len(self.math_expressions)} expression(s)",
            "research_web": f"Research {self.report_topic or 'topic'} online (+ PDF design)",
            "create_pdf": "Create stylized PDF report",
            "send_email": "Email results with PDF attachment",
            "web_search": f"Web search: {self.search_query or 'query'}",
            "file_search": f"File search: {self.file_search_query or 'pattern'}",
        }
        steps = [labels.get(task, task) for task in self.tasks]
        if self.use_web_search and "web_search" not in self.tasks:
            steps.append(labels["web_search"])
        if self.use_file_search and "file_search" not in self.tasks:
            steps.append(labels["file_search"])
        return " → ".join(steps) if steps else "General conversation"


def wants_introduction(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in INTRO_KEYWORDS)


def is_research_report_workflow(user_text: str, math_expressions: list[str]) -> bool:
    """PDF report workflow driven by research, not calculator results."""
    return wants_pdf(user_text) and not math_expressions


def wants_web_research_for_report(user_text: str, web_search_enabled: bool) -> bool:
    """Research online when the user wants an informational PDF (any topic)."""
    math_expressions = extract_math_expressions(user_text)
    if not is_research_report_workflow(user_text, math_expressions):
        return False

    lowered = user_text.lower()
    if any(phrase in lowered for phrase in EXPLICIT_WEB_IN_REPORT):
        return True
    if web_search_enabled:
        return True

    # Informational report with a identifiable topic — planner adds research step
    return extract_report_topic(user_text) != "General Report"


def wants_pdf(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in PDF_KEYWORDS)


def needs_web_search(user_text: str) -> bool:
    """Return True when the query likely needs live internet information."""
    if not user_text.strip():
        return False

    lowered = user_text.lower()

    if any(keyword in lowered for keyword in WEB_SEARCH_KEYWORDS):
        return True

    if is_math_query(user_text) and extract_math_expressions(user_text):
        return False

    if any(
        phrase in lowered
        for phrase in (
            "who is ",
            "who was ",
            "when did ",
            "where is ",
            "latest ",
            "current ",
            "today's ",
            "news about",
            "price of",
            "weather in",
        )
    ):
        return True

    if "?" in user_text and not is_math_query(user_text):
        if re.search(r"\b(what|who|when|where|why|how)\b", lowered):
            return True

    return False


def needs_location(user_text: str) -> bool:
    """Return True when the user query is location-related."""
    return wants_location(user_text)


def needs_file_search(user_text: str) -> bool:
    """Return True when the user wants to find local files."""
    if not user_text.strip():
        return False

    lowered = user_text.lower()
    if any(keyword in lowered for keyword in FILE_SEARCH_KEYWORDS):
        return True

    if re.search(r"\bfind\b.*\b(file|files)\b", lowered):
        return True

    return False


def extract_file_search_query(user_text: str) -> str:
    """Pull a filename or pattern from a file-search request."""
    text = user_text.strip()

    ext_match = re.search(r"(\.\w{2,5})", text)
    if ext_match:
        return ext_match.group(1)

    for pattern in (
        r"(?i)find all\s+(.+?)\s+files",
        r"(?i)find\s+(.+?)\s+files",
        r"(?i)search for\s+(.+?)\s+files",
        r"(?i)files matching\s+(.+)",
        r"(?i)files named\s+(.+)",
        r"(?i)find files?\s+(?:named|called|matching)\s+(.+)",
        r"(?i)find\s+(.+?)\s+in\b",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .\"'")

    bare_ext = re.search(r"(?i)\b(pdf|csv|txt|py|json|xml|md)\b", text)
    if bare_ext:
        return f".{bare_ext.group(1).lower()}"

    return "report"


def should_use_web_search(user_text: str, web_search_enabled: bool) -> bool:
    """User enabled search AND query needs internet lookup."""
    return web_search_enabled and needs_web_search(user_text)


def plan_tasks(user_text: str, web_search_enabled: bool = False) -> TaskPlan:
    """Analyze the user query and decide which tasks to perform, in order."""
    plan = TaskPlan(user_text=user_text, web_search_enabled=web_search_enabled)
    math_expressions = extract_math_expressions(user_text)

    if wants_introduction(user_text):
        plan.tasks.append("introduce")

    if math_expressions:
        plan.tasks.append("calculate_math")
        plan.math_expressions = math_expressions

    plan.report_topic = extract_report_topic(user_text)
    plan.report_aspects = infer_report_aspects(user_text)

    if wants_web_research_for_report(user_text, web_search_enabled):
        plan.tasks.append("research_web")
        plan.use_web_search = True

    if wants_pdf(user_text):
        plan.tasks.append("create_pdf")

    if wants_gmail_inbox_reply(user_text):
        return plan

    # SMTP email workflow disabled: Gmail API inbox operations are handled
    # through dedicated routing/tools rather than report-email tasks.

    if should_use_web_search(user_text, web_search_enabled):
        from agent.custom_tools.web_search_tools import extract_search_query

        plan.use_web_search = True
        plan.search_query = extract_search_query(user_text)

    if needs_file_search(user_text):
        plan.use_file_search = True
        plan.file_search_query = extract_file_search_query(user_text)

    return plan


def is_multi_task_request(user_text: str, web_search_enabled: bool = False) -> bool:
    """True when the query needs the multi-step workflow executor."""
    return plan_tasks(user_text, web_search_enabled).is_multi_task
