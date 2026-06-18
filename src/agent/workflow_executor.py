"""Execute multi-task workflows planned by the decision agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage

from agent.custom_tools.calculator_tools import _result_value
from agent.custom_tools.email_tools import send_smtp_email
from agent.custom_tools.pdf_generator import _generate_pdf_report_sync
from agent.task_planner import TaskPlan

INTRO_TEXT = (
    "Hello! I am **Andromeda**, your multi-tool AI assistant. "
    "I can calculate engineering and math problems with a Casio-style calculator, "
    "generate stylized PDF reports, search the web, and email your results. "
    "Happy to help with your exam practice!"
)

DEFAULT_PDF_PATH = "./reports/math_exam_practice.pdf"


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


def _format_pdf_content(qa_pairs: list[tuple[str, str]], intro_included: bool) -> str:
    lines = [
        "Math & Engineering Exam Practice Report",
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    if intro_included:
        lines.extend(
            [
                "Assistant Introduction",
                INTRO_TEXT.replace("**", ""),
                "",
            ]
        )

    lines.append("Questions and Answers")
    lines.append("=" * 40)
    lines.append("")

    for index, (expression, answer) in enumerate(qa_pairs, start=1):
        lines.append(f"Question {index}: {expression}")
        lines.append(f"Answer {index}: {answer}")
        lines.append("")

    return "\n".join(lines)


def execute_task_plan(plan: TaskPlan) -> AIMessage:
    """Run each planned task in order and return a combined response."""
    sections: list[str] = [f"**Decision agent task plan:** {plan.summary()}", ""]
    qa_pairs: list[tuple[str, str]] = []
    pdf_path = DEFAULT_PDF_PATH

    for task in plan.tasks:
        if task == "introduce":
            sections.append("### Introduction")
            sections.append(INTRO_TEXT)

        elif task == "calculate_math":
            sections.append("### Calculator Results")
            for expression in plan.math_expressions:
                answer = _result_value(expression, "DEG")
                qa_pairs.append((expression, answer))
            sections.append(_format_math_section(qa_pairs))

        elif task == "create_pdf":
            sections.append("### PDF Report")
            pdf_content = _format_pdf_content(
                qa_pairs,
                intro_included="introduce" in plan.tasks,
            )
            pdf_result = _generate_pdf_report_sync(
                title="Math & Engineering Exam Practice",
                subtitle="Questions, Answers & Calculator Results",
                content=pdf_content,
                output_path=pdf_path,
            )
            sections.append(pdf_result)

        elif task == "send_email":
            sections.append("### Email")
            email_body_lines = [
                "Hello,",
                "",
                "Please find your math exam practice results from Andromeda.",
                "",
            ]
            if "introduce" in plan.tasks:
                email_body_lines.extend([INTRO_TEXT.replace("**", ""), ""])

            for index, (expression, answer) in enumerate(qa_pairs, start=1):
                email_body_lines.append(f"{index}. {expression}")
                email_body_lines.append(f"   Answer: {answer}")
                email_body_lines.append("")

            if "create_pdf" in plan.tasks and Path(pdf_path).exists():
                email_body_lines.append(f"A detailed PDF report is attached: {pdf_path}")
            else:
                email_body_lines.append("See the answers above in this email.")

            email_body_lines.extend(["", "Regards,", "Andromeda Agent"])
            attachment = pdf_path if Path(pdf_path).exists() else None
            email_result = send_smtp_email(
                subject="Andromeda — Math Exam Practice Report",
                body="\n".join(email_body_lines),
                attachment_paths=attachment,
            )
            sections.append(email_result)

    return AIMessage(content="\n\n".join(sections).strip())
