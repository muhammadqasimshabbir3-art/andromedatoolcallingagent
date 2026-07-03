#!/usr/bin/env python3
"""Simple demonstration: Process your unread Gmail emails.

Run this script to automatically:
1. Read all unread emails from your Gmail inbox
2. Filter out spam/promotional/automated emails
3. Generate professional replies using AI
4. Send replies in-thread automatically
5. Mark original emails as Read
6. Display a comprehensive summary report

Requirements:
- Gmail OAuth credentials file at ./client_secret.json
- GROQ_API_KEY set in .env (for reply generation)
- Or OLLAMA_URL and OLLAMA_MODEL configured (fallback)

Usage:
    # Process all unread emails:
    uv run python src/demo_email_processing.py

    # Process only first 5 emails:
    uv run python src/demo_email_processing.py --limit 5

    # Use only Ollama (skip Groq):
    uv run python src/demo_email_processing.py --use-ollama-only
"""

import sys
from pathlib import Path

# Add src to path
_SRC_ROOT = Path(__file__).resolve().parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from process_emails_comprehensive import (  # noqa: E402
    main,
)


if __name__ == "__main__":
    sys.exit(main())

