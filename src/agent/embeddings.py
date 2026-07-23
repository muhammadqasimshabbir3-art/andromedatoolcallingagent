"""Local neural embeddings for semantic RAG (business docs + PDF).

Uses BAAI/bge-small-en-v1.5 via sentence-transformers — a free, CPU-friendly
retrieval model (384-d). Vectors are stored under ``models/bge-small-en-v1.5``.

Download once:
    python scripts/download_embedding_model.py

Large documents (2–3 MB) are still split into overlapping chunks before
embedding; the model has a ~512-token context window and embeds chunks, not
whole files.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Sequence

# Strong small English retrieval model (same dim family as prior hash embedder).
MODEL_ID = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
# BGE asymmetric retrieval: instruct queries, not passages.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODEL_DIR = _REPO_ROOT / "models" / "bge-small-en-v1.5"


def model_dir() -> Path:
    """Return the on-disk model directory (override with EMBEDDING_MODEL_PATH)."""
    override = (os.getenv("EMBEDDING_MODEL_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_MODEL_DIR


def _model_ready(path: Path) -> bool:
    """Return True if a saved SentenceTransformer folder looks complete."""
    if not path.is_dir():
        return False
    # sentence-transformers saves config + modules; modules.json is a reliable marker.
    return (path / "modules.json").is_file() or (path / "config.json").is_file()


@lru_cache(maxsize=1)
def get_embedding_model():
    """Lazy-load the local BGE model (downloads to models/ on first miss)."""
    from sentence_transformers import SentenceTransformer

    path = model_dir()
    if _model_ready(path):
        return SentenceTransformer(str(path))

    # First run: pull from Hugging Face Hub (public; ignore broken local HF oauth),
    # then persist under models/ for offline restarts.
    path.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(MODEL_ID, token=False)
    model.save(str(path))
    return model


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Embed document / chunk passages (no query instruction)."""
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(
        list(texts),
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [vector.tolist() for vector in vectors]


def embed_text(text: str) -> list[float]:
    """Embed a single document chunk."""
    return embed_documents([text or ""])[0]


def embed_query(text: str) -> list[float]:
    """Embed a search query with BGE's retrieval instruction prefix."""
    model = get_embedding_model()
    vector = model.encode(
        f"{QUERY_INSTRUCTION}{(text or '').strip()}",
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vector.tolist()


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "MODEL_ID",
    "QUERY_INSTRUCTION",
    "embed_documents",
    "embed_query",
    "embed_text",
    "get_embedding_model",
    "model_dir",
]
