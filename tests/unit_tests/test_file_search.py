"""Tests for file search intent detection."""

from agent.task_planner import extract_file_search_query, needs_file_search, plan_tasks


def test_needs_file_search_for_find_files():
    assert needs_file_search("Find all CSV files in current directory")


def test_needs_file_search_for_list_files():
    assert needs_file_search("List files matching report")


def test_does_not_need_file_search_for_math():
    assert not needs_file_search("What is sqrt(144)?")


def test_extract_file_search_query_extension():
    assert extract_file_search_query("Find all .pdf files") == ".pdf"


def test_plan_marks_file_search():
    plan = plan_tasks("Find all report files")
    assert plan.use_file_search
    assert "File search" in plan.summary()
