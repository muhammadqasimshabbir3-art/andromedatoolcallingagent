# Local embedding models (downloaded, not committed)

Use:

```bash
python scripts/download_embedding_model.py
```

This creates `bge-small-en-v1.5/` (~130 MB) — BAAI/bge-small-en-v1.5 for
semantic RAG over business docs and PDFs.

After downloading (or switching models), re-seed Neon chunks:

```bash
python scripts/seed_business_rag.py
```
