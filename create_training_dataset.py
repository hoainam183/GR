"""
Tạo tập training dataset từ dữ liệu hội thoại sinh viên - giáo viên (data2.csv).

Output:
  - train_qa_pairs.jsonl        : Cặp question-answer đơn lẻ
  - train_conversations.jsonl   : Hội thoại nhiều lượt (OpenAI chat format)
  - train_instruction.jsonl     : Instruction-following format (Alpaca style)
  - training_stats.json         : Thống kê dataset
"""

import json
import re
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
INPUT_PATH = Path(r"d:\GR\src\clean_data\data2.csv")
OUTPUT_DIR = Path(r"d:\GR\training_data")
OUTPUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "Bạn là trợ lý tư vấn học tập của Trường Đại học Bách khoa Hà Nội (HUST). "
    "Hãy trả lời câu hỏi của sinh viên một cách chính xác, lịch sự và hữu ích "
    "dựa trên quy chế đào tạo và các quy định hiện hành của trường."
)


# ── Cleaning functions ─────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """Chuẩn hóa cơ bản: khoảng trắng, xuống dòng."""
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Loại nhiều dòng trống liên tiếp
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Loại khoảng trắng thừa ở đầu/cuối mỗi dòng
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def remove_email_metadata(text: str) -> str:
    """Loại bỏ phần trích dẫn email (On ... wrote:, >..., forwarded)."""
    # Cắt từ dòng "On ... wrote" trở đi (trả lời email)
    text = re.sub(
        r"\n*On\s+.{10,80}\s+wrote:?\s*$",
        "",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    # Cắt dòng bắt đầu bằng ">" (trích dẫn email)
    text = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)
    # Loại "---------- Forwarded message ----------"
    text = re.sub(
        r"-{3,}\s*Forwarded message\s*-{3,}.*", "", text, flags=re.DOTALL
    )
    return text.strip()


def remove_signatures(text: str) -> str:
    """Loại bỏ chữ ký, lời chào cuối thư."""
    # Danh sách pattern chữ ký cuối thư
    sig_patterns = [
        r"\n+TVHT\s*$",
        r"\n+tvht\s*$",
        r"\n+Thân ái[,.]?\s*$",
        r"\n+Thân mến[,.]?\s*$",
        r"\n+Trân trọng[,.]?\s*$",
        r"\n+BR\s*$",
        r"\n+Best regards[,.]?\s*$",
        r"\n+Regards[,.]?\s*$",
    ]
    for pat in sig_patterns:
        text = re.sub(pat, "", text, flags=re.MULTILINE | re.IGNORECASE)

    # Loại dòng chữ ký tên ngắn cuối cùng (vd: "nlgiang", "Cao Tuấn Dũng")
    # Chỉ xóa nếu dòng cuối <= 30 ký tự và không phải câu hoàn chỉnh
    lines = text.rstrip().split("\n")
    while (
        lines
        and len(lines[-1].strip()) <= 30
        and not lines[-1].strip().endswith((".", "?", "!", "ạ", "nhé", "em"))
    ):
        last = lines[-1].strip()
        # Giữ lại nếu trông giống nội dung thực
        if len(last) > 5 and any(c in last for c in ".,?!"):
            break
        if not last:
            lines.pop()
            continue
        # Xóa nếu trông giống tên người / viết tắt
        if re.match(r"^[A-ZÀ-Ỹa-zà-ỹ\s\.]{1,30}$", last):
            lines.pop()
        else:
            break

    return "\n".join(lines).strip()


def remove_internal_messages(text: str) -> str:
    """Loại bỏ các phần trao đổi nội bộ giữa giáo viên (Kính gửi thầy...)."""
    # Nếu bắt đầu bằng "Kính gửi thầy/cô" → đây là tin nội bộ
    if re.match(r"^Kính gửi\s+(thầy|thày|cô)", text, re.IGNORECASE):
        return ""
    return text


def remove_personal_info(text: str) -> str:
    """Loại bỏ thông tin cá nhân nhạy cảm."""
    # Loại email
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)
    # Loại MSSV
    text = re.sub(r"\b(mssv|MSSV)\s*:?\s*\d{8}\b", "[MSSV]", text)
    text = re.sub(r"\b20\d{6}\b", "[MSSV]", text)
    # Loại số điện thoại
    text = re.sub(r"\b0\d{9,10}\b", "[SĐT]", text)
    return text


