# Prototype RAG — Solar Business Knowledge

Short design note for reviewers. Details: [README.md](./README.md), [AgentWorkflow.md](./AgentWorkflow.md).

## Why

Store SQL answers *numbers* (stock, revenue). Policies / FAQs / SOPs need *documents*. We built a hybrid RAG path so Solar can answer “what is our return policy?” from Neon with citations the user can audit.

**Sibling paths (not this file):** live commerce facts → Neon **READ SQL** (AST-gated). Mutations → **Read-Only Guard** (keyword suspicion bulletin → LLM READ/WRITE). Same design idea as RAG: **keywords are additive signals**, not the sole decision — they raise relevance / scrutiny; the model + stronger layers decide.

## What we implemented

| Piece | Choice | Why |
|-------|--------|-----|
| Storage | Neon `business_documents` + `business_chunks` | Same DB as store; simple ops |
| Chunking | ~1500 chars, 200 overlap | Large docs (MB-scale) must be split; BGE window ~512 tokens |
| Keywords | BM25 + phrase + title/tag scores | Exact policy terms still matter — not dropped when semantic landed |
| Semantic | **BAAI/bge-small-en-v1.5** (local, free, 384-d) | Meaning match (“money back” → refund); not hash bags |
| Fusion | 0.35 BM25 + 0.40 BGE + 0.15 phrase + 0.10 field | Best of keywords + meaning |
| Top-k | **5** | Enough context, bounded latency |
| Trust layer | 2-pass Groq read | Model must judge **each** of the 5 before answering |
| Citations | All top-5 listed (USED / reviewed) | User sees where the answer came from |

## End-to-end flow

```text
User policy / FAQ / SOP question
  → decision_agent (graph.py)
       (mutations already diverted to reject_db_mutation if WRITE)
  → run_business_rag
  → retrieve_business_chunks (hybrid score, TOP_K=5)
       BM25 + phrase/title/tag keywords + BGE (BAAI/bge-small-en-v1.5)
  → Pass 1: analyze each [1]…[5] → RELEVANT / NOT_RELEVANT + quotes
  → Pass 2: answer ONLY from RELEVANT quotes, cite [1], [2], …
  → Append Source analysis (trust layer) + Sources (all 5, USED vs reviewed)
```

Hybrid is **additive**: we did **not** drop keywords when adding BGE. Keywords still score exact policy language; BGE covers paraphrase.

## Where it lives

| Concern | File |
|---------|------|
| Route to RAG | `src/agent/graph.py` (`run_business_rag`), `routing` / `needs_business_rag` |
| Retrieve + trust + Sources | `src/agent/custom_tools/business_rag_tools.py` |
| Load / run BGE | `src/agent/embeddings.py` |
| Model on disk | `models/bge-small-en-v1.5/` (download script; weights gitignored) |
| Seed corpus + embed chunks | `scripts/seed_business_rag.py` |
| Download model | `scripts/download_embedding_model.py` |
| Deps | `pyproject.toml` → `sentence-transformers`, `torch` |
| UI pipeline step | `frontend/src/lib/workflowSteps.ts` → 📚 Business RAG |
| PDF semantic search | `src/agent/pdf_analysis.py` (same BGE helpers) |
| Guard (sibling) | `src/agent/custom_tools/db_safety_agent.py` — keywords elevate LLM; not this RAG path |

## How pieces connect

```text
Neon chunks.embedding (JSONB, from seed)
        ↑ embed_documents() at seed time
        │
Query ──embed_query()──► cosine vs chunk vectors  ─┐
Query ──tokenize()────► BM25 / phrase / field     ─┼─► fused score → top 5
                                                   ↓
                              Groq trust pass 1 + 2 → answer + Sources footer
```

## Reliability rules

1. Answer only from sources marked **RELEVANT** (and their quotes).
2. Always show **all top-5** Sources so unused passages are still visible.
3. Re-seed after changing the embedder so stored vectors match query vectors.
4. Store SQL stays separate — RAG is **not** for live stock/order totals.
5. “I want to replace a product, what should I do?” → RAG / advice. “Correct the customer's address” → Guard WRITE block (not RAG).

## Ops commands

```bash
python scripts/download_embedding_model.py   # once — models/bge-small-en-v1.5
python scripts/seed_business_rag.py          # re-run after changing embedder
# then restart langgraph / UI
```

## Quick try

- What is our return and refund policy?
- How do I get my money back for an unopened accessory? *(paraphrase → BGE)*
- Is water damage covered under warranty?
- What are Friday store hours?

Expect pipeline step **📚 Business RAG**, a grounded answer, trust analysis, and a **Sources (top 5…)** footer.
