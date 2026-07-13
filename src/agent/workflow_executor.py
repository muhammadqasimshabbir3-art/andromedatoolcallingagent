"""Execute multi-task workflows planned by the decision agent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage

from agent.custom_tools.calculator_tools import _result_value
from agent.custom_tools.email_tools import send_smtp_email
from agent.custom_tools.pdf_generator import (
    _generate_pdf_report_sync,
    _generate_stylized_topic_pdf_sync,
)
from agent.custom_tools.web_search_tools import web_search_sync
from agent.report_planning import (
    build_content_search_query,
    build_design_search_query,
    report_pdf_filename,
)
from agent.task_planner import TaskPlan

INTRO_TEXT = (
    "Hello! I am **Andromeda**, your multi-tool AI assistant. "
    "I can calculate math, research any topic on the web, build stylized PDF reports, "
    "and email them to you. Happy to help!"
)

DEFAULT_MATH_PDF_PATH = "./reports/math_exam_practice.pdf"
REPORTS_DIR = Path("./reports")


@dataclass
class WorkflowContext:
    """Runtime state while executing a multi-task plan."""

    plan: TaskPlan
    qa_pairs: list[tuple[str, str]] = field(default_factory=list)
    research_content: str = ""
    design_notes: str = ""
    pdf_path: str = ""
    pdf_absolute_path: Path | None = None


@dataclass
class WorkflowResult:
    """Outcome of a multi-task workflow run."""

    message: AIMessage
    pdf_path: str | None = None
    pdf_filename: str | None = None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "report"


def _parse_search_snippets(search_text: str) -> list[str]:
    snippets: list[str] = []
    for line in search_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("**Web Search"):
            continue
        if stripped[0].isdigit() and "." in stripped[:4]:
            continue
        if stripped.startswith("http"):
            continue
        if stripped.startswith("**") and stripped.endswith("**"):
            continue
        cleaned = stripped.lstrip("•-* ").strip()
        if len(cleaned) > 30:
            snippets.append(cleaned)
    return snippets


def _section_from_snippets(
    snippets: list[str],
    search_keywords: tuple[str, ...],
    topic: str,
    section_title: str,
) -> str:
    matched = [
        snippet
        for snippet in snippets
        if any(keyword in snippet.lower() for keyword in search_keywords)
    ]
    if matched:
        return "\n\n".join(matched[:4])

    remaining = [s for s in snippets if s not in matched]
    if remaining:
        return "\n\n".join(remaining[:2])

    return (
        f"This section covers {section_title.lower()} for {topic}. "
        "Content is based on the user request and available research."
    )


def _build_report_sections(
    topic: str,
    research_text: str,
    aspects: list[tuple[str, tuple[str, ...], tuple[str, ...]]],
) -> dict[str, str]:
    """Map web research into PDF sections inferred from the user query."""
    snippets = _parse_search_snippets(research_text)
    sections: dict[str, str] = {}

    for title, _, search_keys in aspects:
        sections[title] = _section_from_snippets(snippets, search_keys, topic, title)

    return sections


def _pdf_subtitle(aspects: list[tuple[str, tuple[str, ...], tuple[str, ...]]]) -> str:
    titles = [title for title, _, _ in aspects if title not in ("Overview", "Summary")]
    if titles:
        return " · ".join(titles[:4])
    return "Research Report"


def _format_math_section(qa_pairs: list[tuple[str, str]]) -> str:
    lines = [
        f"**Calculated {len(qa_pairs)} expression(s)** (angle mode: DEG):",
        "",
    ]
    for index, (expression, answer) in enumerate(qa_pairs, start=1):
        lines.append(f"{index}. `{expression}`")
        lines.append(f"   **Answer:** {answer}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_math_pdf_content(qa_pairs: list[tuple[str, str]], intro_included: bool) -> str:
    lines = [
        "Math & Engineering Exam Practice Report",
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    if intro_included:
        lines.extend(["Assistant Introduction", INTRO_TEXT.replace("**", ""), ""])

    lines.append("Questions and Answers")
    lines.append("=" * 40)
    lines.append("")

    for index, (expression, answer) in enumerate(qa_pairs, start=1):
        lines.append(f"Question {index}: {expression}")
        lines.append(f"Answer {index}: {answer}")
        lines.append("")

    return "\n".join(lines)


def _resolve_pdf_attachment(expected_path: str, topic: str = "") -> Path | None:
    """Find the PDF created in this workflow — avoid attaching unrelated files."""
    candidate = Path(expected_path)
    if candidate.exists() and candidate.is_file():
        return candidate.resolve()

    if not REPORTS_DIR.exists():
        return None

    slug = _slugify(topic) if topic else ""
    if slug:
        topic_matches = sorted(
            REPORTS_DIR.glob(f"{slug}*.pdf"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if topic_matches:
            return topic_matches[0].resolve()

    if candidate.name:
        name_matches = list(REPORTS_DIR.glob(f"*{candidate.name}"))
        if name_matches:
            return max(name_matches, key=lambda path: path.stat().st_mtime).resolve()

    return None


def _is_research_report(plan: TaskPlan) -> bool:
    return "research_web" in plan.tasks or (
        "create_pdf" in plan.tasks and not plan.math_expressions
    )


def execute_task_plan(plan: TaskPlan) -> WorkflowResult:
    """Run each planned task in order and return a combined response + PDF metadata."""
    ctx = WorkflowContext(plan=plan)
    sections: list[str] = [f"**Decision agent task plan:** {plan.summary()}", ""]

    for task in plan.tasks:
        if task == "introduce":
            sections.append("### Introduction")
            sections.append(INTRO_TEXT)

        elif task == "calculate_math":
            sections.append("### Calculator Results")
            for expression in plan.math_expressions:
                answer = _result_value(expression, "DEG")
                ctx.qa_pairs.append((expression, answer))
            sections.append(_format_math_section(ctx.qa_pairs))

        elif task == "research_web":
            topic = plan.report_topic or "General Report"
            aspects = plan.report_aspects
            sections.append("### Web Research")
            sections.append(f"Researching **{topic}** and PDF layout ideas...")

            content_query = build_content_search_query(topic, aspects)
            design_query = build_design_search_query(plan.user_text)

            ctx.research_content = web_search_sync(content_query, max_results=6)
            ctx.design_notes = web_search_sync(design_query, max_results=4)

            sections.append(f"**Topic query:** `{content_query}`")
            sections.append(ctx.research_content[:1200] + ("..." if len(ctx.research_content) > 1200 else ""))
            sections.append("")
            sections.append(f"**Design query:** `{design_query}`")
            sections.append(ctx.design_notes[:800] + ("..." if len(ctx.design_notes) > 800 else ""))

        elif task == "create_pdf":
            sections.append("### PDF Report")

            if _is_research_report(plan):
                topic = plan.report_topic or "Report"
                aspects = plan.report_aspects
                ctx.pdf_path = report_pdf_filename(topic)
                topic_sections = _build_report_sections(
                    topic,
                    ctx.research_content,
                    aspects,
                )
                design_snippets = _parse_search_snippets(ctx.design_notes)
                if design_snippets:
                    topic_sections["Layout & Design Notes"] = "\n\n".join(design_snippets[:3])

                intro_for_pdf = (
                    INTRO_TEXT.replace("**", "")
                    if "introduce" in plan.tasks
                    else ""
                )
                pdf_result = _generate_stylized_topic_pdf_sync(
                    topic=topic,
                    sections=topic_sections,
                    output_path=ctx.pdf_path,
                    subtitle=_pdf_subtitle(aspects),
                    intro_text=intro_for_pdf,
                )
            else:
                ctx.pdf_path = DEFAULT_MATH_PDF_PATH
                pdf_content = _format_math_pdf_content(
                    ctx.qa_pairs,
                    intro_included="introduce" in plan.tasks,
                )
                pdf_result = _generate_pdf_report_sync(
                    title="Math & Engineering Exam Practice",
                    subtitle="Questions, Answers & Calculator Results",
                    content=pdf_content,
                    output_path=ctx.pdf_path,
                )

            ctx.pdf_absolute_path = _resolve_pdf_attachment(ctx.pdf_path, plan.report_topic)
            sections.append(pdf_result)
            if ctx.pdf_absolute_path:
                sections.append(f"Verified PDF path: `{ctx.pdf_absolute_path}`")
            else:
                sections.append("⚠️ Warning: PDF file could not be verified on disk.")

        elif task == "send_email":
            sections.append("### Email")
            topic = plan.report_topic or "Report"
            attachment_path = ctx.pdf_absolute_path or _resolve_pdf_attachment(
                ctx.pdf_path,
                topic,
            )

            if _is_research_report(plan):
                section_names = ", ".join(title for title, _, _ in plan.report_aspects[:4])
                email_body_lines = [
                    "Hello,",
                    "",
                    f"Please find attached the stylized PDF report on **{topic}** from Andromeda.",
                    "",
                ]
                if "introduce" in plan.tasks:
                    email_body_lines.extend([INTRO_TEXT.replace("**", ""), ""])
                email_body_lines.extend(
                    [
                        f"Sections included: {section_names}.",
                        "Content was gathered via web research based on your request.",
                        "",
                    ]
                )
                if attachment_path:
                    email_body_lines.append(
                        f"Attached file: {attachment_path.name} ({attachment_path})"
                    )
                else:
                    email_body_lines.append(
                        "Note: PDF attachment was not found. Please check ./reports/ on the server."
                    )
                email_body_lines.extend(["", "Regards,", "Andromeda Agent"])
                subject = f"Andromeda — {topic} Report (PDF attached)"
            else:
                email_body_lines = [
                    "Hello,",
                    "",
                    "Please find your math exam practice results from Andromeda.",
                    "",
                ]
                if "introduce" in plan.tasks:
                    email_body_lines.extend([INTRO_TEXT.replace("**", ""), ""])
                for index, (expression, answer) in enumerate(ctx.qa_pairs, start=1):
                    email_body_lines.append(f"{index}. {expression}")
                    email_body_lines.append(f"   Answer: {answer}")
                    email_body_lines.append("")
                if attachment_path:
                    email_body_lines.append(f"PDF attached: {attachment_path.name}")
                email_body_lines.extend(["", "Regards,", "Andromeda Agent"])
                subject = "Andromeda — Math Exam Practice Report"

            attachment_str = str(attachment_path) if attachment_path else None
            email_result = send_smtp_email(
                subject=subject,
                body="\n".join(email_body_lines),
                attachment_paths=attachment_str,
            )
            sections.append(email_result)

    message = AIMessage(content="\n\n".join(sections).strip())
    pdf_abs = ctx.pdf_absolute_path
    return WorkflowResult(
        message=message,
        pdf_path=str(pdf_abs) if pdf_abs else None,
        pdf_filename=pdf_abs.name if pdf_abs else None,
    )
