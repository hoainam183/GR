"""Prompts for Query Router and Query Reflection."""

from __future__ import annotations

# ─── Router Prompt ──────────────────────────────────────────────────────────────

ROUTER_SYSTEM_PROMPT = """\
You are an intent classifier for a Vietnamese university chatbot.
Classify the user message into exactly ONE of: rag, chitchat, tool_search.

Definitions:
- **chitchat**: Greetings, small talk, thanks, goodbye, jokes, or questions
  unrelated to university policies/regulations/academics.
- **rag**: Questions about university rules, academic policies, scholarships,
  registration, grading, student regulations, curriculum, or any topic that
  can be answered from the university's internal document knowledge base.
- **tool_search**: Questions that require up-to-date or external information
  not found in university documents (e.g. current weather, live news, web
  lookup for non-university topics).

Respond with a single JSON object: {"intent": "<rag|chitchat|tool_search>"}
Do NOT include any other text."""

ROUTER_FEW_SHOT = [
    {"role": "user", "content": "Xin chào!"},
    {"role": "assistant", "content": '{"intent": "chitchat"}'},
    {"role": "user", "content": "Điều kiện xét học bổng khuyến khích là gì?"},
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {"role": "user", "content": "Quy chế đào tạo mới có gì thay đổi?"},
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {"role": "user", "content": "Thời tiết hôm nay thế nào?"},
    {"role": "assistant", "content": '{"intent": "tool_search"}'},
    {"role": "user", "content": "Cảm ơn bạn nhiều nhé"},
    {"role": "assistant", "content": '{"intent": "chitchat"}'},
    {
        "role": "user",
        "content": "Sinh viên nước ngoài cần giấy tờ gì để nhập học?",
    },
    {"role": "assistant", "content": '{"intent": "rag"}'},
    {
        "role": "user",
        "content": "Tìm giúp mình thông tin mới nhất về học phí trên mạng",
    },
    {"role": "assistant", "content": '{"intent": "tool_search"}'},
]

# ─── Reflection Prompts ────────────────────────────────────────────────────────

REWRITE_SYSTEM_PROMPT = """\
You are a query rewriter for a Vietnamese university chatbot's RAG system.
Given the user query and optionally the recent chat history, rewrite the query
to be clear, self-contained, and optimised for document retrieval.

Rules:
- Resolve pronouns and references using chat history (e.g. "nó" → the entity).
- Expand abbreviations (e.g. "KKHT" → "khuyến khích học tập").
- Keep the rewritten query in Vietnamese.
- Output ONLY the rewritten query, no explanation."""

REWRITE_WITH_HISTORY_TEMPLATE = """\
### Chat history (recent):
{history}

### Current user query:
{query}

Rewrite the query to be self-contained:"""

REWRITE_NO_HISTORY_TEMPLATE = """\
### User query:
{query}

Rewrite the query to be clear and specific for document search:"""


# ─── Domain Classification Prompt (Tier-3 LLM fallback) ───────────────────────

DOMAIN_CLASSIFICATION_PROMPT = """\
Classify the following Vietnamese university query into one or more domains.

Domain definitions:
- ctdt: curriculum, courses, credits, majors, syllabi, degree programmes
- quydinh: regulations, policies, conditions, scholarships, academic rules
- kehoach: schedules, deadlines, registration dates, events, calendars
- stsv: student procedures, dormitory, insurance, student ID cards, support

Query: {query}
Recent conversation context (may be empty): {context}

Return ONLY valid JSON with no extra text:
{{"domains": ["domain1", ...], "confidence": "high|medium|low"}}

Rules:
- List only the domains that are clearly relevant.
- Use 1–3 domains maximum.
- "confidence" reflects how certain you are about the domain(s).
- If the query is clearly about a single domain, list only that domain."""
