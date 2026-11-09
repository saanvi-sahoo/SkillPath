# RAG retrieval benchmark

2026-11-09T14:09:01.876715+00:00 · embeddings `sentence-transformers/all-MiniLM-L6-v2`

| Config | Knowledge Hit@1 | Hit@3 | MRR@5 | Careers strict-P@5 | Median ms (knowledge / careers) |
|---|---|---|---|---|---|
| vector | 0.767 | 0.9 | 0.842 | 0.767 | 9.0 / 10.4 |
| hybrid | 0.667 | 0.8 | 0.74 | 0.8 | 11.7 / 10.0 |
| vector+rerank | 0.8 | 0.967 | 0.884 | 0.858 | 46.0 / 68.2 |
| hybrid+rerank | 0.8 | 0.967 | 0.878 | 0.792 | 50.5 / 76.6 |

Profile retrieval Hit@3: plain 1.0 vs expanded 1.0 (n=18)
