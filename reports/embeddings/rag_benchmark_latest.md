# RAG retrieval benchmark

2026-11-08T10:03:56.626790+00:00 · embeddings `sentence-transformers/all-MiniLM-L6-v2`

| Config | Knowledge Hit@1 | Hit@3 | MRR@5 | Careers strict-P@5 | Median ms (knowledge / careers) |
|---|---|---|---|---|---|
| vector | 0.767 | 0.9 | 0.842 | 0.767 | 8.0 / 4.6 |
| hybrid | 0.667 | 0.8 | 0.74 | 0.8 | 4.1 / 5.1 |
| vector+rerank | 0.8 | 0.967 | 0.884 | 0.858 | 47.4 / 69.3 |
| hybrid+rerank | 0.8 | 0.967 | 0.878 | 0.792 | 51.3 / 76.4 |

Profile retrieval Hit@3: plain 1.0 vs expanded 1.0 (n=18)
