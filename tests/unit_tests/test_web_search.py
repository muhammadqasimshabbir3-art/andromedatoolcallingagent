"""Tests for web search intent detection."""

from agent.task_planner import needs_web_search, should_use_web_search


def test_needs_web_search_for_explicit_request():
    assert needs_web_search("Search the web for Python best practices")


def test_needs_web_search_for_factual_question():
    assert needs_web_search("Who won the latest UEFA Euro?")


def test_does_not_need_web_search_for_math():
    assert not needs_web_search("What is log(1000) + sin(30)?")


def test_should_use_web_search_requires_toggle():
    query = "Search online for AI news"
    assert not should_use_web_search(query, web_search_enabled=False)
    assert should_use_web_search(query, web_search_enabled=True)
