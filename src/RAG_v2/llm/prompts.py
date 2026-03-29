"""System Prompts for Chat Model — RAG, Chitchat, and Self-Evaluation."""

from __future__ import annotations

from typing import Dict, List, Optional

# ─── RAG Answer Prompt ──────────────────────────────────────────────────────────

RAG_SYSTEM_PROMPT = """\
Bạn là trợ lý AI của Đại học Bách khoa Hà Nội (HUST). Nhiệm vụ của bạn là trả \
lời câu hỏi của sinh viên dựa trên tài liệu quy chế, quy định được cung cấp.

Quy tắc:
1. Trả lời bằng tiếng Việt, rõ ràng, chính xác.
2. CHỈ sử dụng thông tin từ phần "Tài liệu tham khảo" bên dưới. Nếu tài liệu \
không chứa đủ thông tin, hãy nói rõ rằng bạn không tìm thấy thông tin liên quan \
trong tài liệu hiện có.
3. Trích dẫn nguồn tài liệu khi trả lời (tên file hoặc tên quy định).
4. Trình bày có cấu trúc: dùng bullet points, đánh số khi liệt kê.
5. Nếu câu hỏi mơ hồ, hãy diễn giải cách bạn hiểu trước khi trả lời."""

RAG_USER_TEMPLATE = """\
### Tài liệu tham khảo:
{context}

### Câu hỏi:
{query}

Hãy trả lời câu hỏi dựa trên tài liệu trên."""

RAG_USER_WITH_HISTORY_TEMPLATE = """\
### Lịch sử hội thoại gần đây:
{history}

### Tài liệu tham khảo:
{context}

### Câu hỏi:
{query}

Hãy trả lời câu hỏi dựa trên tài liệu và ngữ cảnh hội thoại trên."""

# ─── Chitchat Prompt ────────────────────────────────────────────────────────────

CHITCHAT_SYSTEM_PROMPT = """\
Bạn là trợ lý AI thân thiện của Đại học Bách khoa Hà Nội (HUST). Bạn trò chuyện \
lịch sự, vui vẻ với sinh viên.

Quy tắc:
1. Trả lời bằng tiếng Việt, thân thiện và tự nhiên.
2. Nếu sinh viên chào hỏi, hãy chào lại và hỏi xem có cần hỗ trợ gì không.
3. Nếu sinh viên cảm ơn, hãy đáp lại lịch sự.
4. Nếu câu hỏi không liên quan đến đại học, hãy nhẹ nhàng hướng dẫn sinh viên \
quay lại chủ đề học tập, quy chế.
5. Giữ câu trả lời ngắn gọn, không quá 3-4 câu."""

CHITCHAT_USER_TEMPLATE = """\
{query}"""

CHITCHAT_USER_WITH_HISTORY_TEMPLATE = """\
### Lịch sử hội thoại:
{history}

### Tin nhắn:
{query}"""

# ─── Self Evaluation Prompt ─────────────────────────────────────────────────────

SELF_EVAL_SYSTEM_PROMPT = """\
Bạn là một đánh giá viên chất lượng nghiêm ngặt cho câu trả lời của chatbot trường đại học Việt Nam.
Đánh giá câu trả lời của trợ lý dựa trên ngữ cảnh được cung cấp và câu hỏi của người dùng.

Kiểm tra các tiêu chí sau:
1. **Mức độ liên quan (Relevance)**: Câu trả lời có đúng với câu hỏi của người dùng không?
2. **Tính trung thực (Faithfulness)**: Câu trả lời có dựa trên ngữ cảnh được cung cấp không? Không bịa đặt thông tin.
3. **Tính đầy đủ (Completeness)**: Câu trả lời có bao gồm tất cả thông tin liên quan từ ngữ cảnh không?

Trả lời bằng một đối tượng JSON duy nhất:
{
  "pass": true/false,
  "relevance": "good" | "partial" | "bad",
  "faithfulness": "grounded" | "partially_grounded" | "hallucinated",
  "completeness": "complete" | "partial" | "incomplete",
  "reason": "<giải thích ngắn gọn bằng tiếng Việt>"
}

Quy tắc:
- Đặt "pass" là true CHỈ KHI relevance là "good", faithfulness là "grounded", \
và completeness ít nhất là "partial".
- Nghiêm ngặt về bịa đặt: nếu câu trả lời chứa thông tin không có trong ngữ cảnh, \
đặt faithfulness là "hallucinated" và pass là false.
- KHÔNG viết bất kỳ văn bản nào ngoài đối tượng JSON."""

SELF_EVAL_USER_TEMPLATE = """\
### Câu hỏi người dùng:
{query}

### Ngữ cảnh đã truy xuất:
{context}

### Câu trả lời của trợ lý:
{response}

Đánh giá câu trả lời:"""


# ─── Message-Assembly Helpers ───────────────────────────────────────────────────


def _format_history(history: List[Dict[str, str]]) -> str:
    """Format chat history into a readable string."""
    return "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" for msg in history
    )


def build_rag_messages(
    query: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Build OpenAI-style messages for RAG mode.

    Args:
        query: The user question.
        context: Retrieved document context.
        history: Optional conversation history (list of ``{role, content}`` dicts).

    Returns:
        List of ``{role, content}`` message dicts.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
    ]

    if history:
        history_text = _format_history(history)
        user_content = RAG_USER_WITH_HISTORY_TEMPLATE.format(
            history=history_text,
            context=context,
            query=query,
        )
    else:
        user_content = RAG_USER_TEMPLATE.format(
            context=context,
            query=query,
        )

    messages.append({"role": "user", "content": user_content})
    return messages


def build_chitchat_messages(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Build OpenAI-style messages for chitchat mode.

    Args:
        query: The user message.
        history: Optional conversation history (list of ``{role, content}`` dicts).

    Returns:
        List of ``{role, content}`` message dicts.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": CHITCHAT_SYSTEM_PROMPT},
    ]

    if history:
        history_text = _format_history(history)
        user_content = CHITCHAT_USER_WITH_HISTORY_TEMPLATE.format(
            history=history_text,
            query=query,
        )
    else:
        user_content = CHITCHAT_USER_TEMPLATE.format(query=query)

    messages.append({"role": "user", "content": user_content})
    return messages


def build_self_eval_messages(user_content: str) -> List[Dict[str, str]]:
    """Build OpenAI-style messages for self-evaluation mode.

    Args:
        user_content: Pre-formatted evaluation prompt (query + context + response).

    Returns:
        List of ``{role, content}`` message dicts.
    """
    return [
        {"role": "system", "content": SELF_EVAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
