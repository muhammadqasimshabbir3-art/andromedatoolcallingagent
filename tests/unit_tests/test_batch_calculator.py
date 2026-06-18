"""Unit tests for batch math solving."""

from agent.custom_tools.calculator_tools import solve_math_batch


SAMPLE_PROBLEMS = """\
What is:
log(2500) + ln(7)
Evaluate:
sin(73.5) * cos(41.2) + tan(12.7)
Evaluate:
(3 + 4i)^7
Evaluate:
factorial(17) / (sqrt(12345) * log(987654))
Evaluate exactly:
sin(73.2456)^2 + cos(73.2456)^2
What is:
log(1000) + ln(E^5)
Evaluate:
((123456789^2 + 987654321^2) / sqrt(7777777)) * ln(12345)
What is:
sin(90)
Without approximation, evaluate:
log(1000) + ln(E^5) + sin(90)
"""


def test_batch_parses_multiple_lines():
    result = solve_math_batch(SAMPLE_PROBLEMS)
    assert "Solved 9 problem(s)" in result
    assert "log(2500) + ln(7)" in result
    assert "sin(90)" in result


def test_batch_sin_90_is_one():
    result = solve_math_batch("sin(90)")
    assert "= 1" in result


def test_batch_trig_identity():
    result = solve_math_batch("sin(73.2456)^2 + cos(73.2456)^2")
    assert "= 1" in result
