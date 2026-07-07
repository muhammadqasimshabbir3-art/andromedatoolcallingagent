"""Unit tests for PDF analysis helpers."""

import pytest
from langchain_core.messages import HumanMessage

from agent.graph import decision_agent
from agent.pdf_analysis import split_text_into_chunks


def test_split_text_into_overlapping_page_chunks():
    text = (
        "[Page 1]\n"
        + "Alpha beta gamma. " * 80
        + "\n\n[Page 2]\n"
        + "Delta epsilon zeta. " * 80
    )

    chunks = split_text_into_chunks(text, chunk_size=500, overlap=80)

    assert len(chunks) > 1
    assert chunks[0].text.startswith("[Page 1]")
    assert chunks[0].page_start == 1
    assert all(chunk.text for chunk in chunks)


@pytest.mark.anyio
async def test_pdf_payload_routes_to_pdf_analysis():
    result = await decision_agent(
        {
            "messages": [HumanMessage(content="What is the main conclusion?")],
            "pdf_data_base64": "JVBERi0xLjQK",
            "pdf_filename": "sample.pdf",
        }
    )

    assert result["agent_route"] == "run_pdf_analysis"
