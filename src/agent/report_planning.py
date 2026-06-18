"""Generic report topic and section inference for the decision agent."""

from __future__ import annotations

import re

# (section title, user-language keywords, web-search keywords)
DEFAULT_REPORT_ASPECTS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("Overview", ("overview", "what is", "introduction", "about"), ("overview", "what is", "introduction")),
    ("Key Points", ("key point", "important", "main", "highlights"), ("key", "important", "facts")),
    ("Recommendations", ("recommend", "should", "best practice", "advice"), ("recommend", "best practice", "tips")),
    ("Summary", ("summary", "conclusion", "in summary"), ("summary", "conclusion")),
]

OPTIONAL_REPORT_ASPECTS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("Causes", ("cause", "causes", "reason", "why", "origin"), ("cause", "reason", "origin", "factor")),
    (
        "Prevention",
        ("prevent", "prevention", "avoid", "protect", "preventions"),
        ("prevent", "protection", "avoid", "control"),
    ),
    (
        "Treatment & Solutions",
        ("cure", "treatment", "treat", "therapy", "solution", "remedy"),
        ("treat", "cure", "therapy", "solution", "management"),
    ),
    ("Benefits", ("benefit", "advantage", "pros"), ("benefit", "advantage")),
    ("Challenges", ("challenge", "risk", "problem", "issue"), ("challenge", "risk", "problem")),
    ("Applications", ("application", "use case", "uses", "how to use"), ("application", "use case")),
]


def extract_report_topic(user_text: str) -> str:
    """Infer the report subject from natural language (any topic, not hardcoded)."""
    text = user_text.strip()
    lowered = text.lower()

    patterns = (
        r"(?i)\b(?:about|on|regarding|for)\s+([a-zA-Z][\w\s\-]{2,60}?)"
        r"(?:\s+disease|\s+topic|\s+subject|\s+report|\s+pdf\b|,|\.|$)",
        r"(?i)\b([a-zA-Z][\w\s\-]{2,40}?)\s+disease\b",
        r"(?i)\bpdf\s+(?:file\s+)?(?:for|about|on)\s+([a-zA-Z][\w\s\-]{2,60}?)(?:\s+report|,|\.|$)",
        r"(?i)\breport\s+(?:on|about|for)\s+([a-zA-Z][\w\s\-]{2,60}?)(?:\s+report|,|\.|$)",
        r"(?i)\bstylized\s+(?:pdf\s+)?(?:for|about|on)\s+([a-zA-Z][\w\s\-]{2,60}?)(?:\s+report|,|\.|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            topic = _clean_topic(match.group(1))
            if topic:
                return topic

    # Fallback: meaningful capitalized phrase or last substantive noun chunk
    skip = {
        "yourself", "pdf", "file", "report", "email", "internet", "search",
        "create", "generate", "stylized", "good", "pattern", "formatting",
        "colors", "colours", "then", "send", "me", "via",
    }
    words = re.findall(r"[a-zA-Z]{3,}", lowered)
    candidates = [word for word in words if word not in skip]
    if candidates:
        # Prefer longer tokens near disease/report semantics
        for word in reversed(candidates):
            if len(word) >= 4:
                return word.title()

    return "General Report"


def _clean_topic(raw: str) -> str:
    topic = re.sub(
        r"(?i)\b(it|its|they|them|this|that|with|and|then|you|can|have|which|different)\b",
        " ",
        raw,
    )
    topic = re.sub(r"\s+", " ", topic).strip(" .,-")
    if len(topic) < 2:
        return ""
    return topic.title()


def infer_report_aspects(
    user_text: str,
) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    """Build PDF sections from what the user asked for, with sensible defaults."""
    lowered = user_text.lower()
    aspects: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    for title, user_keys, search_keys in OPTIONAL_REPORT_ASPECTS:
        if any(key in lowered for key in user_keys):
            aspects.append((title, user_keys, search_keys))

    if aspects:
        if not any(title == "Overview" for title, _, _ in aspects):
            aspects.insert(0, DEFAULT_REPORT_ASPECTS[0])
        return aspects

    return list(DEFAULT_REPORT_ASPECTS)


def build_content_search_query(
    topic: str,
    aspects: list[tuple[str, tuple[str, ...], tuple[str, ...]]],
) -> str:
    """Compose a web search query from topic + requested aspects."""
    search_terms: list[str] = []
    for _, _, search_keys in aspects:
        search_terms.extend(search_keys[:2])
    unique_terms = list(dict.fromkeys(search_terms))[:6]
    return f"{topic} " + " ".join(unique_terms)


def build_design_search_query(user_text: str) -> str:
    """Compose a PDF layout/design search query from user styling language."""
    lowered = user_text.lower()
    style_bits = []
    for token in ("color", "colour", "format", "pattern", "layout", "section", "design", "stylized"):
        if token in lowered:
            style_bits.append(token)
    style_part = " ".join(style_bits) if style_bits else "professional layout sections colors"
    return f"PDF report {style_part} formatting best practices"


def report_pdf_filename(topic: str) -> str:
    """Topic-based PDF path (generic, not disease-specific)."""
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_") or "report"
    return f"./reports/{slug}_report.pdf"
