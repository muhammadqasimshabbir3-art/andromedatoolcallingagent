"""Unit tests for graph routing helpers."""

from agent.routing import (
    extract_math_expression,
    is_batch_math_query,
    is_math_query,
    pick_tool_choice,
    wants_email,
    wants_gmail_inbox_reply,
)


def test_simple_math_detection():
    assert is_math_query("what is 2+2")
    assert not is_math_query("what is your name")


def test_batch_math_detection():
    text = "log(10)\nsin(30)"
    assert is_batch_math_query(text)
    assert pick_tool_choice(text) == {
        "type": "function",
        "function": {"name": "solve_math_batch_tool"},
    }


def test_single_math_tool_choice():
    assert pick_tool_choice("what is 2+2") == {
        "type": "function",
        "function": {"name": "casio_calculator"},
    }


def test_email_intent():
    assert wants_email("send these answers to my email")
    assert pick_tool_choice("email me the results") is None


def test_gmail_inbox_intent():
    assert wants_gmail_inbox_reply("process my unread emails in gmail inbox")
    assert wants_gmail_inbox_reply("auto reply to unread messages")
    assert not wants_gmail_inbox_reply("email me the pdf report")
    # Inbox intent must not be treated as SMTP outbound email.
    assert not wants_email("reply to my unread emails")


def test_extract_expression():
    assert extract_math_expression("what is 2+2") == "2+2"
