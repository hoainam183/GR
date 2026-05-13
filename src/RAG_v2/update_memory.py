import json
import os
import shutil

ROOT_MEM = "/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/PROJECT_MEMORY.md"
AGENT_MEM = "/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/.agent/PROJECT_MEMORY.md"

with open(ROOT_MEM, "r") as f:
    content = f.read()

new_sections = """

---

## 13. Mobile App (React Native)
- Đang phát triển kiến trúc Mobile App dùng React Native / Expo.
- Có monorepo structure share TypeScript types giữa Web và Mobile.
- Dùng Server-Sent Events (SSE) tương thích với React Native để stream chat.
- Xác thực bằng `expo-secure-store`.

---

## 14. Known Bugs & Kiến trúc cần chú ý (Cập nhật liên tục)
- **`query_agent` blocking async loop**: Hàm `query_agent` trong `rag_pipeline.py` gọi `agent.run()` đồng bộ. Cần offload sang thread (ví dụ: `asyncio.to_thread`) nếu gọi trong FastAPI async route để không block event loop.
- **Mất `user_context` trong luồng Agent**: `query_agent` nhận `user_context` nhưng KHÔNG truyền xuống `self.agent.run(...)`. Điều này làm luồng agent không có thông tin user.
- **`validity_filter` không được dùng trong Agent tool**: Hàm `_rag_search` trong `tool_adapters.py` chỉ gọi `searcher` và `reranker`, KHÔNG gọi `validity_filter` (bộ lọc này hiện chỉ được dùng trong `rag_flow` cơ bản).
- **Qwen 8B lờ đi negative constraints**: Các rule phức tạp ("KHÔNG dùng ke_hoach cho môn học kỳ mấy") dễ bị Qwen 8B lờ đi do semantic của từ "học kỳ" quá gần với "kế hoạch". Cần thiết kế prompt cực kỳ cẩn thận hoặc dùng model lớn hơn.
"""

if "## 13. Mobile App (React Native)" not in content:
    content += new_sections

with open(AGENT_MEM, "w") as f:
    f.write(content)

with open(ROOT_MEM, "w") as f:
    f.write(content)

# Create KI
KI_DIR = "/Users/nam.nguyen/.gemini/antigravity/knowledge/update_project_memory"
os.makedirs(os.path.join(KI_DIR, "artifacts"), exist_ok=True)

metadata = {
    "title": "Always Update PROJECT_MEMORY.md after changes",
    "summary": "Mỗi khi có code mới, thay đổi kiến trúc, hoặc phát hiện bug/cạm bẫy mới, BẮT BUỘC phải cập nhật file .agent/PROJECT_MEMORY.md để giữ context luôn mới nhất cho các agent sau.",
    "timestamp": "2026-05-01T12:20:00Z",
    "references": ["/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/.agent/PROJECT_MEMORY.md"]
}

with open(os.path.join(KI_DIR, "metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

rule_content = """# Rule: Update Project Memory

Mỗi khi bạn thực hiện các thay đổi sau trong dự án:
- Thêm module, thư mục mới (ví dụ: mobile, frontend).
- Thay đổi schema của request/response.
- Thêm collection mới hoặc thay đổi metadata filters.
- Thêm Agent Tools.
- Khám phá ra một "cạm bẫy" (gotcha) hoặc bug kiến trúc mới.

**BẠN BẮT BUỘC PHẢI:**
Mở file `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/.agent/PROJECT_MEMORY.md` và `/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2/PROJECT_MEMORY.md`, cập nhật nội dung tương ứng.

File này là bộ nhớ sống của toàn bộ kiến trúc dự án. Nếu không cập nhật, các agent sau sẽ làm việc với context cũ và gây ra lỗi.
"""

with open(os.path.join(KI_DIR, "artifacts/rule.md"), "w") as f:
    f.write(rule_content)

print("Memory files updated and KI created successfully.")
