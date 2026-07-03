"""Unit tests for Gmail inbox tool wrapper."""

from unittest.mock import patch

from agent.custom_tools.gmail_inbox_tools import (
    extract_gmail_inbox_limit,
    process_gmail_inbox_sync,
)


def test_extract_gmail_inbox_limit():
    assert extract_gmail_inbox_limit("process 5 unread emails") == 5
    assert extract_gmail_inbox_limit("reply to 3 unread messages") == 3
    assert extract_gmail_inbox_limit("process my unread inbox") is None


@patch("agent.custom_tools.gmail_inbox_tools.process_unread_and_reply")
@patch("agent.custom_tools.gmail_inbox_tools.Path.exists", return_value=True)
def test_process_gmail_inbox_sync_success(mock_exists, mock_process):
    mock_process.return_value = {"processed": 2, "succeeded": 2, "failed": 0}

    result = process_gmail_inbox_sync(limit=2)

    assert "Gmail inbox auto-reply complete" in result
    assert "Processed: 2" in result
    mock_process.assert_called_once()


@patch("agent.custom_tools.gmail_inbox_tools.Path.exists", return_value=False)
def test_process_gmail_inbox_sync_missing_credentials(mock_exists):
    result = process_gmail_inbox_sync()
    assert "OAuth credentials not found" in result
