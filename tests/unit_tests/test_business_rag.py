"""Unit tests for business RAG routing and traditional keyword scoring."""

from agent.custom_tools.business_rag_tools import (
    _bm25_scores,
    _tokenize,
    needs_business_rag,
    score_chunk_candidates,
)
from agent.custom_tools.database_tools import needs_store_database
from agent.embeddings import embed_text
from agent.graph import _pick_route
from langchain_core.messages import HumanMessage


def test_needs_business_rag_for_policy():
    assert needs_business_rag("what is our return policy?")
    assert needs_business_rag("warranty coverage for earbuds")
    assert needs_business_rag(
        "I am customers i want to replace a product what should i do"
    )
    assert not needs_business_rag("how many products are low in stock?")


def test_store_vs_rag_routing():
    rag_route = _pick_route(
        "what is the refund policy?",
        [HumanMessage(content="what is the refund policy?")],
    )
    replace_route = _pick_route(
        "I am customers i want to replace a product what should i do",
        [
            HumanMessage(
                content="I am customers i want to replace a product what should i do"
            )
        ],
    )
    store_route = _pick_route(
        "which products are low in stock?",
        [HumanMessage(content="which products are low in stock?")],
    )
    assert rag_route == "run_business_rag"
    assert replace_route == "run_business_rag"
    assert store_route == "call_model"
    assert needs_store_database("low stock products")
    assert not needs_store_database(
        "I am customers i want to replace a product what should i do"
    )

def test_bm25_ranks_keyword_match_higher():
    query_tokens = _tokenize("return refund policy")
    docs = [
        _tokenize("wireless earbuds battery life and charging tips"),
        _tokenize("solar store return and refund policy for unopened electronics"),
        _tokenize("opening hours friday schedule for downtown store"),
    ]
    scores = _bm25_scores(query_tokens, docs)
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_hybrid_prefers_return_policy_for_refund_query():
    candidates = [
        {
            "chunk_id": 1,
            "title": "Electronics Product Care Guide",
            "doc_type": "product_guide",
            "tags": ["electronics", "care"],
            "content": "Charge case weekly. Avoid sweat damage to earbuds.",
            "embedding": embed_text(
                "Charge case weekly. Avoid sweat damage to earbuds."
            ),
            "doc_metadata": {},
        },
        {
            "chunk_id": 2,
            "title": "Solar Store Return & Refund Policy",
            "doc_type": "policy",
            "tags": ["returns", "refunds", "customers"],
            "content": (
                "Unopened electronics may be returned within 14 days. "
                "Card refunds take 5-7 business days."
            ),
            "embedding": embed_text(
                "Unopened electronics may be returned within 14 days. "
                "Card refunds take 5-7 business days."
            ),
            "doc_metadata": {"department": "customer_success"},
        },
    ]
    ranked = score_chunk_candidates("what is the return refund policy?", candidates)
    assert ranked[0]["title"] == "Solar Store Return & Refund Policy"
    assert "bm25" in ranked[0]["score_breakdown"]
    assert "field_keywords" in ranked[0]["score_breakdown"]


def test_format_rag_sources_lists_all_top_passages():
    from agent.custom_tools.business_rag_tools import format_rag_sources

    footer = format_rag_sources(
        [
            {
                "title": "Gift Cards & Store Credit Policy",
                "doc_type": "policy",
                "score": 0.9,
                "doc_metadata": {"department": "finance", "version": "1.2"},
            },
            {
                "title": "Gift Cards & Store Credit Policy",
                "doc_type": "policy",
                "score": 0.7,
                "doc_metadata": {"department": "finance", "version": "1.2"},
            },
        ],
        relevant_indexes={1},
    )
    assert footer.startswith("Sources (top 2 retrieved")
    assert "Gift Cards & Store Credit Policy" in footer
    assert "business_documents" in footer
    assert "department=finance" in footer
    assert "[1]" in footer
    assert "[2]" in footer
    assert "USED" in footer
    assert "reviewed" in footer


def test_trust_layer_parses_relevant_sources_and_two_pass_answer():
    from agent.custom_tools.business_rag_tools import (
        _parse_relevant_source_indexes,
        answer_business_rag_sync,
        format_source_analysis_section,
    )

    analysis = """
### [1] Warranty Coverage Guide
- Verdict: RELEVANT
- Quotes: Electronics accessories: 6 months manufacturer warranty.
- Why: Direct warranty length for earbuds.

### [2] Privacy & Customer Data Policy
- Verdict: NOT_RELEVANT
- Quotes: none
- Why: About privacy, not warranty.
"""
    chunks = [
        {"title": "Warranty Coverage Guide", "doc_type": "policy"},
        {"title": "Privacy & Customer Data Policy", "doc_type": "policy"},
    ]
    assert _parse_relevant_source_indexes(analysis, 2) == {1}
    section = format_source_analysis_section(analysis, chunks)
    assert "used: [1] Warranty Coverage Guide" in section

    calls: list[str] = []

    def fake_llm(messages):
        content = messages[0]["content"]
        calls.append(content[:80])
        if "document analyst" in content or "trust layer" in content.lower():
            return analysis
        assert "Source analysis:" in content
        return "Earbuds accessories have a 6-month warranty [1]."

    # Avoid live Neon: stub retrieve by patching via monkeypatch-like injection
    import agent.custom_tools.business_rag_tools as rag

    original = rag.retrieve_business_chunks

    def fake_retrieve(query: str, top_k: int = 5):
        return [
            {
                "title": "Warranty Coverage Guide",
                "doc_type": "policy",
                "content": "Electronics accessories (chargers, earbuds, bulbs): 6 months.",
                "score": 0.9,
                "doc_metadata": {"department": "after_sales", "version": "1.4"},
                "tags": ["warranty"],
            },
            {
                "title": "Privacy & Customer Data Policy",
                "doc_type": "policy",
                "content": "We do not sell customer lists.",
                "score": 0.4,
                "doc_metadata": {"department": "compliance", "version": "1.3"},
                "tags": ["privacy"],
            },
        ][:top_k]

    rag.retrieve_business_chunks = fake_retrieve
    try:
        text = answer_business_rag_sync("warranty on earbuds?", fake_llm)
    finally:
        rag.retrieve_business_chunks = original

    assert "6-month warranty" in text or "6-month" in text
    assert "Source analysis (trust layer)" in text
    assert "Sources (top 2 retrieved" in text
    assert "USED" in text
    assert "[1] Warranty Coverage Guide" in text
    assert len(calls) == 2
