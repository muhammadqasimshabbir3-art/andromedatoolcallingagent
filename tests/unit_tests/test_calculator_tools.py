"""Unit tests for the Casio-style calculator tool."""

from agent.custom_tools.calculator_tools import evaluate_casio_expression


def test_basic_arithmetic():
    result = evaluate_casio_expression("2 + 3 * 4")
    assert "Result: 14" in result


def test_log_base_10():
    result = evaluate_casio_expression("log(1000)")
    assert "Result: 3" in result


def test_natural_log():
    result = evaluate_casio_expression("ln(E)")
    assert "Result: 1" in result


def test_sin_degrees():
    result = evaluate_casio_expression("sin(30)", angle_mode="DEG")
    assert "Result: 0.5" in result


def test_complex_iota():
    result = evaluate_casio_expression("sqrt(-1)")
    assert "Result: i" in result


def test_complex_rectangular():
    result = evaluate_casio_expression("2+3i")
    assert "2 + 3i" in result


def test_factorial():
    result = evaluate_casio_expression("factorial(5)")
    assert "Result: 120" in result


def test_invalid_expression():
    result = evaluate_casio_expression("log(0)")
    assert "Calculator error" in result
