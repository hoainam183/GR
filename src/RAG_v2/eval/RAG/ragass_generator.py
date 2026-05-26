"""
ragass_generator.py — Tạo synthetic evaluation dataset theo chuẩn RAGAS.

Pipeline:
  1. Load chunks từ stsv + quydinh JSON files
  2. Embed + cluster (ClusterEngine) để tìm nhóm chunks liên quan
  3. LLM (Gemini) sinh 3 loại câu hỏi:
       - Single-chunk  (30%): 1 chunk → 1 câu hỏi cụ thể
       - Multi-chunk   (50%): 2-3 chunks cùng cluster → 1 câu hỏi tổng hợp
       - Adversarial   (20%): câu hỏi "bẫy" — không thể trả lời từ context
  4. Mỗi item có ground_truth_contexts = list[chunk_id] (key cho RAGAS eval)
  5. Lưu JSONL để ragass_evaluator.py consume

Chạy:
    python eval/RAG/ragass_generator.py
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import hashlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Tải file .env từ thư mục gốc RAG_v2
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from .cluster_engine import ClusterEngine

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — Sửa tại đây, không cần CLI args
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    # ── Dữ liệu đầu vào ──────────────────────────────────────────────────────
    "chunk_files": {
        "stsv": Path(__file__).parent.parent.parent / "data/stsv/chunks/stsv_all_chunks.json",
        "quydinh": Path(__file__).parent.parent.parent / "data/quydinh/chunks/quydinh_all_chunks.json",
    },

    # ── Output ────────────────────────────────────────────────────────────────
    "output_dir": Path(__file__).parent / "outputs",
    "output_file": "ragass_dataset.jsonl",  # append mode — chạy lại không mất data cũ

    # ── Dataset size ──────────────────────────────────────────────────────────
    "total_samples": 150,           # tổng số items mục tiêu
    "question_ratios": {
        "single":      0.30,        # 45 items
        "multi":       0.50,        # 75 items
        "adversarial": 0.20,        # 30 items
    },

    # ── Chunk filter ──────────────────────────────────────────────────────────
    "min_chunk_len": 100,           # bỏ chunk quá ngắn

    # ── Clustering ────────────────────────────────────────────────────────────
    "chunks_per_cluster": 5,        # ~5 chunks/cluster target
    "min_cluster_size": 2,          # cluster multi-chunk phải có >= 2 chunks
    "multi_group_max_size": 3,      # mỗi group multi-chunk tối đa 3 chunks

    # ── LLM (Gemini) ──────────────────────────────────────────────────────────
    "llm_backend": "gemini",
    "gemini_model": "gemini-3.1-flash-lite",   # nhanh + rẻ hơn Flash 1.5
    "gemini_api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
    "llm_delay_seconds": 30,        # delay giữa các lần gọi LLM (tránh RPM limit)
    "llm_max_tokens": 1200,

    # ── Seed ──────────────────────────────────────────────────────────────────
    "seed": 42,
}

# ─────────────────────────────────────────────────────────────────────────────
# Dataclass output
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RAGASSItem:
    """
    Một item trong RAGAS evaluation dataset.

    ground_truth_contexts là key quan trọng nhất:
      - Dùng để tính context_recall (RAG có retrieve đủ chunks này không?)
      - Dùng để tính context_precision (RAG có retrieve chunks không liên quan không?)
    """
    id: str
    question: str
    ground_truth: str                       # câu trả lời chuẩn
    ground_truth_contexts: List[str]        # list[chunk_id] — chunks cần thiết để trả lời
    ground_truth_context_texts: List[str]   # text tương ứng (để debug/inspect)
    question_type: str                      # "single" | "multi" | "adversarial"
    source: str                             # "stsv" | "quydinh"
    expected_collection: str
    answerable: bool
    expected_behavior: str
    difficulty: str = "medium"
    answer_type: str = "factoid"
    atomic_facts: List[str] = field(default_factory=list)
    expected_keywords: List[str] = field(default_factory=list)
    expected_citations: List[str] = field(default_factory=list)
    doc_type: str = ""
    document_title: str = ""
    chapter: str = ""
    article: str = ""
    clause: str = ""
    effective_date: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_ragas_dict(self) -> Dict:
        """Format cho RAGAS evaluate (contexts = ground_truth_context_texts)."""
        return {
            "id": self.id,
            "question": self.question,
            "ground_truth": self.ground_truth,
            "contexts": self.ground_truth_context_texts,
            "ground_truth_contexts": self.ground_truth_contexts,
            "question_type": self.question_type,
            "source": self.source,
            "expected_collection": self.expected_collection,
            "answerable": self.answerable,
            "expected_behavior": self.expected_behavior,
        }


def _full_context_id(source: str, chunk_id: Any) -> str:
    text = str(chunk_id or "").strip()
    if not text:
        return ""
    if "/" in text:
        return text
    return f"{source}/{text}" if source else text


def _stable_item_id(source: str, question_type: str, context_ids: List[str]) -> str:
    raw = "|".join([source, question_type, *context_ids])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{source}_{question_type}_{digest}"


def _metadata_value(metadata: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _extract_schema_metadata(chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    metadata = dict(chunks[0].get("metadata") or {}) if chunks else {}
    document_title = _metadata_value(
        metadata,
        "document_title",
        "doc_title",
        "title",
        "filename",
        "source_file",
    )
    doc_type = _metadata_value(metadata, "doc_type", "document_type") or document_title
    return {
        "doc_type": doc_type,
        "document_title": document_title,
        "chapter": _metadata_value(metadata, "chapter", "chapter_title"),
        "article": _metadata_value(metadata, "article", "article_title"),
        "clause": _metadata_value(metadata, "clause", "clause_number", "khoan"),
        "effective_date": _metadata_value(metadata, "effective_date", "date_str", "valid_as_of"),
    }


def _expected_citations(schema_meta: Dict[str, str]) -> List[str]:
    parts = [
        schema_meta.get("doc_type") or schema_meta.get("document_title"),
        schema_meta.get("article"),
    ]
    citation_parts = [str(part).strip() for part in parts if str(part or "").strip()]
    if schema_meta.get("clause"):
        citation_parts.append(f"Khoản {schema_meta['clause']}")
    return [" - ".join(citation_parts)] if citation_parts else []


def _extract_atomic_facts(answer: str, limit: int = 5) -> List[str]:
    text = " ".join(str(answer or "").split())
    facts: List[str] = []
    facts.extend(re.findall(r"https?://\S+", text))
    facts.extend(re.findall(r"\b\d+(?:[.,]\d+)?\s*(?:năm|tháng|tuần|ngày|tín chỉ|TC|%)\b", text, re.IGNORECASE))
    facts.extend(re.findall(r"\b[A-ZĐ]{2,}[A-ZĐ0-9-]*\b", text))

    stopwords = {
        "và", "của", "cho", "theo", "trong", "được", "không", "thông", "tin",
        "sinh", "viên", "học", "này", "các", "một", "với", "cần", "tại",
    }
    for token in re.findall(r"\b[\wÀ-ỹ-]{4,}\b", text):
        lowered = token.lower()
        if lowered not in stopwords and token not in facts:
            facts.append(token)
        if len(facts) >= limit:
            break

    deduped: List[str] = []
    for fact in facts:
        if fact and fact not in deduped:
            deduped.append(fact)
    return deduped[:limit]


def _make_item(
    *,
    question: str,
    ground_truth: str,
    chunks: List[Dict[str, Any]],
    question_type: str,
    source: str,
    answer_type: str,
    answerable: bool,
    expected_behavior: str,
    difficulty: str,
    metadata: Dict[str, Any],
) -> RAGASSItem:
    context_ids = [
        _full_context_id(str(chunk.get("source") or source), chunk["chunk_id"])
        for chunk in chunks
    ]
    schema_meta = _extract_schema_metadata(chunks)
    atomic_facts = _extract_atomic_facts(ground_truth)
    bare_context_ids = [str(chunk["chunk_id"]) for chunk in chunks]
    return RAGASSItem(
        id=_stable_item_id(source, question_type, context_ids),
        question=question,
        ground_truth=ground_truth,
        ground_truth_contexts=context_ids,
        ground_truth_context_texts=[chunk["content"] for chunk in chunks],
        question_type=question_type,
        source=source,
        expected_collection=source,
        answerable=answerable,
        expected_behavior=expected_behavior,
        difficulty=difficulty,
        answer_type=answer_type,
        atomic_facts=atomic_facts,
        expected_keywords=atomic_facts[:5],
        expected_citations=_expected_citations(schema_meta),
        metadata={**metadata, "bare_ground_truth_contexts": bare_context_ids},
        **schema_meta,
    )


# ─────────────────────────────────────────────────────────────────────────────
# LLM prompts
# ─────────────────────────────────────────────────────────────────────────────

_SINGLE_PROMPT = """\
Bạn là chuyên gia tạo dataset đánh giá hệ thống RAG cho trường Đại học Bách Khoa Hà Nội.

