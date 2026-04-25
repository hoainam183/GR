## Ket qua Evaluation - LangGraph Agent vs RAG v2

### Simple Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | 0.88 | 0.73 |
| Avg Latency | 75.0s | 71.5s |
| Route Accuracy | N/A | 100% |

Nhan xet:
- Agent khong cai thien cho nhom simple trong lan chay nay (keyword score giam 0.15).
- Tuy nhien do tre trung binh cua nhanh agent route (thuc te la rag_v2) van thap hon nhe.

### Complex Questions (n=10)
| Metric | RAG v2 | Agent |
|---|---|---|
| Keyword Score | 0.97 | 1.00 |
| Tool Selection Accuracy | N/A | 80% |
| Avg Latency | 110.5s | 69.8s |
| Avg Iterations | N/A | 1.7 |
| Route Accuracy | N/A | 80% |

Nhan xet:
- Agent dat cai thien nho ve do dung keyword (+0.03) cho nhom complex.
- Agent nhanh hon dang ke trong nhom complex (giam trung binh 40.7s/cau).

### Ket luan nhanh
- Cac cau simple co regression hay khong: Co
- Cac cau complex agent tot hon rag_v2 hay khong: Co
- Snapshot MongoDB agent_traces da thu duoc: Khong (agent_traces_count = 0)
