"""Tests for generic research → PDF → email workflow planning."""

from unittest.mock import patch

from agent.report_planning import extract_report_topic, infer_report_aspects
from agent.task_planner import plan_tasks
from agent.workflow_executor import execute_task_plan

MALARIA_QUERY = """\
introduce yourself and then create a pdf file stylized pdf file with good pattern \
you can search internet so that you have which different colors and formatting of \
generation of pdf file for malaria disease it causes prevention cure and preventions \
then send this to me via email
"""

CLIMATE_QUERY = """\
Introduce yourself, search the web for information on climate change impacts and \
best practices, create a stylized PDF report, and email it to me.
"""


def test_planner_detects_research_pdf_email_workflow():
    plan = plan_tasks(MALARIA_QUERY, web_search_enabled=False)
    assert plan.is_multi_task
    assert "introduce" in plan.tasks
    assert "research_web" in plan.tasks
    assert "create_pdf" in plan.tasks
    assert "send_email" in plan.tasks


def test_planner_infers_topic_and_sections_from_query():
    plan = plan_tasks(MALARIA_QUERY)
    assert plan.report_topic == "Malaria"
    section_titles = [title for title, _, _ in plan.report_aspects]
    assert "Causes" in section_titles
    assert "Prevention" in section_titles


def test_planner_works_for_any_topic_not_hardcoded():
    plan = plan_tasks(CLIMATE_QUERY, web_search_enabled=True)
    assert plan.is_multi_task
    assert "research_web" in plan.tasks
    topic = extract_report_topic(CLIMATE_QUERY)
    assert "climate" in topic.lower() or topic != "General Report"


def test_infer_report_aspects_defaults_when_unspecified():
    aspects = infer_report_aspects("create a pdf about renewable energy")
    titles = [title for title, _, _ in aspects]
    assert "Overview" in titles


@patch("agent.workflow_executor.send_smtp_email")
@patch("agent.workflow_executor.web_search_sync")
def test_workflow_uses_topic_pdf_path_not_math_default(mock_search, mock_email):
    mock_search.side_effect = [
        "**Web Search:** topic\n\n   Research snippet about the subject.",
        "**Web Search:** design\n\n   Use clear section headers and accent colors.",
    ]
    mock_email.return_value = "Email sent successfully.\nAttachments: malaria_report.pdf"

    plan = plan_tasks(MALARIA_QUERY)
    response = execute_task_plan(plan)

    assert "malaria_report.pdf" in response.content
    mock_email.assert_called_once()
    attachment = mock_email.call_args.kwargs["attachment_paths"]
    assert attachment is not None
    assert "math_exam" not in attachment.lower()
    assert "malaria" in attachment.lower()