Dựa vào đoạn văn bản dưới đây, hãy tạo MỘT câu hỏi mà sinh viên thực tế có thể hỏi, \
và câu trả lời hoàn toàn dựa trên đoạn văn bản.

Yêu cầu:
- Câu hỏi tự nhiên như sinh viên thực sự viết (không cần thuật ngữ chính xác)
- Câu trả lời chỉ dựa vào nội dung đoạn văn, không thêm thông tin ngoài
- Đa dạng loại: factoid (hỏi thông tin cụ thể) hoặc procedural (hỏi quy trình)

ĐOẠN VĂN:
---
{context}
---

Trả về JSON thuần (không có markdown fence):
{{"question": "...", "answer": "...", "question_type": "factoid|procedural"}}"""

_MULTI_PROMPT = """\
Bạn là chuyên gia tạo dataset đánh giá hệ thống RAG cho trường Đại học Bách Khoa Hà Nội.

Dựa vào {n} đoạn văn bản dưới đây (từ các phần khác nhau của cùng chủ đề), \
hãy tạo MỘT câu hỏi mà sinh viên có thể hỏi và cần TỔ HỢP thông tin từ nhiều đoạn để trả lời đầy đủ.

Yêu cầu:
- Câu hỏi phải cần thông tin từ ÍT NHẤT 2 đoạn văn bản trên để trả lời hoàn chỉnh
- Câu hỏi tự nhiên như sinh viên thực sự viết
- Câu trả lời tổng hợp thông tin từ tất cả các đoạn liên quan

