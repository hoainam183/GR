from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .tool_adapters import execute_tool

logger = logging.getLogger(__name__)

# ─── Collection type aliases ──────────────────────────────────────────────────

CollectionName = Literal["quy_dinh", "chuong_trinh", "ke_hoach", "ho_tro_sv"]
CurriculumCollection = Literal["quy_dinh", "chuong_trinh"]

# ─── Pydantic input schemas ───────────────────────────────────────────────────


class RagSearchInput(BaseModel):
    query: str = Field(description="Cau truy van tim kiem, viet ngan gon va cu the")
    collection: CollectionName = Field(description="Collection can tim kiem")


class QueryItem(BaseModel):
    query: str
    collection: CollectionName


class MultiRagSearchInput(BaseModel):
    queries: list[QueryItem] = Field(
        min_length=2,
        max_length=4,
        description="Danh sach query, moi query 1 collection",
    )


class CompareCohortsInput(BaseModel):
    """So sánh giữa 2 **khóa** sinh viên (K65, K70, …). Không dùng cho mã ngành."""
    topic: str = Field(description="Chủ đề so sánh, ví dụ: học bổng KKHT, điều kiện tốt nghiệp")
    cohort_a: str = Field(description="Mã khóa thứ nhất, ví dụ: K65")
    cohort_b: str = Field(description="Mã khóa thứ hai, ví dụ: K70")
    collection: CurriculumCollection = Field(description="Collection chứa thông tin cần so sánh")


class CompareProgramsInput(BaseModel):
    """So sánh chương trình / môn học giữa 2 **mã ngành** (IT-E6, IT-E7, …). Không dùng cho mã khóa."""
    topic: str = Field(description="Chủ đề so sánh tổng quát, ví dụ: cấu trúc chương trình, môn bắt buộc")
    major_a: str = Field(description="Mã ngành thứ nhất, ví dụ: IT-E7")
    major_b: str = Field(description="Mã ngành thứ hai, ví dụ: IT-E6")
    collection: CurriculumCollection = Field(description="Thường là chuong_trinh; dùng quy_dinh khi so sánh quy định áp dụng theo ngành")
    course_keyword: str | None = Field(
        default=None,
        description="(Khuyến dùng khi so sánh 1 môn cụ thể) Tên hoặc mã môn, ví dụ: Lập trình mạng, IT3100",
    )


class WebSearchInput(BaseModel):
    query: str = Field(description="Cau truy van web, kem ten truong de chinh xac hon")


class ClarifyInput(BaseModel):
    message: str = Field(description="Cau hoi lam ro, ngan gon")
    options: list[str] = Field(max_length=3, description="2-3 lua chon goi y")


# ─── Adapter functions ────────────────────────────────────────────────────────
# Bridge between LangChain's Pydantic-validated calling convention and the
# execute_tool dispatcher that the rest of the codebase uses.


def _rag_search(query: str, collection: str) -> str:
    logger.debug("[lc_tools] rag_search collection=%s query='%s'", collection, query[:60])
    return execute_tool("rag_search", {"query": query, "collection": collection})


def _multi_rag_search(queries: list[Any]) -> str:
    """Accept both Pydantic QueryItem objects and plain dicts."""
    queries_dicts: list[dict[str, str]] = []
    for item in queries:
        if hasattr(item, "model_dump"):
            queries_dicts.append(item.model_dump())
        elif hasattr(item, "dict"):
            queries_dicts.append(item.dict())
        elif isinstance(item, dict):
            queries_dicts.append({"query": str(item.get("query", "")), "collection": str(item.get("collection", ""))})
        else:
            logger.warning("[lc_tools] Unexpected query item type: %s", type(item))
            continue
    logger.debug("[lc_tools] multi_rag_search %d queries", len(queries_dicts))
    return execute_tool("multi_rag_search", {"queries": queries_dicts})


def _compare_cohorts(topic: str, cohort_a: str, cohort_b: str, collection: str) -> str:
    """Adapter cho compare_cohorts (khóa Kxx)."""
    return execute_tool(
        "compare_cohorts",
        {"topic": topic, "cohort_a": cohort_a, "cohort_b": cohort_b, "collection": collection},
    )


def _compare_programs(
    topic: str,
    major_a: str,
    major_b: str,
    collection: str,
    course_keyword: str | None = None,
) -> str:
    """Adapter cho compare_programs (mã ngành)."""
    return execute_tool(
        "compare_programs",
        {
            "topic": topic,
            "major_a": major_a,
            "major_b": major_b,
            "collection": collection,
            "course_keyword": course_keyword,
        },
    )


def _web_search(query: str) -> str:
    logger.debug("[lc_tools] web_search query='%s'", query[:60])
    return execute_tool("web_search", {"query": query})


def _clarify_question(message: str, options: list[str]) -> str:
    logger.debug("[lc_tools] clarify_question message='%s'", message[:60])
    return execute_tool("clarify_question", {"message": message, "options": options})


# ─── LangChain StructuredTools ────────────────────────────────────────────────
# Phase 3 cleanup: compare_cohorts, compare_programs, and multi_rag_search
# removed from agent tool list — now handled by planner-executor path.
# Adapter functions above are kept for backward compatibility / fallback.

LANGGRAPH_TOOLS: list[StructuredTool] = [
    StructuredTool.from_function(
        func=_rag_search,
        name="rag_search",
        description=(
            "Tìm kiếm thông tin trong database trường. Chọn đúng collection:\n"
            "- quy_dinh: quy định học vụ, học bổng, điều kiện tốt nghiệp, kỷ luật, ngoại ngữ;\n"
            "- chuong_trinh: môn học, tín chỉ, chương trình đào tạo, môn tiên quyết;\n"
            "- ke_hoach: lịch đăng ký học phần, lịch thi, deadline, kế hoạch học kỳ;\n"
            "- ho_tro_sv: biểu mẫu, giấy tờ thủ tục, thuê nhà, tìm việc thực tập, hỗ trợ sinh viên."
        ),
        args_schema=RagSearchInput,
    ),
    StructuredTool.from_function(
        func=_web_search,
        name="web_search",
        description=(
            "Tìm thông tin HUST mới nhất từ web qua Tavily, giới hạn vào "
            "hust.edu.vn và nguồn giáo dục chính thống. Dùng khi câu hỏi có "
            "deadline, lịch thi, đăng ký học phần, thông báo mới, năm học/học kỳ "
            "cụ thể, hoặc khi rag_search không có kết quả liên quan. Không dùng "
            "cho câu hỏi khái niệm, quy trình ổn định, hoặc thông tin đã có trong "
            "database nội bộ."
        ),
        args_schema=WebSearchInput,
    ),
    StructuredTool.from_function(
        func=_clarify_question,
        name="clarify_question",
        description=(
            "Hỏi lại người dùng khi câu hỏi quá mơ hồ không thể tìm kiếm. "
            "Tối đa 1 lần trong cuộc hội thoại."
        ),
        args_schema=ClarifyInput,
    ),
]

# Fast name → tool lookup used by _tools_node
TOOL_MAP: dict[str, StructuredTool] = {tool.name: tool for tool in LANGGRAPH_TOOLS}
