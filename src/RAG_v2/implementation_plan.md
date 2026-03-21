# Implement Embedding Classifier Router (Strategy 4)

Thay thế LLM-based router bằng **lightweight embedding classifier**: dùng BGE-M3 để encode query → train Logistic Regression/SVM phân loại intent (chitchat/rag/tool_search) và domain (ctdt/quydinh/kehoach/stsv). Zero API cost, latency 10-50ms.

## User Review Required

> [!IMPORTANT]
> **2-level classification**: Classifier sẽ phân loại cả **intent** (Level 1: chitchat/rag/tool_search) và **domain** (Level 2: ctdt/quydinh/kehoach/stsv) trong cùng 1 model duy nhất, bằng cách dùng **6 labels** gộp: `chitchat`, `tool_search`, `ctdt`, `quydinh`, `kehoach`, `stsv`. Nếu label thuộc nhóm domain → intent tự động là `rag`.

> [!WARNING]
> Cần **load BGE-M3 model** để embed query khi inference. Nếu model đã được load sẵn trong pipeline (e.g. singleton), có thể reuse. Nếu không, classifier sẽ tự load model riêng (~2-3GB RAM). Bạn có muốn classifier tự load model riêng hay reuse model từ embedding layer?

---

## Proposed Changes

### Query Module — Training Data

#### [NEW] [training_data.py](file:///d:/GR/src/RAG_v2/query/training_data.py)

Chứa labeled training samples [(query, label)](file:///d:/GR/src/RAG_v2/query/router.py#48-74) cho 6 categories:
- `chitchat` (~50 samples): chào hỏi, cảm ơn, small talk
- `tool_search` (~30 samples): thời tiết, tin tức, tra cứu web
- `ctdt` (~60 samples): chương trình đào tạo, môn học, tín chỉ, khoa/viện
- `quydinh` (~60 samples): quy chế, quy định, điều kiện, kỷ luật
- `kehoach` (~60 samples): lịch thi, lịch học, thông báo, đăng ký
- `stsv` (~60 samples): thủ tục, hướng dẫn, KTX, bảo hiểm, thẻ SV

Mỗi sample là một câu hỏi thực tế mà sinh viên ĐHBK Hà Nội có thể hỏi, viết bằng tiếng Việt tự nhiên.

---

### Query Module — Domain Classifier

#### [NEW] [domain_classifier.py](file:///d:/GR/src/RAG_v2/query/domain_classifier.py)

Class `DomainClassifier`:
- [__init__(embedder, model_path)](file:///d:/GR/src/RAG_v2/embedding/bge_m3.py#28-59) — nhận embedder instance hoặc None (sẽ tự load BGE-M3)
- `train(training_data, test_size=0.2)` — embed + fit LogisticRegression, report accuracy
- `predict(query) → {"label": str, "intent": str, "confidence": float, "probabilities": dict}` — encode query → classify
- `save(path)` / `load(path)` — persist model bằng joblib (chỉ save classifier, KHÔNG save embedder)

Flow:
```
query → BGE-M3 embed (1024-dim) → LogisticRegression → label
                                                        ↓
                                        if label in {ctdt,quydinh,kehoach,stsv}:
                                            intent = "rag", domain = label
                                        elif label == "chitchat":
                                            intent = "chitchat", domain = None
                                        elif label == "tool_search":
                                            intent = "tool_search", domain = None
```

---

### Query Module — Router Update

#### [MODIFY] [router.py](file:///d:/GR/src/RAG_v2/query/router.py)

Thêm option `mode` (`"llm"` | `"classifier"`) vào `QueryRouter.__init__()`:
- `mode="llm"`: giữ nguyên behavior hiện tại (gọi OpenAI)
- `mode="classifier"`: dùng `DomainClassifier` thay thế
- Return dict mở rộng: `{"intent": str, "domain": str | None, "confidence": float}`

#### [MODIFY] [__init__.py](file:///d:/GR/src/RAG_v2/query/__init__.py)

Export thêm `DomainClassifier`.

---

### Query Module — Training Script

#### [NEW] [train_classifier.py](file:///d:/GR/src/RAG_v2/query/train_classifier.py)

Script chạy training:
1. Load training data từ `training_data.py`
2. Khởi tạo [BGEm3Embedder](file:///d:/GR/src/RAG_v2/embedding/bge_m3.py#17-140)
3. Train `DomainClassifier` với cross-validation
4. In classification report (precision, recall, F1 per class)
5. Save model vào `query/models/domain_classifier.joblib`

---

## Verification Plan

### Automated Tests

#### [NEW] [test_domain_classifier.py](file:///d:/GR/src/RAG_v2/query/test_domain_classifier.py)

Unit tests cho `DomainClassifier`:
1. **Test predict format**: verify output dict có đúng keys (`label`, [intent](file:///d:/GR/src/RAG_v2/query/router.py#86-109), `confidence`, `probabilities`)
2. **Test intent mapping**: verify `ctdt` → `intent="rag"`, `chitchat` → `intent="chitchat"`
3. **Test save/load**: train → save → load → predict should match
4. **Test known queries**: verify 5-10 obvious queries gồm cả tiếng Việt

```bash
cd d:\GR\src\RAG_v2
python -m pytest query/test_domain_classifier.py -v
```

### Manual Verification

Chạy training script và review classification report:
```bash
cd d:\GR\src\RAG_v2
python -m query.train_classifier
```

Kết quả mong đợi: Accuracy ≥ 85% trên test split, F1 ≥ 0.80 cho mỗi class.
