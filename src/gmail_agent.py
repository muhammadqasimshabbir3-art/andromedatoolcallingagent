"""Gmail agent: OAuth 2.0 auth, unread inbox processing, Groq/Ollama replies, in-thread send.

Authenticate with Gmail via OAuth 2.0, read unread inbox messages, generate
professional replies with Groq (primary) or Ollama (fallback), send them in the
same thread, and mark the original message as read.

LLM Priority:
    1. Groq API  (fast, cloud-based — requires GROQ_API_KEY)
    2. Ollama    (local fallback — requires Ollama running on OLLAMA_URL)
    If both are unavailable the email is skipped and reported as failed.

Environment variables (see .env.example):
    GOOGLE_CLIENT_SECRETS  Path to OAuth client secrets JSON from Google Cloud
    GMAIL_TOKEN_FILE       Path to cache OAuth tokens after first login
    GMAIL_SCOPES           Comma-separated Gmail API scopes
    GMAIL_USER_ID          Gmail user id (default: "me")
    GMAIL_INBOX_QUERY      Gmail search query for unread messages
    GMAIL_PROCESS_LIMIT    Max messages to process per run (0 = no limit)
    GROQ_API_KEY           Groq cloud API key (primary LLM)
    GROQ_MODEL             Groq model name (default: llama3-8b-8192)
    OLLAMA_URL             Ollama server base URL
    OLLAMA_MODEL           Ollama model name
    OLLAMA_TIMEOUT         HTTP timeout in seconds for Ollama requests
    OLLAMA_MAX_TOKENS      Max tokens for generated reply
    LOG_LEVEL              Logging level (DEBUG, INFO, WARNING, ERROR)

Usage:
    uv run python src/gmail_agent.py
    uv run python src/gmail_agent.py --limit 5
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Optional, TypedDict

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gmail_agent")

FALLBACK_REPLY_TEXT = (
    "Thank you for your message. I'm currently unavailable to craft a full response, "
    "but I will follow up shortly."
)
OLLAMA_MAX_RETRIES = 3
OLLAMA_RETRY_BACKOFF = 2


class ParsedEmail(TypedDict):
    """Structured fields extracted from a Gmail message."""

    id: str
    thread_id: str
    sender: str
    subject: str
    message_id: str
    body: str
    headers: dict[str, str]


@dataclass(frozen=True)
class GmailAgentConfig:
    """Configuration loaded from environment variables."""

    client_secrets: str
    token_file: str
    scopes: tuple[str, ...]
    user_id: str
    inbox_query: str
    process_limit: int
    groq_api_key: str
    groq_model: str
    ollama_url: str
    ollama_model: str
    ollama_timeout: int
    ollama_max_tokens: int
    log_level: str

    @classmethod
    def from_env(cls) -> GmailAgentConfig:
        """Build configuration from the current environment."""
        scopes_raw = os.getenv(
            "GMAIL_SCOPES",
            "https://www.googleapis.com/auth/gmail.modify",
        )
        scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip())

        def int_env(name: str, default: int) -> int:
            raw_value = os.getenv(name, "")
            if not raw_value or not raw_value.strip():
                return default
            try:
                return int(raw_value)
            except ValueError:
                logger.warning(
                    "Invalid integer for %s: %r; using %d",
                    name,
                    raw_value,
                    default,
                )
                return default

        return cls(
            client_secrets=os.getenv("GOOGLE_CLIENT_SECRETS", "client_secret.json"),
            token_file=os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"),
            scopes=scopes,
            user_id=os.getenv("GMAIL_USER_ID", "me"),
            inbox_query=os.getenv("GMAIL_INBOX_QUERY", "is:unread in:inbox"),
            process_limit=int_env("GMAIL_PROCESS_LIMIT", 0),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_model=os.getenv("GROQ_MODEL", "llama3-8b-8192"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            ollama_timeout=int_env("OLLAMA_TIMEOUT", 120),
            ollama_max_tokens=int_env("OLLAMA_MAX_TOKENS", 512),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def configure_logging(level: str = "INFO") -> None:
    """Configure module logger with a stream handler."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)


