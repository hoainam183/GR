"""
demo_notebook.py — Demo chạy từng bước (thay thế Jupyter notebook)

Chạy: python demo_notebook.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


# ─── BƯỚC 0: Cấu hình ────────────────────────────────────────────────────────
print("=" * 60)
print("BƯỚC 0: Cấu hình")
print("=" * 60)

from config import EvalConfig, BackendType

cfg = EvalConfig()

# ⬇️ Chọn backend: LMSTUDIO hoặc GEMINI
cfg.backend = BackendType.LMSTUDIO
# cfg.backend = BackendType.GEMINI
# cfg.gemini.api_key = "YOUR_KEY_HERE"

# Đường dẫn đến file chunks
cfg.chunk_files = [
    "data/ITE6_fix_chunks.json",
    "data/06__Quy_dinh_ngoai_ngu_K70_chunks.json",
]

# Tham số sinh QA
cfg.max_chunks_to_sample = 15    # giảm để test nhanh
cfg.num_questions_per_chunk = 2

print(f"Backend: {cfg.backend.value}")
print(f"Max chunks: {cfg.max_chunks_to_sample}")


# ─── BƯỚC 1: Load và xem chunks ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("BƯỚC 1: Load Chunks")
print("=" * 60)

from chunk_loader import load_and_prepare_chunks

chunks = load_and_prepare_chunks(cfg)

# Xem vài mẫu
print(f"\n📋 Xem 3 chunk mẫu:")
for i, chunk in enumerate(chunks[:3], 1):
    print(f"\n[{i}] {chunk.chunk_id} | {chunk.source_file}")
    print(f"    Path: {chunk.hierarchy_path[:80]}...")
    print(f"    Size: {len(chunk.content)} chars | has_table={chunk.has_table}")
    print(f"    Content preview: {chunk.content[:150].strip()}...")


# ─── BƯỚC 2: Khởi tạo LLM Client ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("BƯỚC 2: Khởi tạo LLM Client")
print("=" * 60)

from llm_client import create_llm_client

client = create_llm_client(cfg)

# Test nhanh client
print("\n🧪 Test LLM client...")
test_response = client.generate(
    prompt="Tiếng Nhật N3 tương đương trình độ gì?",
    system_prompt="Trả lời ngắn gọn bằng tiếng Việt.",
)
print(f"Test response: {test_response[:200]}")


# ─── BƯỚC 3: Sinh QA Dataset ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BƯỚC 3: Sinh QA Dataset")
print("=" * 60)

from qa_generator import QAGenerator

generator = QAGenerator(client, cfg)
dataset = generator.generate(chunks)

# Lưu dataset
from pathlib import Path
Path("outputs").mkdir(exist_ok=True)
dataset.save("outputs/demo_qa_dataset.json")

# Xem vài mẫu
print(f"\n📋 Xem 5 QA pairs mẫu:")
for pair in dataset.pairs[:5]:
    print(f"\n[{pair.question_type.upper()}]")
    print(f"Q: {pair.question}")
    print(f"A: {pair.ground_truth}")
    print(f"Source: {pair.source_chunk_id}")


# ─── BƯỚC 4: Sinh Answers ────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BƯỚC 4: Sinh Answers từ RAG")
print("=" * 60)

from evaluator import SimpleAnswerGenerator

answer_gen = SimpleAnswerGenerator(client)
answers = answer_gen.generate_answers(dataset.pairs)

print(f"\n📋 Xem 3 answer mẫu:")
for pair, answer in zip(dataset.pairs[:3], answers[:3]):
    print(f"\nQ: {pair.question}")
    print(f"Expected: {pair.ground_truth}")
    print(f"Got:      {answer[:200]}")


# ─── BƯỚC 5: RAGAS Evaluation ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BƯỚC 5: RAGAS Evaluation")
print("=" * 60)

try:
    from evaluator import RAGASEvaluator

    evaluator = RAGASEvaluator(client, cfg)
    result = evaluator.evaluate(dataset, answers)
    result.save("outputs/demo_eval_result.json")

    print("\n🎉 Evaluation hoàn tất!")
    print(f"   Kết quả: outputs/demo_eval_result.json")

except ImportError as e:
    print(f"\n⚠️  RAGAS chưa được cài: {e}")
    print("   Chạy: pip install ragas datasets")
    print("   QA dataset đã được lưu tại: outputs/demo_qa_dataset.json")
