#!/usr/bin/env python3
"""Verify email processing setup and test connectivity.

This script checks that all required components are properly configured:
- Gmail OAuth credentials
- LLM service (Groq or Ollama)
- Email filtering logic
- Reply generation
- Gmail API connectivity

Run this before processing emails to ensure everything works.

Usage:
    uv run python src/verify_email_setup.py
    uv run python src/verify_email_setup.py --verbose
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
_SRC_ROOT = Path(__file__).resolve().parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

load_dotenv()


def check_oauth_credentials() -> tuple[bool, str]:
    """Check if Gmail OAuth credentials are configured."""
    client_secrets = os.getenv("GOOGLE_CLIENT_SECRETS", "client_secret.json")
    if not Path(client_secrets).exists():
        return False, f"✗ OAuth secrets file not found at: {client_secrets}"
    return True, f"✓ OAuth secrets file found at: {client_secrets}"


def check_groq_api() -> tuple[bool, str]:
    """Check if Groq API is configured."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return False, "✗ GROQ_API_KEY not set in .env"
    if len(groq_key) < 10:
        return False, "✗ GROQ_API_KEY appears invalid (too short)"
    return True, "✓ Groq API key configured"


def check_ollama() -> tuple[bool, str]:
    """Check if Ollama is available."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        import requests

        response = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if response.status_code == 200:
            return True, f"✓ Ollama accessible at {ollama_url}"
        return False, f"✗ Ollama returned error at {ollama_url}"
    except Exception as e:
        return (
            False,
            f"✗ Ollama not accessible at {ollama_url} ({str(e)[:50]})",
        )


def check_gmail_connection() -> tuple[bool, str]:
    """Test Gmail API connection."""
    try:
        from gmail_agent import GmailAgentConfig, get_gmail_service, configure_logging

        configure_logging("WARNING")
        config = GmailAgentConfig.from_env()
        service = get_gmail_service(config)

        # Try to call a simple API method
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown")
        return True, f"✓ Gmail API connected (logged in as: {email_address})"
    except FileNotFoundError as e:
        return False, f"✗ Gmail OAuth setup required: {str(e)[:80]}"
    except Exception as e:
        return False, f"✗ Gmail configuration failed: {str(e)[:80]}"


def check_email_filtering() -> tuple[bool, str]:
    """Test email filtering logic."""
    try:
        from process_emails_comprehensive import is_spam_or_promotional, ParsedEmail

        # Test cases
        test_emails = [
            (
                ParsedEmail(
                    id="1",
                    thread_id="1",
                    sender="noreply@example.com",
                    subject="Password Reset",
                    message_id="<1>",
                    body="Click here to reset your password",
                ),
                True,  # Should be filtered
            ),
            (
                ParsedEmail(
                    id="2",
                    thread_id="2",
                    sender="john@example.com",
                    subject="Meeting Tomorrow",
                    message_id="<2>",
                    body="Let's discuss the project tomorrow at 2pm",
                ),
                False,  # Should NOT be filtered
            ),
            (
                ParsedEmail(
                    id="3",
                    thread_id="3",
                    sender="sales@example.com",
                    subject="Special Sale - 50% Off",
                    message_id="<3>",
                    body="Limited time offer on all products",
                ),
                True,  # Should be filtered
            ),
        ]

        passed = 0
        for test_email, should_filter in test_emails:
            result = is_spam_or_promotional(test_email)
            if result == should_filter:
                passed += 1

        if passed == len(test_emails):
            return True, f"✓ Email filtering logic works ({passed}/{len(test_emails)} test cases passed)"
        return False, f"✗ Email filtering failed ({passed}/{len(test_emails)} test cases passed)"
    except Exception as e:
        return False, f"✗ Email filtering check failed: {str(e)[:80]}"


def check_reply_generation() -> tuple[bool, str]:
    """Test reply generation (without actually generating)."""
    try:
        from langgraph.graph import StateGraph

        # The system uses Groq which requires network access
        # Just check that the LangChain import works
        return True, "✓ Reply generation libraries available"
    except Exception as e:
        return (
            False,
            f"✗ Reply generation libraries missing: {str(e)[:80]}",
        )


def main(verbose: bool = False) -> int:
    """Run all checks and report status."""
    print("=" * 70)
    print("EMAIL PROCESSING SETUP VERIFICATION")
    print("=" * 70)
    print()

    checks = [
        ("OAuth Credentials", check_oauth_credentials),
        ("Groq API", check_groq_api),
        ("Ollama Service", check_ollama),
        ("Gmail API Connection", check_gmail_connection),
        ("Email Filtering Logic", check_email_filtering),
        ("Reply Generation", check_reply_generation),
    ]

    results = []
    failed_count = 0

    for check_name, check_func in checks:
        print(f"Checking {check_name}...", end=" ", flush=True)
        success, message = check_func()
        print(message)
        results.append((check_name, success, message))
        if not success:
            failed_count += 1

    print()
    print("=" * 70)

    # Critical checks
    critical = [
        "OAuth Credentials",
        "Gmail API Connection",
        "Email Filtering Logic",
    ]

    # Warning checks (not critical but needed for full functionality)
    warning_checks = ["Groq API", "Ollama Service"]

    critical_failed = 0
    warning_failed = 0

    for check_name, success, _ in results:
        if not success:
            if check_name in critical:
                critical_failed += 1
            elif check_name in warning_checks:
                warning_failed += 1

    if critical_failed > 0:
        print(f"✗ SETUP INCOMPLETE: {critical_failed} critical check(s) failed")
        print("  Please fix the issues above before processing emails.")
        print()
        return 1
    elif warning_failed > 0:
        print(f"⚠ WARNING: {warning_failed} optional service(s) not available")
        print("  Email processing will work, but replies may fail.")
        print("  Set up Groq API or Ollama to enable automatic reply generation.")
        print()
        return 0
    else:
        print("✓ ALL CHECKS PASSED - System ready!")
        print()
        print("You can now process emails with:")
        print("  uv run python src/demo_email_processing.py")
        print()
        return 0


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    sys.exit(main(verbose))

