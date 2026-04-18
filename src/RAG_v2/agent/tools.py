from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


COLLECTION_DESCRIPTIONS: dict[str, str] = {
    "quy_dinh": "quy dinh hoc vu, hoc bong, mien giam hoc phi, ky luat, dieu kien tot nghiep",
    "chuong_trinh": "chuong trinh dao tao, danh sach mon hoc, so tin chi, mon tien quyet, bat buoc va tu chon",
    "ke_hoach": "lich thi, lich hoc ky, ke hoach nam hoc, tuan hoc, ngay nghi le",
    "thong_bao": "thong bao moi, tin tuc nha truong, su kien sap dien ra",
}


def _collection_description_text() -> str:
    return "; ".join(
        f"{name}: {description}" for name, description in COLLECTION_DESCRIPTIONS.items()
    )


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Tim kiem thong tin trong mot collection cu the cua co so du lieu truong. "
                "Dung khi cau hoi ro rang thuoc ve mot linh vuc duy nhat. "
                f"Collections: {_collection_description_text()}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cau truy van tim kiem, viet lai ngan gon va cu the",
                    },
                    "collection": {
                        "type": "string",
                        "enum": list(COLLECTION_DESCRIPTIONS.keys()),
                        "description": "Ten collection can tim kiem",
                    },
                },
                "required": ["query", "collection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multi_rag_search",
            "description": (
                "Tim kiem dong thoi nhieu collection de tra loi cau hoi tong hop. "
                "Dung khi cau hoi can thong tin tu nhieu nguon."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "description": "Danh sach query, moi query tim tren mot collection",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "collection": {
                                    "type": "string",
                                    "enum": list(COLLECTION_DESCRIPTIONS.keys()),
                                },
                            },
                            "required": ["query", "collection"],
                        },
                        "minItems": 2,
                        "maxItems": 4,
                    },
                },
                "required": ["queries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_cohorts",
            "description": (
                "So sanh quy dinh hoac chuong trinh dao tao giua hai khoa sinh vien. "
                "Dung khi cau hoi de cap den 2 khoa khac nhau (K65, K66, K70...)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Chu de can so sanh, vi du: hoc bong KKHT",
                    },
                    "cohort_a": {
                        "type": "string",
                        "description": "Khoa thu nhat, vi du: K65",
                    },
                    "cohort_b": {
                        "type": "string",
                        "description": "Khoa thu hai, vi du: K70",
                    },
                    "collection": {
                        "type": "string",
                        "enum": ["quy_dinh", "chuong_trinh"],
                        "description": "Collection chua thong tin can so sanh",
                    },
                },
                "required": ["topic", "cohort_a", "cohort_b", "collection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Tim kiem thong tin moi nhat tren internet qua Tavily. "
                "Chi dung khi thong tin co the chua co trong database hoac rag_search khong co ket qua."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cau truy van web, nen kem ten truong de chinh xac",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clarify_question",
            "description": (
                "Hoi lai nguoi dung khi cau hoi mo ho khong the tim kiem duoc. "
                "Nen dung toi da 1 lan trong mot luot hoi dap."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Cau hoi lam ro, ngan gon",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-3 lua chon goi y",
                        "maxItems": 3,
                    },
                },
                "required": ["message", "options"],
            },
        },
    },
]

TOOL_NAMES: list[str] = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]


@dataclass(frozen=True)
class AgentTool:
    """Metadata wrapper for one declared function-calling tool."""

    name: str
    declaration: dict[str, Any]


class ToolRegistry:
    """Simple immutable-ish registry for tool declarations."""

    def __init__(self, declarations: list[dict[str, Any]] | None = None) -> None:
        payload = declarations or TOOL_DEFINITIONS
        self._by_name: dict[str, AgentTool] = {}
        for declaration in payload:
            fn = declaration.get("function", {})
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            self._by_name[name] = AgentTool(name=name, declaration=declaration)

    def names(self) -> list[str]:
        return list(self._by_name.keys())

    def as_openai_tools(self) -> list[dict[str, Any]]:
        return [tool.declaration for tool in self._by_name.values()]

    def get(self, name: str) -> AgentTool | None:
        return self._by_name.get(name)


def build_default_tool_declarations() -> list[dict[str, Any]]:
    """Return a detached copy-ready list for OpenAI-compatible tool calling."""
    return copy.deepcopy(TOOL_DEFINITIONS)