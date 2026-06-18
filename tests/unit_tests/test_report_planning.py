"""Tests for generic report topic and section inference."""

from agent.report_planning import (
    build_content_search_query,
    build_design_search_query,
    extract_report_topic,
    infer_report_aspects,
    report_pdf_filename,
)


def test_extract_topic_from_disease_phrase():
    assert extract_report_topic("pdf for malaria disease causes and prevention") == "Malaria"


def test_extract_topic_from_about_phrase():
    topic = extract_report_topic("create a report about renewable energy applications")
    assert "renewable" in topic.lower()


def test_infer_aspects_from_user_language():
    aspects = infer_report_aspects("report on diabetes causes treatment and prevention")
    titles = [title for title, _, _ in aspects]
    assert "Causes" in titles
    assert "Prevention" in titles


def test_build_search_queries_from_plan():
    aspects = infer_report_aspects("malaria causes prevention cure")
    query = build_content_search_query("Malaria", aspects)
    assert "Malaria" in query
    design = build_design_search_query("stylized pdf with colors and formatting")
    assert "color" in design.lower() or "format" in design.lower()


def test_report_pdf_filename_is_topic_based():
    assert report_pdf_filename("Climate Change") == "./reports/climate_change_report.pdf"
