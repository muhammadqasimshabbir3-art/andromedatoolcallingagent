"""Unit tests for the Gmail OAuth agent."""

import base64
from email import message_from_bytes
from unittest.mock import MagicMock, patch

import pytest

from gmail_agent import (
    FALLBACK_REPLY_TEXT,
    GmailAgentConfig,
    build_reply_message,
    extract_body_from_payload,
    generate_reply_with_ollama,
    get_message,
    list_unread_messages,
    mark_as_read,
    needs_reply,
    process_single_message,
    process_unread_and_reply,
    send_reply,
)


@pytest.fixture
def config() -> GmailAgentConfig:
    return GmailAgentConfig(
        client_secrets="client_secret.json",
        token_file="gmail_token.json",
        scopes=("https://www.googleapis.com/auth/gmail.modify",),
        user_id="me",
        inbox_query="is:unread in:inbox",
        process_limit=0,
        groq_api_key="",
        groq_model="",
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2",
        ollama_timeout=30,
        ollama_max_tokens=256,
        log_level="WARNING",
    )


def test_extract_body_from_plain_text_part():
    body = "Hello from Gmail"
    encoded = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    payload = {
        "mimeType": "text/plain",
        "body": {"data": encoded, "size": len(body)},
    }

    assert extract_body_from_payload(payload) == body


def test_extract_body_from_html_part():
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    encoded = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": encoded},
            }
        ],
    }

    assert "Hello" in extract_body_from_payload(payload)
    assert "world" in extract_body_from_payload(payload)


def test_build_reply_message_sets_thread_headers():
    reply = build_reply_message(
        to_addr="sender@example.com",
        subject="Project update",
        thread_id="thread-123",
        in_reply_to="<msg-id@mail.gmail.com>",
        body_text="Thanks for the update.",
    )

    raw_bytes = base64.urlsafe_b64decode(reply["raw"].encode("utf-8"))
    mime = message_from_bytes(raw_bytes)

    assert mime["To"] == "sender@example.com"
    assert mime["Subject"] == "Re: Project update"
    assert mime["In-Reply-To"] == "<msg-id@mail.gmail.com>"
    assert mime["References"] == "<msg-id@mail.gmail.com>"
    assert reply["threadId"] == "thread-123"


def test_build_reply_message_preserves_existing_re_prefix():
    reply = build_reply_message(
        to_addr="sender@example.com",
        subject="Re: Already replied",
        thread_id="thread-456",
        in_reply_to="",
        body_text="Acknowledged.",
    )

    raw_bytes = base64.urlsafe_b64decode(reply["raw"].encode("utf-8"))
    mime = message_from_bytes(raw_bytes)
    assert mime["Subject"] == "Re: Already replied"


@patch("gmail_agent.requests.post")
def test_generate_reply_with_ollama_success(mock_post, config):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"response": "Thank you for your email."},
    )
    mock_post.return_value.raise_for_status = MagicMock()

    original = {
        "id": "1",
        "thread_id": "t1",
        "sender": "Alice <alice@example.com>",
        "subject": "Question",
        "message_id": "<abc@example.com>",
        "body": "Can you help?",
    }

    reply = generate_reply_with_ollama(original, config)
    assert reply == "Thank you for your email."
    mock_post.assert_called_once()


@patch("gmail_agent.requests.post", side_effect=OSError("connection refused"))
def test_generate_reply_with_ollama_fallback(mock_post, config):
    original = {
        "id": "1",
        "thread_id": "t1",
        "sender": "Alice <alice@example.com>",
        "subject": "Question",
        "message_id": "<abc@example.com>",
        "body": "Can you help?",
    }

    reply = generate_reply_with_ollama(original, config)
    assert reply == FALLBACK_REPLY_TEXT


def test_list_unread_messages_paginates(config):
    service = MagicMock()
    first_page = MagicMock()
    first_page.execute.return_value = {
        "messages": [{"id": "1", "threadId": "t1"}],
        "nextPageToken": "page-2",
    }
    second_page = MagicMock()
    second_page.execute.return_value = {
        "messages": [{"id": "2", "threadId": "t2"}],
    }
    service.users.return_value.messages.return_value.list.side_effect = [
        first_page,
        second_page,
    ]

    messages = list_unread_messages(service, config)
    assert len(messages) == 2
    assert messages[0]["id"] == "1"
    assert messages[1]["id"] == "2"