{contexts_block}

Trả về JSON thuần (không có markdown fence):
{{"question": "...", "answer": "...", "requires_chunks": [1, 2, ...]}}
(requires_chunks: danh sách số thứ tự đoạn văn [bắt đầu từ 1] cần để trả lời)"""

_ADVERSARIAL_PROMPT = """\
Bạn là chuyên gia tạo dataset đánh giá hệ thống RAG cho trường Đại học Bách Khoa Hà Nội.

Dựa vào đoạn văn bản dưới đây, hãy tạo MỘT câu hỏi liên quan đến chủ đề này \
nhưng KHÔNG THỂ trả lời được chỉ từ đoạn văn bản (thiếu thông tin, hoặc thông tin không có ở đây).

Mục đích: Test xem hệ thống RAG có biết "không biết" hay không.

Yêu cầu:
- Câu hỏi phải nghe có vẻ liên quan đến chủ đề
- Nhưng đoạn văn bản KHÔNG chứa đủ thông tin để trả lời chính xác
- Ground truth answer: giải thích ngắn gọn tại sao không thể trả lời từ context này

ĐOẠN VĂN:
---
{context}
---

Trả về JSON thuần (không có markdown fence):
{{"question": "...", "answer": "Không có đủ thông tin trong context để trả lời câu hỏi này. ...", "why_unanswerable": "..."}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Chunk loader (tùy chỉnh cho 2 file stsv + quydinh)
# ─────────────────────────────────────────────────────────────────────────────


def load_chunks(file_path: Path, source: str, min_len: int = 100) -> List[Dict]:
    """Load và normalize chunks từ JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        raw = json.load(f)

    chunks = []
    for item in raw:
        content = item.get("content", "").strip()
        if len(content) < min_len:
            continue
        chunk_id = item.get("chunk_id") or item.get("id") or f"row_{len(chunks):04d}"
        chunks.append({
            "chunk_id": chunk_id,
            "content": content,
            "source": source,
            "metadata": item.get("metadata", {}),
        })

    logger.info("Loaded %d valid chunks từ '%s' (min_len=%d)", len(chunks), file_path.name, min_len)
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# LLM caller
# ─────────────────────────────────────────────────────────────────────────────


class GeminiCaller:
    """Wrapper Gemini API với delay để tránh RPM limit."""

    def __init__(self, api_key: str, model: str, delay_seconds: float = 30.0) -> None:
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY chưa được set.\n"
                "  export GEMINI_API_KEY=your_key"
            )
        self.api_key = api_key
        self.model = model
        self.delay = delay_seconds
        self._client = None
        self._last_call_time: float = 0.0

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)  # type: ignore
            self._client = genai.GenerativeModel(self.model)  # type: ignore
        return self._client

    def generate(self, prompt: str, max_tokens: int = 1200) -> str:
        """Gọi Gemini với delay tự động."""
        # Đảm bảo delay giữa các lần gọi
        elapsed = time.time() - self._last_call_time
        if elapsed < self.delay and self._last_call_time > 0:
            wait = self.delay - elapsed
            logger.info("  ⏳ Waiting %.1fs (RPM throttle)...", wait)
            time.sleep(wait)

        client = self._get_client()
        self._last_call_time = time.time()

        try:
            response = client.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.2},
            )
            return response.text.strip()
        except Exception as e:
            logger.error("Gemini call failed: %s", e)
            raise


def _parse_json_response(raw: str) -> Optional[Dict]:
    """Parse JSON từ LLM response, xử lý markdown fence nếu có."""
    text = raw.strip()
    # Strip markdown fence
    if "```" in text:
        parts = text.split("```")
        for part in parts[1:]:
            cleaned = part.lstrip("json").strip()
            if cleaned:
                text = cleaned
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Thử extract JSON bằng regex
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        logger.warning("Không parse được JSON từ response: %s...", raw[:100])
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Question generators
# ─────────────────────────────────────────────────────────────────────────────


def generate_single(llm: GeminiCaller, chunk: Dict, max_tokens: int) -> Optional[RAGASSItem]:
    """Tạo Single-chunk question từ 1 chunk."""
    prompt = _SINGLE_PROMPT.format(context=chunk["content"][:2000])
    try:
        raw = llm.generate(prompt, max_tokens=max_tokens)
        parsed = _parse_json_response(raw)
        if not parsed or not parsed.get("question") or not parsed.get("answer"):
            return None
        source = chunk.get("source", "unknown")
        return _make_item(
            question=parsed["question"],
            ground_truth=parsed["answer"],
            chunks=[chunk],
            question_type="single",
            source=source,
            answer_type=parsed.get("question_type", "factoid"),
            answerable=True,
            expected_behavior="answer_with_citation",
            difficulty="easy",
            metadata={"chunk_id": chunk["chunk_id"], "q_type_detail": parsed.get("question_type", "factoid")},
        )
    except Exception as e:
        logger.warning("generate_single failed: %s", e)
        return None


def generate_multi(llm: GeminiCaller, group: List[Dict], max_tokens: int) -> Optional[RAGASSItem]:
    """Tạo Multi-chunk question từ 2-3 chunks cùng cluster."""
    contexts_block = "\n\n".join(
        f"[Đoạn {i+1}]\n{c['content'][:1000]}"
        for i, c in enumerate(group)
    )
    prompt = _MULTI_PROMPT.format(n=len(group), contexts_block=contexts_block)
    try:
        raw = llm.generate(prompt, max_tokens=max_tokens)
        parsed = _parse_json_response(raw)
        if not parsed or not parsed.get("question") or not parsed.get("answer"):
            return None

        # Xác định chunks thực sự cần (từ requires_chunks nếu có)
        req = parsed.get("requires_chunks", list(range(1, len(group) + 1)))
        req_indices = [int(r) - 1 for r in req if 1 <= int(r) <= len(group)]
        if not req_indices:
            req_indices = list(range(len(group)))

        needed_chunks = [group[i] for i in req_indices]
        source = group[0].get("source", "unknown")
        return _make_item(
            question=parsed["question"],
            ground_truth=parsed["answer"],
            chunks=needed_chunks,
            question_type="multi",
            source=source,
            answer_type="comparison" if "so sánh" in parsed["question"].lower() else "procedural",
            answerable=True,
            expected_behavior="answer_with_citation",
            difficulty="hard" if len(needed_chunks) >= 3 else "medium",
            metadata={
                "all_chunk_ids": [c["chunk_id"] for c in group],
                "required_chunk_ids": [c["chunk_id"] for c in needed_chunks],
            },
        )
    except Exception as e:
        logger.warning("generate_multi failed: %s", e)
        return None


def generate_adversarial(llm: GeminiCaller, chunk: Dict, max_tokens: int) -> Optional[RAGASSItem]:
    """Tạo Adversarial question — câu hỏi không trả lời được từ chunk này."""
    prompt = _ADVERSARIAL_PROMPT.format(context=chunk["content"][:2000])
    try:
        raw = llm.generate(prompt, max_tokens=max_tokens)
        parsed = _parse_json_response(raw)
        if not parsed or not parsed.get("question") or not parsed.get("answer"):
            return None
        source = chunk.get("source", "unknown")
        return _make_item(
            question=parsed["question"],
            ground_truth=parsed["answer"],
            chunks=[chunk],   # chunk liên quan nhưng không đủ
            question_type="adversarial",
            source=source,
            answer_type="refusal",
            answerable=False,
            expected_behavior="refuse_insufficient_context",
            difficulty="hard",
            metadata={
                "chunk_id": chunk["chunk_id"],
                "why_unanswerable": parsed.get("why_unanswerable", ""),
            },
        )
    except Exception as e:
        logger.warning("generate_adversarial failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────


def run(config: Dict = CONFIG) -> Path:
    """
    Chạy toàn bộ pipeline generate và lưu JSONL.

    Returns:
        Path tới output file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    rng = random.Random(config["seed"])

    # ── 1. Load chunks ────────────────────────────────────────────────────────
    all_chunks: List[Dict] = []
    for source, file_path in config["chunk_files"].items():
        chunks = load_chunks(file_path, source=source, min_len=config["min_chunk_len"])
        all_chunks.extend(chunks)

    logger.info("Tổng: %d chunks từ %d nguồn", len(all_chunks), len(config["chunk_files"]))

    # ── 2. Cluster ────────────────────────────────────────────────────────────
    logger.info("\n🔗 Clustering chunks...")
    engine = ClusterEngine(
        chunks_per_cluster=config["chunks_per_cluster"],
        min_cluster_size=config["min_cluster_size"],
    )
    engine.fit(all_chunks)
    logger.info("Cluster stats: %s", engine.stats())

    multi_groups = engine.get_multi_chunk_groups(
        min_size=2,
        max_size=config["multi_group_max_size"],
    )
    rng.shuffle(multi_groups)

    # ── 3. Phân bổ số lượng ───────────────────────────────────────────────────
    total = config["total_samples"]
    ratios = config["question_ratios"]
    n_single = int(total * ratios["single"])
    n_multi  = int(total * ratios["multi"])
    n_adv    = total - n_single - n_multi   # phần còn lại

    logger.info(
        "\n📊 Mục tiêu: %d total (%d single | %d multi | %d adversarial)",
        total, n_single, n_multi, n_adv,
    )

    # Shuffle pool chunks
    shuffled_chunks = list(all_chunks)
    rng.shuffle(shuffled_chunks)

    # ── 4. Init LLM ───────────────────────────────────────────────────────────
    llm = GeminiCaller(
        api_key=config["gemini_api_key"],
        model=config["gemini_model"],
        delay_seconds=config["llm_delay_seconds"],
    )

    # ── 5. Generate ───────────────────────────────────────────────────────────
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / config["output_file"]

    total_generated = 0
    type_counts = {"single": 0, "multi": 0, "adversarial": 0}

    with open(output_path, "w", encoding="utf-8") as fout:

        # --- Single-chunk ---
        logger.info("\n[1/3] Generating SINGLE-CHUNK questions...")
        chunk_pool = iter(shuffled_chunks)
        while type_counts["single"] < n_single:
            try:
                chunk = next(chunk_pool)
            except StopIteration:
                logger.warning("Hết chunks cho single-chunk, dừng ở %d/%d", type_counts["single"], n_single)
                break

            logger.info(
                "  single [%d/%d] chunk=%s source=%s",
                type_counts["single"] + 1, n_single, chunk["chunk_id"][:8], chunk["source"],
            )
            item = generate_single(llm, chunk, config["llm_max_tokens"])
            if item:
                fout.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
                fout.flush()
                type_counts["single"] += 1
                total_generated += 1

        # --- Multi-chunk ---
        logger.info("\n[2/3] Generating MULTI-CHUNK questions...")
        group_pool = iter(multi_groups)
        while type_counts["multi"] < n_multi:
            try:
                group = next(group_pool)
            except StopIteration:
                logger.warning("Hết multi-chunk groups, dừng ở %d/%d", type_counts["multi"], n_multi)
                break

            logger.info(
                "  multi [%d/%d] group_size=%d source=%s",
                type_counts["multi"] + 1, n_multi, len(group), group[0]["source"],
            )
            item = generate_multi(llm, group, config["llm_max_tokens"])
            if item:
                fout.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
                fout.flush()
                type_counts["multi"] += 1
                total_generated += 1

        # --- Adversarial ---
        logger.info("\n[3/3] Generating ADVERSARIAL questions...")
        adv_pool = iter(rng.sample(shuffled_chunks, min(n_adv * 3, len(shuffled_chunks))))
        while type_counts["adversarial"] < n_adv:
            try:
                chunk = next(adv_pool)
            except StopIteration:
                logger.warning("Hết chunks cho adversarial, dừng ở %d/%d", type_counts["adversarial"], n_adv)
                break

            logger.info(
                "  adversarial [%d/%d] chunk=%s source=%s",
                type_counts["adversarial"] + 1, n_adv, chunk["chunk_id"][:8], chunk["source"],
            )
            item = generate_adversarial(llm, chunk, config["llm_max_tokens"])
            if item:
                fout.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
                fout.flush()
                type_counts["adversarial"] += 1
                total_generated += 1

    logger.info(
        "\n✅ Done! %d items → %s\n   single=%d | multi=%d | adversarial=%d",
        total_generated, output_path,
        type_counts["single"], type_counts["multi"], type_counts["adversarial"],
    )
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run()
