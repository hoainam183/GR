# RAG v2 — University Chatbot System

Hệ thống chatbot RAG cho trường đại học, thiết kế theo kiến trúc 8 Layers.

## Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│   Query Router      │ → Chitchat? / RAG? / Tool Search?
└────────┬────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Chitchat    RAG Flow
    │         │
    │    ┌────▼────────────┐
    │    │ Query Reflection │ → Rewrite, Clarify, Add context
    │    └────┬────────────┘
    │         │
    │    ┌────▼────────────┐
    │    │ Ensemble Embed   │ → BGE-M3 + E5-large
    │    └────┬────────────┘
    │         │
    │    ┌────▼────────────┐
    │    │ Hybrid Search    │ → Qdrant + Elasticsearch
    │    └────┬────────────┘
    │         │
    │    ┌────▼────────────┐
    │    │ Reranker         │ → BGE-v2-M3 → Top 5
    │    └────┬────────────┘
    │         │
    └────┬────┘
         │
    ┌────▼────────────┐
    │ Chat Model       │ → OpenAI GPT
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ Self Evaluation  │ → Quality check
    └────┬────────────┘
         │
    ┌────┴────┐
    │ OK      │ FAIL → Tavily Search → Re-generate
    ▼         │
Final Answer  │
    │◄────────┘
    ▼
┌─────────────────────┐
│ MongoDB Memory      │ → Save history + state
└─────────────────────┘
```

## Folder Structure

```
RAG_v2/
├── data/               # Raw data (đã có)
├── document_loader/    # PDF → Markdown (đã có)
├── chunking/           # Chunking pipeline (đã có)
├── embedding/          # BGE-M3 + E5 ensemble
├── retrieval/          # Qdrant + Elasticsearch hybrid
├── reranking/          # BGE-v2-M3 reranker
├── query/              # Router + Reflection
├── llm/                # Chat Model + Self Eval
├── tools/              # Tavily search
├── memory/             # MongoDB persistence
├── pipeline/           # Orchestration
├── api/                # FastAPI backend
└── config/             # Settings
```

## Development Phases

Xem chi tiết: [rag_v2_phase_tasks.md](./rag_v2_phase_tasks.md)
