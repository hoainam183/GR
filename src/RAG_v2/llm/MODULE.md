# Module: `llm`

Tầng LLM provider-agnostic: một interface chung `BaseLLM`, nhiều nhà cung cấp (Gemini, DeepSeek, LM Studio) qua endpoint OpenAI-compatible, cùng bộ prompt tiếng Việt và bước tự đánh giá chất lượng câu trả lời.

## Files

### `base.py`
Định nghĩa interface trừu tượng chung cho mọi LLM backend; provider cụ thể chỉ nhận credentials/model params, không đọc `Settings` trực tiếp.
- `BaseLLM.generate()` — sinh câu trả lời dạng blocking theo mode (rag/chitchat/self_eval/reformat).
- `BaseLLM.generate_stream()` — sinh câu trả lời theo luồng, yield từng đoạn text.

### `deepseek.py`
Provider DeepSeek qua API OpenAI-compatible, có retry exponential backoff khi bị rate-limit; đây là model chính sinh câu trả lời.
- `DeepSeekLLM.generate()` — gọi chat completion, retry tối đa 3 lần khi `RateLimitError`.
- `DeepSeekLLM.generate_stream()` — mở stream, chỉ retry đến chunk đầu rồi yield các delta.
- `DeepSeekLLM._build_messages()` — chọn bộ message theo mode.

### `gemini.py`
Provider Gemini qua endpoint OpenAI-compatible của Google; dùng cho reflection và synthesis.
- `GeminiLLM.generate()` — sinh câu trả lời đầy đủ, retry backoff khi rate-limit.
- `GeminiLLM.generate_stream()` — sinh câu trả lời theo luồng.
- `GeminiLLM._build_messages()` — dựng danh sách message theo mode.

### `lm_studio.py`
Provider LM Studio (local) qua endpoint OpenAI-compatible; retry tối thiểu (`_MAX_RETRIES=1`), dùng cho tool-calling/agent nội bộ.
- `LMStudioLLM.generate()` — gọi model local sinh câu trả lời.
- `LMStudioLLM.generate_stream()` — sinh theo luồng từ model local.
- `LMStudioLLM._build_messages()` — dựng message theo mode.

### `chat_model.py`
Shim tương thích ngược: re-export `GeminiLLM` dưới tên `ChatModel`.

### `prompts.py`
Chứa toàn bộ system prompt (RAG, chitchat, self-eval, reformat tài liệu) và các helper dựng message kiểu OpenAI; nhúng bảng thuật ngữ HUST và strip Markdown link khỏi lịch sử.
- `build_rag_messages()` — dựng message RAG kèm ngữ cảnh và lịch sử.
- `build_chitchat_messages()` — dựng message trò chuyện thường.
- `build_self_eval_messages()` — dựng message cho bước tự đánh giá.
- `build_reformat_messages()` — dựng message chuẩn hoá cấu trúc Markdown khi ingest.
- `_strip_markdown_links()` — chỉ giữ nhãn hiển thị của Markdown link trong lịch sử.

### `self_eval.py`
Dùng một LLM làm giám khảo chấm chất lượng câu trả lời (relevance/faithfulness/completeness) và quyết định pass/fail cùng nhu cầu web-search.
- `SelfEvaluator.evaluate()` — chấm câu trả lời theo query + context, trả dict kết quả.
- `SelfEvaluator._parse_evaluation()` — parse JSON đánh giá, fallback về kết quả fail khi lỗi.
- `SelfEvaluator._strip_markdown_fences()` — bỏ code fence bọc quanh JSON.

### `__init__.py`
Khai báo registry provider (`register_llm`, `create_llm`) để lazy-import và khởi tạo LLM theo `Settings`, đồng thời export `BaseLLM`, `ChatModel`, `SelfEvaluator`.
- `register_llm()` — decorator đăng ký class provider theo tên.
- `create_llm()` — lazy-import và tạo instance provider được cấu hình.