def _print_oauth_setup_help(secrets_path: str) -> None:
    """Print step-by-step instructions when OAuth credentials are missing."""
    logger.error("OAuth client secrets not found at: %s", secrets_path)
    help_text = f"""
Gmail OAuth setup required:

  1. Open https://console.cloud.google.com/
  2. Enable the Gmail API for your project
  3. Go to APIs & Services → Credentials
  4. Create OAuth Client ID → Application type: Desktop app
  5. Download the JSON file and save it as:
       {secrets_path}
  6. Add to your .env file:
       GOOGLE_CLIENT_SECRETS={secrets_path}
  7. Run again: uv run python src/gmail_agent.py

On first run, a browser window opens for Gmail login.
After that, tokens are saved to GMAIL_TOKEN_FILE (default: ./gmail_token.json).
"""
    print(help_text, file=sys.stderr)


def get_gmail_service(config: GmailAgentConfig) -> Any:
    """Authenticate via OAuth 2.0 and return a Gmail API service client.

    Loads cached credentials from ``config.token_file`` when valid. Refreshes
    expired tokens automatically. Falls back to the local OAuth consent flow.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds: Optional[Credentials] = None

    if os.path.exists(config.token_file):
        try:
            creds = Credentials.from_authorized_user_file(
                config.token_file, list(config.scopes)
            )
            logger.info("Loaded credentials from %s", config.token_file)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to load credentials file: %s", exc)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed expired credentials")
            except Exception as exc:
                logger.warning("Failed to refresh credentials: %s", exc)
                creds = None

        if not creds:
            if not os.path.exists(config.client_secrets):
                _print_oauth_setup_help(config.client_secrets)
                raise FileNotFoundError(
                    f"OAuth client secrets not found: {config.client_secrets}"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                config.client_secrets,
                list(config.scopes),
            )
            creds = flow.run_local_server(port=0)
            logger.info("Completed OAuth 2.0 consent flow")

        try:
            with open(config.token_file, "w", encoding="utf-8") as token_handle:
                token_handle.write(creds.to_json())
            logger.info("Saved credentials to %s", config.token_file)
        except OSError as exc:
            logger.warning("Failed to save token file: %s", exc)

    try:
        return build("gmail", "v1", credentials=creds)
    except Exception as exc:
        logger.exception("Failed to build Gmail service: %s", exc)
        raise


def list_unread_messages(service: Any, config: GmailAgentConfig) -> list[dict[str, str]]:
    """Return metadata for all unread messages matching the inbox query.

    Handles Gmail API pagination so every unread inbox message is included.
    """
    from googleapiclient.errors import HttpError

    messages: list[dict[str, str]] = []
    page_token: Optional[str] = None

    try:
        while True:
            request = service.users().messages().list(
                userId=config.user_id,
                q=config.inbox_query,
                pageToken=page_token,
            )
            response = request.execute()
            messages.extend(response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info("Found %d unread inbox message(s)", len(messages))
        return messages
    except HttpError as exc:
        logger.exception("Gmail API error while listing messages: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error while listing messages: %s", exc)
        raise


def _decode_base64url(data: Optional[str]) -> str:
    """Decode a Gmail API base64url-encoded string."""
    if not data:
        return ""
    try:
        padding = len(data) % 4
        if padding:
            data += "=" * (4 - padding)
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
            "utf-8", errors="replace"
        )
    except (ValueError, UnicodeDecodeError) as exc:
        logger.debug("Failed to decode message part: %s", exc)
        return ""


def _html_to_text(html: str) -> str:
    """Convert HTML email content to plain text."""
    if not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_body_from_payload(payload: dict[str, Any]) -> str:
    """Extract plain-text body from a Gmail message payload.

    Prefers ``text/plain`` parts. Falls back to ``text/html`` converted to text.
    """
    body_data = payload.get("body", {}).get("data")
    if body_data:
        return _decode_base64url(body_data)

    plain_text = ""
    html_text = ""

    for part in payload.get("parts", []) or []:
        mime_type = part.get("mimeType", "")
        part_data = part.get("body", {}).get("data")

        if mime_type == "text/plain" and part_data:
            plain_text = _decode_base64url(part_data)
            if plain_text.strip():
                return plain_text.strip()
        elif mime_type == "text/html" and part_data:
            html_text = _decode_base64url(part_data)
        elif part.get("parts"):
            nested = extract_body_from_payload(part)
            if nested.strip():
                return nested.strip()

    if plain_text.strip():
        return plain_text.strip()
    if html_text.strip():
        return _html_to_text(html_text)
    return ""


def get_message(service: Any, config: GmailAgentConfig, msg_id: str) -> ParsedEmail:
    """Fetch a message and extract sender, subject, IDs, and body text."""
    from googleapiclient.errors import HttpError

    try:
        raw_message = (
            service.users()
            .messages()
            .get(userId=config.user_id, id=msg_id, format="full")
            .execute()
        )
    except HttpError as exc:
        logger.exception("Failed to fetch message %s: %s", msg_id, exc)
        raise

    headers = raw_message.get("payload", {}).get("headers", [])

    def header_value(name: str) -> str:
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value", "")
        return ""

    sender = header_value("From")
    subject = header_value("Subject")
    message_id = header_value("Message-ID") or header_value("Message-Id")
    body = extract_body_from_payload(raw_message.get("payload", {}))
    headers_map = {header.get("name", "").lower(): header.get("value", "") for header in headers}

    return ParsedEmail(
        id=raw_message.get("id", msg_id),
        thread_id=raw_message.get("threadId", ""),
        sender=sender,
        subject=subject,
        message_id=message_id,
        body=body,
        headers=headers_map,
    )


def generate_reply_with_groq(original: ParsedEmail, config: GmailAgentConfig) -> Optional[str]:
    """Generate a professional reply using the Groq cloud API (primary LLM).

    Returns the reply text string on success, or ``None`` if Groq is unavailable
    or not configured (no API key).
    """
    if not config.groq_api_key:
        logger.debug("GROQ_API_KEY not set — skipping Groq")
        return None

    prompt = (
        "You are an assistant that writes professional, concise, and context-aware "
        "email replies. Address the sender's message directly, keep a courteous tone, "
        "include clear next steps when appropriate, and limit the reply to 2-4 short "
        "paragraphs. Do not include a subject line or email headers — only the reply "
        "body text.\n\n"
        f"From: {original['sender']}\n"
        f"Subject: {original['subject']}\n\n"
        "Original message:\n"
        f"{original['body']}\n\n"
        "Reply:"
    )

    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage

        llm = ChatGroq(
            model=config.groq_model,
            api_key=config.groq_api_key,
            temperature=0.4,
            max_tokens=config.ollama_max_tokens,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        reply = response.content.strip() if hasattr(response, "content") else str(response).strip()
        if reply:
            logger.info("Reply generated via Groq (%s)", config.groq_model)
            return reply
        logger.warning("Groq returned an empty response")
        return None
    except Exception as exc:
        logger.warning("Groq reply generation failed: %s", exc)
        return None


def _is_valid_reply_text(reply_text: Optional[str]) -> bool:
    return bool(reply_text and reply_text.strip())


def _retrying_ollama_request(url: str, payload: dict[str, Any], timeout: int) -> Optional[str]:
    for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("response"):
                reply = str(data["response"]).strip()
                if reply:
                    logger.info("Reply generated via Ollama (%s) on attempt %d", payload["model"], attempt)
                    return reply
            logger.warning("Unexpected or empty Ollama response on attempt %d: %s", attempt, data)
            return None
        except requests.exceptions.Timeout as exc:
            logger.warning(
                "Ollama timeout on attempt %d/%d after %ds for model '%s'.",
                attempt,
                OLLAMA_MAX_RETRIES,
                timeout,
                payload["model"],
            )
            if attempt < OLLAMA_MAX_RETRIES:
                sleep_time = OLLAMA_RETRY_BACKOFF ** (attempt - 1)
                logger.info("Retrying Ollama in %ds...", sleep_time)
                time.sleep(sleep_time)
                continue
            return None
        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "Ollama connection error on attempt %d/%d: %s",
                attempt,
                OLLAMA_MAX_RETRIES,
                exc,
            )
            if attempt < OLLAMA_MAX_RETRIES:
                sleep_time = OLLAMA_RETRY_BACKOFF ** (attempt - 1)
                logger.info("Retrying Ollama in %ds...", sleep_time)
                time.sleep(sleep_time)
                continue
            return None
        except (requests.RequestException, OSError) as exc:
            logger.warning("Ollama request failed on attempt %d/%d: %s", attempt, OLLAMA_MAX_RETRIES, exc)
            if attempt < OLLAMA_MAX_RETRIES:
                sleep_time = OLLAMA_RETRY_BACKOFF ** (attempt - 1)
                logger.info("Retrying Ollama in %ds...", sleep_time)
                time.sleep(sleep_time)
                continue
            return None
    return None


def generate_reply_with_ollama(original: ParsedEmail, config: GmailAgentConfig) -> str:
    """Generate a professional, context-aware reply using the Ollama LLM (fallback).

    Returns the reply text string on success. If Ollama times out, returns an
    empty response, or raises an exception, the function will retry and then
    return a safe fallback reply so the agent can continue processing.
    """
    prompt = (
        "You are an assistant that writes professional, concise, and context-aware "
        "email replies. Address the sender's message directly, keep a courteous tone, "
        "include clear next steps when appropriate, and limit the reply to 2-4 short "
        "paragraphs. Do not include a subject line or email headers — only the reply "
        "body text.\n\n"
        f"From: {original['sender']}\n"
        f"Subject: {original['subject']}\n\n"
        "Original message:\n"
        f"{original['body']}\n\n"
        "Reply:"
    )

    url = f"{config.ollama_url.rstrip('/')}/api/generate"
    payload = {
        "model": config.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": config.ollama_max_tokens},
    }

    reply = _retrying_ollama_request(url, payload, config.ollama_timeout)
    if _is_valid_reply_text(reply):
        return reply

    logger.warning("Ollama reply unavailable after retries; using fallback reply text")
    return FALLBACK_REPLY_TEXT


def generate_reply(original: ParsedEmail, config: GmailAgentConfig) -> Optional[str]:
    """Generate a reply using Groq (primary) then Ollama (fallback).

    Returns the reply text on success, or ``None`` if both LLMs are unavailable.
    The caller should skip sending and mark the email as failed when ``None`` is returned.
    """
    # 1. Try Groq first (fast cloud API)
    reply = generate_reply_with_groq(original, config)
    if reply:
        return reply

    # 2. Fall back to local Ollama
    logger.info("Falling back to Ollama for reply generation...")
    reply = generate_reply_with_ollama(original, config)
    if reply:
        return reply

    # 3. Both LLMs failed — do NOT send a generic canned reply
    logger.error(
        "Both Groq and Ollama are unavailable. Cannot generate a reply for: %s",
        original["sender"],
    )
    return None


def build_reply_message(
    to_addr: str,
    subject: str,
    thread_id: str,
    in_reply_to: str,
    body_text: str,
) -> dict[str, str]:
    """Build a MIME reply encoded for the Gmail API ``messages.send`` endpoint."""
    if not _is_valid_reply_text(body_text):
        logger.warning("Invalid reply text encountered; using fallback message")
        body_text = FALLBACK_REPLY_TEXT

    message = EmailMessage()
    message["To"] = to_addr
    normalized_subject = subject.strip()
    if not normalized_subject.lower().startswith("re:"):
        normalized_subject = f"Re: {normalized_subject}"
    message["Subject"] = normalized_subject

    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to

    message.set_content(body_text)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw, "threadId": thread_id}


def send_reply(
    service: Any,
    config: GmailAgentConfig,
    original: ParsedEmail,
    reply_text: str,
) -> Optional[dict[str, Any]]:
    """Send a reply in the same Gmail thread as the original message."""
    from googleapiclient.errors import HttpError

    _name, addr = parseaddr(original["sender"])
    if not addr:
        logger.error("Could not parse sender address from: %s", original["sender"])
        raise ValueError(f"Invalid sender address: {original['sender']}")

    if not original["thread_id"]:
        logger.error("Missing thread ID for message %s", original["id"])
        raise ValueError("Missing thread ID; cannot reply in-thread")

    body = build_reply_message(
        to_addr=addr,
        subject=original["subject"],
        thread_id=original["thread_id"],
        in_reply_to=original["message_id"],
        body_text=reply_text,
    )

    try:
        sent = (
            service.users()
            .messages()
            .send(userId=config.user_id, body=body)
            .execute()
        )
        logger.info(
            "Sent in-thread reply to %s (sent id: %s, thread: %s)",
            addr,
            sent.get("id"),
            original["thread_id"],
        )
        return sent
    except HttpError as exc:
        logger.exception("Gmail API error while sending reply: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Failed to send reply: %s", exc)
        return None


def mark_as_read(service: Any, config: GmailAgentConfig, msg_id: str) -> bool:
    """Remove the UNREAD label from a message after a successful reply."""
    from googleapiclient.errors import HttpError

    try:
        (
            service.users()
            .messages()
            .modify(
                userId=config.user_id,
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            )
            .execute()
        )
        logger.info("Marked message %s as read", msg_id)
        return True
    except HttpError as exc:
        logger.exception("Gmail API error while marking as read: %s", exc)
        return False
    except Exception as exc:
        logger.exception("Unexpected error while marking as read: %s", exc)
        return False


def _is_auto_generated(email: ParsedEmail) -> bool:
    sender = (email.get("sender") or "").lower()
    subject = (email.get("subject") or "").lower()
    headers = email.get("headers", {})

    auto_subject = [
        "mail delivery subsystem",
        "mailer-daemon",
        "postmaster",
        "delivery status notification",
        "failed delivery",
        "delivery failure",
        "undeliverable",
        "returned mail",
        "auto-generated",
        "auto reply",
        "auto-response",
        "out of office",
        "read receipt",
        "delivery status",
    ]
    no_reply_signals = [
        "no-reply",
        "noreply",
        "do-not-reply",
        "donotreply",
        "donotreply",
        "no reply",
        "do not reply",
    ]
    suspicious_senders = [
        "notifications@",
        "alerts@",
        "verify@",
        "security@",
        "admin@",
        "mailer-daemon",
        "postmaster",
        "support@",
        "noreply@",
        "no-reply@",
    ]

    if any(pattern in sender for pattern in suspicious_senders):
        return True
    if any(signal in subject for signal in no_reply_signals + auto_subject):
        return True

    precedence = headers.get("precedence", "").lower()
    auto_submitted = headers.get("auto-submitted", "").lower()
    if precedence in ("bulk", "junk", "list"):
        return True
    if auto_submitted and auto_submitted != "no":
        return True

    return False


def _appears_promotional_or_business(email: ParsedEmail) -> bool:
    sender = (email.get("sender") or "").lower()
    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()

    business_markers = [
        "invoice",
        "receipt",
        "order #",
        "shipping",
        "tracking",
        "payment",
        "subscription",
        "renewal",
        "account update",
        "statement",
        "billing",
        "payment due",
        "receipt",
        "delivery note",
        "ticket confirmation",
    ]
    marketing_markers = [
        "unsubscribe",
        "promotional",
        "marketing",
        "newsletter",
        "offer",
        "sale",
        "coupon",
        "discount",
        "deal",
        "webinar",
        "social media",
        "job alert",
        "new job",
        "career opportunity",
        "password reset",
        "one-time password",
        "otp",
        "verification code",
        "security code",
        "confirm your identity",
        "click below",
        "act now",
        "limited time",
    ]

    if any(marker in sender for marker in ["@facebook.com", "@twitter.com", "@linkedin.com", "@instagram.com", "@slack.com", "@paypal.com", "@stripe.com", "@amazon.com"]):
        return True

    if any(marker in subject for marker in business_markers + marketing_markers):
        return True
    if any(marker in body for marker in business_markers + marketing_markers):
        return True

    return False


def _has_personal_sender(email: ParsedEmail) -> bool:
    sender = (email.get("sender") or "")
    display_name, address = parseaddr(sender)
    display_name = (display_name or "").strip().lower()
    address = (address or "").strip().lower()

    if not address:
        return False

    generic_tokens = [
        "team",
        "support",
        "sales",
        "info",
        "newsletter",
        "service",
        "admin",
        "help",
        "alerts",
        "notifications",
        "no-reply",
        "noreply",
        "do-not-reply",
        "donotreply",
        "mailer-daemon",
        "postmaster",
    ]

    if any(token in display_name for token in generic_tokens):
        return False
    if any(token in address for token in generic_tokens):
        return False

    local_part = address.split("@", 1)[0]
    if any(token in local_part for token in generic_tokens):
        return False

    if display_name and any(char.isalpha() for char in display_name):
        return True
    if local_part.isalpha() or "." in local_part or "_" in local_part:
        return True

    return False


def needs_reply(email: ParsedEmail) -> tuple[bool, str]:
    """Classify an email as Needs Reply or No Reply Needed."""
    if _is_auto_generated(email):
        return False, "Auto-generated or no-reply email"
    if _appears_promotional_or_business(email):
        return False, "Promotional, business, or transactional email"
    if not _has_personal_sender(email):
        return False, "Sender does not appear to be a human contact"

    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()
    needs_reply_signals = [
        "question",
        "could you",
        "can you",
        "would you",
        "please",
        "let me know",
        "follow up",
        "next steps",
        "request",
        "need your",
        "help",
        "review",
        "proposal",
        "schedule",
        "meeting",
        "available",
        "touch base",
        "reply",
        "respond",
    ]
    no_reply_signals = [
        "thank you",
        "thanks",
        "received",
        "got it",
        "acknowledged",
        "confirm receipt",
        "delivery confirmation",
        "shipment",
        "invoice",
        "receipt",
    ]

    if any(signal in subject or signal in body for signal in no_reply_signals):
        return False, "Content suggests no reply is needed"

    if any(signal in subject or signal in body for signal in needs_reply_signals):
        return True, "Contains a reply request or question"

    return False, "Sender appears human but no explicit reply request was found"


def process_single_message(
    service: Any,
    config: GmailAgentConfig,
    msg_id: str,
) -> Optional[bool]:
    """Process one unread message: parse, decide whether to reply, send, and optionally mark read."""
    original = get_message(service, config, msg_id)
    logger.info(
        "Processing message from %s | subject: %s | thread: %s",
        original["sender"],
        original["subject"],
        original["thread_id"],
    )

    needs_response, reason = needs_reply(original)
    if not needs_response:
        logger.info("No reply needed: %s | %s", original["sender"], reason)
        if not mark_as_read(service, config, msg_id):
            logger.warning("Skipped message %s could not be marked as read", msg_id)
        return None

    reply_text = generate_reply(original, config)
    if not _is_valid_reply_text(reply_text):
        logger.error("No valid reply text generated for message %s", msg_id)
        return False

    sent = send_reply(service, config, original, reply_text)
    if not sent:
        logger.error("Failed to send reply for message %s", msg_id)
        return False

    if not mark_as_read(service, config, msg_id):
        logger.warning("Reply sent but failed to mark %s as read", msg_id)
    return True


def process_unread_and_reply(
    limit: Optional[int] = None,
    config: Optional[GmailAgentConfig] = None,
) -> dict[str, int]:
    """Process unread inbox messages end-to-end.

    Returns a summary dict with keys ``processed``, ``succeeded``, and ``failed``.

    Args:
        limit: Max messages to process. If None, uses env GMAIL_PROCESS_LIMIT.
            If the configured limit is 0 or unset, process all unread messages.
        config: GmailAgentConfig instance. If None, loads from environment.
    """
    cfg = config or GmailAgentConfig.from_env()
    configure_logging(cfg.log_level)

    effective_limit = limit
    if effective_limit is not None and effective_limit <= 0:
        effective_limit = None

    if effective_limit is None and cfg.process_limit > 0:
        effective_limit = cfg.process_limit

    if effective_limit is None:
        logger.info("No processing limit configured; will process all unread messages")

    service = get_gmail_service(cfg)
    message_refs = list_unread_messages(service, cfg)

    summary = {"processed": 0, "succeeded": 0, "failed": 0}
    if not message_refs:
        logger.info("No unread inbox messages to process")
        return summary

    if effective_limit is None:
        logger.info("Processing all %d unread messages", len(message_refs))
    else:
        logger.info("Will process up to %d of %d unread messages", effective_limit, len(message_refs))

    for message_ref in message_refs:
        if effective_limit is not None and summary["processed"] >= effective_limit:
            logger.info(
                "Reached processing limit (%d). %d messages remain unprocessed.",
                effective_limit,
                len(message_refs) - summary["processed"],
            )
            break

        msg_id = message_ref.get("id")
        if not msg_id:
            continue

        summary["processed"] += 1
        try:
            result = process_single_message(service, cfg, msg_id)
            if result is True:
                summary["succeeded"] += 1
            elif result is False:
                summary["failed"] += 1
            else:
                logger.info("Message %s was skipped and will not count as a failure", msg_id)
        except Exception as exc:
            logger.exception("Error processing message %s: %s", msg_id, exc)
            summary["failed"] += 1

    logger.info(
        "Run complete: processed=%d succeeded=%d failed=%d",
        summary["processed"],
        summary["succeeded"],
        summary["failed"],
    )
    return summary


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Read unread Gmail inbox messages, reply with Ollama, mark as read.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unread messages to process (overrides GMAIL_PROCESS_LIMIT)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""
    args = _parse_args(argv)
    config = GmailAgentConfig.from_env()
    configure_logging(config.log_level)

    try:
        summary = process_unread_and_reply(limit=args.limit, config=config)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        return 1

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())