def test_get_message_parses_headers_and_body(config):
    body = "Please review the attached document."
    encoded = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    service = MagicMock()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "msg-1",
        "threadId": "thread-1",
        "payload": {
            "headers": [
                {"name": "From", "value": "Bob <bob@example.com>"},
                {"name": "Subject", "value": "Review request"},
                {"name": "Message-ID", "value": "<bob-msg@example.com>"},
            ],
            "body": {"data": encoded},
        },
    }

    parsed = get_message(service, config, "msg-1")
    assert parsed["id"] == "msg-1"
    assert parsed["thread_id"] == "thread-1"
    assert parsed["sender"] == "Bob <bob@example.com>"
    assert parsed["subject"] == "Review request"
    assert parsed["message_id"] == "<bob-msg@example.com>"
    assert parsed["body"] == body


def test_send_reply_uses_thread_id(config):
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "sent-1",
        "threadId": "thread-1",
    }

    original = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "sender": "Bob <bob@example.com>",
        "subject": "Hello",
        "message_id": "<bob-msg@example.com>",
        "body": "Hi there",
    }

    result = send_reply(service, config, original, "Hello Bob")
    assert result is not None
    send_body = service.users.return_value.messages.return_value.send.call_args.kwargs["body"]
    assert send_body["threadId"] == "thread-1"


def test_mark_as_read_removes_unread_label(config):
    service = MagicMock()
    assert mark_as_read(service, config, "msg-1") is True
    modify_kwargs = (
        service.users.return_value.messages.return_value.modify.call_args.kwargs
    )
    assert modify_kwargs["id"] == "msg-1"
    assert modify_kwargs["body"] == {"removeLabelIds": ["UNREAD"]}


def test_build_reply_message_uses_fallback_for_empty_body():
    reply = build_reply_message(
        to_addr="sender@example.com",
        subject="Hello",
        thread_id="thread-123",
        in_reply_to="<msg-id@mail.gmail.com>",
        body_text="",
    )

    raw_bytes = base64.urlsafe_b64decode(reply["raw"].encode("utf-8"))
    mime = message_from_bytes(raw_bytes)
    assert FALLBACK_REPLY_TEXT in mime.get_payload(decode=True).decode("utf-8")


def test_needs_reply_classifies_human_question():
    email = {
        "sender": "Alice <alice@example.com>",
        "subject": "Can you review this proposal?",
        "body": "Hi, could you please review the attached draft and let me know your thoughts?",
        "headers": {},
    }
    needs, reason = needs_reply(email)
    assert needs is True
    assert "reply request" in reason.lower()


def test_needs_reply_skips_system_email():
    email = {
        "sender": "Mail Delivery Subsystem <mailer-daemon@example.com>",
        "subject": "Delivery Status Notification (Failure)",
        "body": "Your message could not be delivered.",
        "headers": {"precedence": "bulk"},
    }
    needs, reason = needs_reply(email)
    assert needs is False
    assert "auto-generated" in reason.lower()


def test_needs_reply_skips_promotional_email():
    email = {
        "sender": "Promo <newsletter@shop.example.com>",
        "subject": "Special offer just for you",
        "body": "Save 50% on your next purchase with this coupon.",
        "headers": {"list-unsubscribe": "<mailto:unsubscribe@shop.example.com>"},
    }
    needs, reason = needs_reply(email)
    assert needs is False
    assert "promotional" in reason.lower()


def test_process_single_message_marks_skipped_email_as_read(config):
    service = MagicMock()
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "msg-1",
        "threadId": "thread-1",
        "payload": {
            "headers": [
                {"name": "From", "value": "Promo <newsletter@shop.example.com>"},
                {"name": "Subject", "value": "Special offer just for you"},
                {"name": "Message-ID", "value": "<msg-id@example.com>"},
            ],
            "body": {"data": base64.urlsafe_b64encode(b"Save 50% on your next purchase.").decode().rstrip("=")},
        },
    }

    result = process_single_message(service, config, "msg-1")
    assert result is None
    assert service.users.return_value.messages.return_value.modify.call_count == 1


@patch("gmail_agent.process_single_message", return_value=True)
@patch("gmail_agent.list_unread_messages")
@patch("gmail_agent.get_gmail_service")
def test_process_unread_and_reply_summary(
    mock_get_service,
    mock_list_messages,
    mock_process_single,
    config,
):
    mock_list_messages.return_value = [{"id": "1"}, {"id": "2"}]

    summary = process_unread_and_reply(limit=2, config=config)

    assert summary == {"processed": 2, "succeeded": 2, "failed": 0}
    assert mock_process_single.call_count == 2