def clean_question(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = clean_text(text)
    text = remove_email_metadata(text)
    text = remove_personal_info(text)
    # Loại lời chào đầu thư quá chung chung (giữ nội dung)
    text = re.sub(
        r"^(Dạ\s+)?(thưa\s+)?(thầy|cô)[,.]?\s*", "", text, flags=re.IGNORECASE
    )
    text = re.sub(
        r"^Em\s+chào\s+(thầy|cô)[,.]?\s*", "", text, flags=re.IGNORECASE
    )
    text = re.sub(
        r"^Kính\s+gửi\s+(thầy|cô)[,.]?\s*", "", text, flags=re.IGNORECASE
    )
    # Loại lời cảm ơn cuối
    text = re.sub(
        r"\n*(Em\s+)?(xin\s+)?cám ơn\s*(thầy|cô)?[.!]?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\n*(Em\s+)?(xin\s+)?cảm ơn\s*(thầy|cô)?[.!]?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def clean_answer(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = clean_text(text)
    text = remove_internal_messages(text)
    if not text:
        return ""
    text = remove_email_metadata(text)
    text = remove_signatures(text)
    text = remove_personal_info(text)
    # Loại lời chào đầu "Chào em," nhưng giữ phần sau
    text = re.sub(r"^Chào em[,.]?\s*\n?", "", text, flags=re.IGNORECASE)
    return text.strip()


def is_valid_pair(question: str, answer: str) -> bool:
    """Kiểm tra cặp Q-A có đủ chất lượng không."""
    if not question or not answer:
        return False
    if len(question) < 10 or len(answer) < 15:
        return False
    # Loại câu trả lời chỉ yêu cầu thêm thông tin mà không có nội dung
    low_quality_patterns = [
        r"^Em cho biết thêm",
        r"^(Em )?liên hệ trực tiếp",
        r"^Đây là email",
    ]
    for pat in low_quality_patterns:
        if re.match(pat, answer, re.IGNORECASE):
            return False
    return True


# ── Main pipeline ──────────────────────────────────────────────────────
def main():
    print("Loading data...")
    df = pd.read_csv(INPUT_PATH)
    print(f"  Total rows: {len(df)}")

    # ── 1. Drop rows without questions ────────────────────────────────
    df = df.dropna(subset=["questions"])
    print(f"  After dropping null questions: {len(df)}")

    # ── 2. Clean questions & answers ──────────────────────────────────
    print("Cleaning texts...")
    df["clean_question"] = df["questions"].apply(clean_question)
    df["clean_answer"] = df["answers"].apply(clean_answer)

    # ── 3. Filter valid pairs ─────────────────────────────────────────
    valid_mask = df.apply(
        lambda r: is_valid_pair(r["clean_question"], r["clean_answer"]), axis=1
    )
    df_valid = df[valid_mask].copy()
    print(f"  Valid Q-A pairs: {len(df_valid)}")

    # ── 4. Deduplicate ────────────────────────────────────────────────
    df_valid = df_valid.drop_duplicates(
        subset=["clean_question", "clean_answer"]
    )
    print(f"  After dedup: {len(df_valid)}")

    # ═══════════════════════════════════════════════════════════════════
    # Format 1: Single-turn Q-A pairs (JSONL)
    # ═══════════════════════════════════════════════════════════════════
    qa_pairs = []
    for _, row in df_valid.iterrows():
        qa_pairs.append(
            {
                "question": row["clean_question"],
                "answer": row["clean_answer"],
            }
        )

    qa_path = OUTPUT_DIR / "train_qa_pairs.jsonl"
    with open(qa_path, "w", encoding="utf-8") as f:
        for item in qa_pairs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n[1] Saved {len(qa_pairs)} Q-A pairs → {qa_path}")

    # ═══════════════════════════════════════════════════════════════════
    # Format 2: Multi-turn conversations (OpenAI chat format)
    # ═══════════════════════════════════════════════════════════════════
    conversations = []
    for thread_id, group in df_valid.groupby("thread_id"):
        group = group.sort_values("created_at")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for _, row in group.iterrows():
            messages.append({"role": "user", "content": row["clean_question"]})
            messages.append(
                {"role": "assistant", "content": row["clean_answer"]}
            )
        conversations.append({"thread_id": thread_id, "messages": messages})

    conv_path = OUTPUT_DIR / "train_conversations.jsonl"
    with open(conv_path, "w", encoding="utf-8") as f:
        for item in conversations:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[2] Saved {len(conversations)} conversations → {conv_path}")

    # ═══════════════════════════════════════════════════════════════════
    # Format 3: Instruction format (Alpaca-style)
    # ═══════════════════════════════════════════════════════════════════
    instruction_data = []
    for _, row in df_valid.iterrows():
        instruction_data.append(
            {
                "instruction": SYSTEM_PROMPT,
                "input": row["clean_question"],
                "output": row["clean_answer"],
            }
        )

    inst_path = OUTPUT_DIR / "train_instruction.jsonl"
    with open(inst_path, "w", encoding="utf-8") as f:
        for item in instruction_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(
        f"[3] Saved {len(instruction_data)} instruction samples → {inst_path}"
    )

    # ═══════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════
    q_lens = df_valid["clean_question"].str.len()
    a_lens = df_valid["clean_answer"].str.len()
    stats = {
        "total_raw_rows": int(pd.read_csv(INPUT_PATH).shape[0]),
        "valid_qa_pairs": len(qa_pairs),
        "unique_conversations": len(conversations),
        "question_length": {
            "min": int(q_lens.min()),
            "median": int(q_lens.median()),
            "mean": round(float(q_lens.mean()), 1),
            "max": int(q_lens.max()),
        },
        "answer_length": {
            "min": int(a_lens.min()),
            "median": int(a_lens.median()),
            "mean": round(float(a_lens.mean()), 1),
            "max": int(a_lens.max()),
        },
    }

    stats_path = OUTPUT_DIR / "training_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n[Stats] → {stats_path}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    # ── Sample output ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SAMPLE Q-A PAIRS (first 3):")
    print("=" * 60)
    for i, item in enumerate(qa_pairs[:3]):
        print(f"\n--- Sample {i+1} ---")
        print(f"Q: {item['question'][:200]}")
        print(f"A: {item['answer'][:200]}")


if __name__ == "__main__":
    main()
