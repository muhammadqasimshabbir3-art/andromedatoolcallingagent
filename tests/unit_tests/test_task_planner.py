"""Tests for decision agent and math expression extraction."""

from agent.custom_tools.calculator_tools import extract_math_expressions
from agent.task_planner import is_multi_task_request, plan_tasks

USER_EXAM_QUERY = """\
your first task is to introduce yourself,then  I am practicing for my math and engineering exams. Please calculate the following expressions and give final answers:
log(1000) + ln(E^5), sin(73.5) * cos(41.2) + tan(12.7), (3 + 4i)^7, factorial(17) / (sqrt(12345) * log(987654)), sin(73.2456)^2 + cos(73.2456)^2, (1 + i)^25, log(1000) + ln(E^5) + sin(90), ((123456789^2 + 987654321^2) / sqrt(7777777)) * ln(12345), sqrt(-1) * (3 - 4i)^5, asin(0.37) + acos(0.22) - atan(1.75), and ((987654321^2 + 123456789^2) * factorial(15)) / (sqrt(98765) * log(1234567)).
create a pdf file to save tehse question and answer  a very good stylized the pdf file then i want  it send to me emails
"""


def test_extracts_eleven_math_expressions():
    expressions = extract_math_expressions(USER_EXAM_QUERY)
    assert len(expressions) == 11
    assert expressions[0] == "log(1000) + ln(E^5)"
    assert "factorial(15)" in expressions[-1]


def test_does_not_treat_intro_as_math():
    expressions = extract_math_expressions(USER_EXAM_QUERY)
    assert not any("introduce" in expr.lower() for expr in expressions)
    assert not any("pdf" in expr.lower() for expr in expressions)


def test_multi_task_plan_order():
    plan = plan_tasks(USER_EXAM_QUERY)
    assert plan.is_multi_task
    assert plan.tasks == [
        "introduce",
        "calculate_math",
        "create_pdf",
        "send_email",
    ]
    assert len(plan.math_expressions) == 11
    assert is_multi_task_request(USER_EXAM_QUERY)


def test_web_search_only_when_enabled():
    query = "Search the web for latest Python news"
    plan_off = plan_tasks(query, web_search_enabled=False)
    assert not plan_off.use_web_search

    plan_on = plan_tasks(query, web_search_enabled=True)
    assert plan_on.use_web_search
    assert "Web search" in plan_on.summary()
