"""PDF extraction and RAG analysis helpers for Andromeda.

The public functions in this module are intentionally dependency-light at
import time. PDF parsing and the Chroma vector database are imported only when
the user actually uploads a PDF, so the rest of the agent keeps working even
when optional PDF dependencies are not installed yet.
"""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.async_utils import run_in_thread
from agent.embeddings import embed_documents, embed_query

MAX_PDF_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 6
# Re-export for callers that historically imported dims from this module.
EMBEDDING_DIMENSIONS = 384



class PDFAnalysisError(ValueError):
    """Raised when an uploaded PDF cannot be analyzed safely."""


@dataclass(frozen=True)
class PDFChunk:
    """A text chunk stored in the vector database."""

    chunk_id: str
    text: str
    page_start: int
    page_end: int


@dataclass
class PDFDocumentIndex:
    """In-memory representation of an uploaded PDF and its vector store."""

    fingerprint: str
    filename: str
    text: str
    chunks: list[PDFChunk]
    collection: Any


_INDEX_CACHE: dict[str, PDFDocumentIndex] = {}


def _require_pdf_dependencies() -> tuple[Any, Any, Any]:
    """Import optional PDF dependencies with an actionable error message."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PDFAnalysisError(
            "PDF analysis requires the `pypdf` package. Install project dependencies and try again."
        ) from exc

    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as exc:
        raise PDFAnalysisError(
            "PDF analysis requires the `chromadb` package for vector search. Install project dependencies and try again."
        ) from exc

    return PdfReader, chromadb, Settings


def decode_pdf_payload(pdf_data_base64: str) -> bytes:
    """Decode and validate a base64 PDF payload from the UI."""
    if not pdf_data_base64:
        raise PDFAnalysisError("No PDF file was provided.")

    try:
        payload = base64.b64decode(pdf_data_base64, validate=True)
    except Exception as exc:
        raise PDFAnalysisError("The uploaded PDF payload is invalid.") from exc

    if not payload:
        raise PDFAnalysisError("The uploaded PDF file is empty.")
    if len(payload) > MAX_PDF_BYTES:
        raise PDFAnalysisError(
            f"The uploaded PDF is too large. The current limit is {MAX_PDF_BYTES // (1024 * 1024)} MB."
        )
    if not payload.startswith(b"%PDF"):
        raise PDFAnalysisError("Unsupported file type. Please upload a valid PDF file.")

    return payload


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from every page in a PDF, rejecting encrypted or empty files."""
    PdfReader, _, _ = _require_pdf_dependencies()

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as exc:
        raise PDFAnalysisError("The uploaded PDF could not be read as a valid PDF file.") from exc

    if getattr(reader, "is_encrypted", False):
        raise PDFAnalysisError("Encrypted or password-protected PDF files are not supported.")

    pages = getattr(reader, "pages", [])
    if not pages:
        raise PDFAnalysisError("The uploaded PDF does not contain any pages.")

    extracted_pages: list[str] = []
    for page_number, page in enumerate(pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        page_text = re.sub(r"[ \t]+", " ", page_text)
        page_text = re.sub(r"\n{3,}", "\n\n", page_text).strip()
        if page_text:
            extracted_pages.append(f"[Page {page_number}]\n{page_text}")

    full_text = "\n\n".join(extracted_pages).strip()
    if not full_text:
        raise PDFAnalysisError(
            "No extractable text was found in the PDF. Scanned image-only PDFs need OCR before analysis."
        )

    return full_text


def split_text_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[PDFChunk]:
    """Split extracted PDF text into overlapping chunks with page metadata."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")

    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []

    chunks: list[PDFChunk] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            boundary = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind(". ", start, end),
                normalized.rfind(" ", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk_text = normalized[start:end].strip()
        if chunk_text:
            page_numbers = [int(match) for match in re.findall(r"\[Page\s+(\d+)\]", chunk_text)]
            page_start = min(page_numbers) if page_numbers else 0
            page_end = max(page_numbers) if page_numbers else page_start
            chunks.append(
                PDFChunk(
                    chunk_id=f"chunk-{len(chunks)}",
                    text=chunk_text,
                    page_start=page_start,
                    page_end=page_end,
                )
            )

        if end >= text_length:
            break
        start = max(0, end - overlap)

    return chunks


def _build_chroma_index(fingerprint: str, filename: str, text: str) -> PDFDocumentIndex:
    """Create an in-memory Chroma collection for an extracted PDF."""
    _, chromadb, Settings = _require_pdf_dependencies()
    chunks = split_text_into_chunks(text)
    if not chunks:
        raise PDFAnalysisError("The PDF text could not be split into searchable chunks.")

    client = chromadb.Client(
        Settings(
            anonymized_telemetry=False,
            is_persistent=False,
        )
    )
    collection = client.create_collection(
        name=f"pdf_{fingerprint[:16]}_{uuid.uuid4().hex[:8]}",
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=embed_documents([chunk.text for chunk in chunks]),
        metadatas=[
            {
                "filename": filename,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
            }
            for chunk in chunks
        ],
    )

    return PDFDocumentIndex(
        fingerprint=fingerprint,
        filename=filename,
        text=text,
        chunks=chunks,
        collection=collection,
    )


def get_pdf_index(pdf_data_base64: str, filename: str = "uploaded.pdf") -> PDFDocumentIndex:
    """Return a cached Chroma index for an uploaded PDF payload."""
    pdf_bytes = decode_pdf_payload(pdf_data_base64)
    fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
    cached = _INDEX_CACHE.get(fingerprint)
    if cached:
        return cached

    text = extract_pdf_text(pdf_bytes)
    index = _build_chroma_index(fingerprint, filename or "uploaded.pdf", text)
    _INDEX_CACHE[fingerprint] = index

    # Keep memory bounded during long-running Streamlit/LangGraph sessions.
    if len(_INDEX_CACHE) > 5:
        oldest_key = next(iter(_INDEX_CACHE))
        if oldest_key != fingerprint:
            _INDEX_CACHE.pop(oldest_key, None)

    return index


def retrieve_context(index: PDFDocumentIndex, query: str, top_k: int = TOP_K) -> str:
    """Retrieve relevant PDF chunks from Chroma for a user question."""
    results = index.collection.query(
        query_embeddings=[embed_query(query)],
        n_results=min(top_k, len(index.chunks)),
        include=["documents", "metadatas", "distances"],
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    context_parts: list[str] = []
    for document, metadata in zip(documents, metadatas, strict=False):
        page_start = metadata.get("page_start", 0) if isinstance(metadata, dict) else 0
        page_end = metadata.get("page_end", page_start) if isinstance(metadata, dict) else page_start
        page_label = (
            f"Page {page_start}"
            if page_start == page_end or not page_end
            else f"Pages {page_start}-{page_end}"
        )
        context_parts.append(f"[{page_label}]\n{document}")

    return "\n\n---\n\n".join(context_parts).strip()


async def summarize_pdf(index: PDFDocumentIndex) -> str:
    """Generate a concise summary of the uploaded PDF using the existing model."""
    from agent.graph import get_model

    summary_source = index.text[:12000]
    messages = [
        SystemMessage(
            content=(
                "You summarize uploaded PDF documents. Be concise, accurate, and only use "
                "the document text provided by the user."
            )
        ),
        HumanMessage(
            content=(
                f"PDF filename: {index.filename}\n\n"
                f"Document text excerpt:\n{summary_source}\n\n"
                "Write a concise summary with the main points and important facts."
            )
        ),
    ]
    response = await get_model().ainvoke(messages)
    return str(response.content).strip() or "I could not generate a PDF summary."


async def answer_pdf_question(index: PDFDocumentIndex, question: str) -> str:
    """Answer a question using only retrieved PDF context."""
    from agent.graph import get_model

    # embed_query / Chroma are sync CPU — keep them off the ASGI event loop.
    context = await run_in_thread(retrieve_context, index, question)
    if not context:
        return "The answer was not found in the uploaded PDF."

    messages = [
        SystemMessage(
            content=(
                "You answer questions using only the uploaded PDF context. "
                "If the answer is not explicitly supported by the context, say: "
                "'The answer was not found in the uploaded PDF.' Do not use outside knowledge."
            )
        ),
        HumanMessage(
            content=(
                f"PDF filename: {index.filename}\n\n"
                f"Relevant PDF context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer clearly and cite page numbers when available."
            )
        ),
    ]
    response = await get_model().ainvoke(messages)
    answer = str(response.content).strip()
    return answer or "The answer was not found in the uploaded PDF."


async def pdf_analysis_response(
    question: str,
    pdf_data_base64: str,
    pdf_filename: str = "uploaded.pdf",
    summarize_only: bool = False,
) -> AIMessage:
    """Analyze an uploaded PDF and return a graph-compatible AI message."""
    try:
        # PDF parse + first BGE load (sentence_transformers import) is sync/blocking;
        # LangGraph blockbuster rejects that on the event loop — run in a worker thread.
        index = await run_in_thread(get_pdf_index, pdf_data_base64, pdf_filename)
        if summarize_only or not question.strip():
            summary = await summarize_pdf(index)
            return AIMessage(
                content=(
                    f"PDF uploaded: **{index.filename}**\n\n"
                    f"**Summary**\n{summary}\n\n"
                    "You can ask follow-up questions about this PDF without uploading it again."
                )
            )

        answer = await answer_pdf_question(index, question.strip())
        return AIMessage(content=answer)
    except PDFAnalysisError as exc:
        return AIMessage(content=f"PDF analysis error: {exc}")
