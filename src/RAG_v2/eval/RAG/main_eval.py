"""
main_eval.py — Điều phối toàn bộ RAG Evaluation Pipeline

Sử dụng:
    # Với LMStudio (Qwen3 8B đang chạy local)
    python main_eval.py --backend lmstudio

    # Với Google Gemini
    python main_eval.py --backend gemini --api-key YOUR_KEY

    # Tùy chỉnh số lượng
    python main_eval.py --backend lmstudio --max-chunks 20 --questions-per-chunk 3

    # Chỉ sinh QA dataset, chưa đánh giá
    python main_eval.py --backend lmstudio --generate-only
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Thêm thư mục hiện tại vào path
sys.path.insert(0, str(Path(__file__).parent))

from .config import EvalConfig, BackendType, DEFAULT_CONFIG
from .chunk_loader import load_and_prepare_chunks
from .llm_client import create_llm_client
from .qa_generator import QAGenerator, QADataset
from .evaluator import RAGASEvaluator, SimpleAnswerGenerator


def sanitize_filename_part(name: str, max_len: int = 120) -> str:
    """Chuẩn hóa tên file để dùng an toàn trong output path."""
    safe = re.sub(r"[^\w.-]+", "_", name).strip("._")
    if not safe:
        safe = "chunk_file"
    return safe[:max_len]


def resolve_progress_file_path(cfg: EvalConfig, explicit_path: str | None) -> Path:
    """Trả về đường dẫn file progress cho batch mode."""
    if explicit_path:
        return Path(explicit_path)
    return Path(cfg.output_dir) / f"qa_batch_progress_{cfg.backend.value}.json"


def load_progress(progress_path: Path) -> dict[str, Any]:
    """Load progress JSON; nếu chưa có thì khởi tạo rỗng."""
    if not progress_path.exists():
        return {"version": 1, "files": {}}

    try:
        with open(progress_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # File hỏng/cụt không được làm dừng cả pipeline.
        return {"version": 1, "files": {}}

    if not isinstance(data, dict):
        return {"version": 1, "files": {}}
    if "files" not in data or not isinstance(data["files"], dict):
        data["files"] = {}
    data.setdefault("version", 1)
    return data


def save_progress(progress_path: Path, progress_data: dict[str, Any]) -> None:
    """Ghi progress an toàn bằng temp file rồi replace."""
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_data["updated_at"] = datetime.now().isoformat()
    tmp_path = progress_path.with_suffix(progress_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(progress_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG Evaluation Pipeline cho tài liệu ĐHBK Hà Nội",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--backend",
        choices=["lmstudio", "gemini", "gemini_with_fallback"],
        default="gemini_with_fallback",
        help="LLM backend (default: gemini_with_fallback — Gemini 2.5 Flash, fallback LMStudio khi hết RPD)",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Google API key (Gemini only, hoặc set GOOGLE_API_KEY env)",
    )
    parser.add_argument(
        "--max-chunks", type=int, default=0,
        help="Số chunk tối đa để lấy mẫu (default: 0 = dùng toàn bộ chunk hợp lệ)",
    )
    parser.add_argument(
        "--questions-per-chunk", type=int, default=2,
        help="Số câu hỏi mỗi chunk (default: 2)",
    )
    parser.add_argument(
        "--generate-only", action="store_true",
        help="Chỉ sinh QA dataset, không chạy RAGAS evaluation",
    )
    parser.add_argument(
        "--qa-file", type=str, default=None,
        help="Load QA dataset từ file JSON có sẵn (bỏ qua bước generation)",
    )
    parser.add_argument(
        "--output-dir", type=str, default="outputs",
        help="Thư mục lưu kết quả (default: outputs)",
    )
    parser.add_argument(
        "--split-output-by-chunk-file", action="store_true",
        help="Sinh mỗi file output riêng theo từng file chunks đầu vào",
    )
    parser.add_argument(
        "--max-files-per-run", type=int, default=0,
        help="Giới hạn số file chunks xử lý mỗi lượt chạy (default: 0 = không giới hạn)",
    )
    parser.add_argument(
        "--progress-file", type=str, default=None,
        help="File JSON lưu tiến độ batch (default: outputs/qa_batch_progress_<backend>.json)",
    )
    parser.add_argument(
        "--resume-from-progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Tiếp tục từ tiến độ đã có khi chạy split batch (default: bật)",
    )
    parser.add_argument(
        "--chunk-files", nargs="+",
        default=[
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/1.2. Kỹ thuật Cơ khí_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/2017.07.02-CTDT-KSCLC-Hang-khong_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/4.3. Kỹ thuật Nhiệt_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/CTDT_CDT_TN_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/CTĐT Cử nhân Kỹ thuật CĐT 2023_song ngữ_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/CTĐT ME-NUT_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/ME_GU_Giới thiệu CTwebsite 01_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/cokhi/chunks_recursive_parent_child/Quyển CTĐT Cơ điện tử_LUH website 01.docx_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/dien-dientu/chunks_recursive_parent_child/3khung_ct_cn_-thac-sy_k69_ee2_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/dien-dientu/chunks_recursive_parent_child/ctdt-dien-1-ee1-program-final.137618.10284_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/dien-dientu/chunks_recursive_parent_child/eee18_cttt_program_ee1_final_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/dien-dientu/chunks_recursive_parent_child/khung-ct-ee-ep-k68_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/dien-dientu/chunks_recursive_parent_child/khung-ctdt-ee-e8_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/Hoa_hoc_Chuong_trinh_cu_nhan_thac_si_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/KTHH_Ky_su_180TC_2021_23_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/KT_Moi_truong_Cu_nhan_Ky_su_Bac_7_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/KT_Sinh_hoc_Cu_nhan_Ky_su_Bac_7_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/QLTNMT_Cu_nhan_Ky_su_Bac_7_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/kt_thuc_pham_cu_nhan_ky_su_bac_7_2020_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/ky_thuat_hoa_duoc_ct_tien_tien_2020_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/hoa/chunks_recursive_parent_child/ky_thuat_thuc_pham_ct_tien_tien_2019_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/CTDT-CN.KHMT-K70-V2025.03.28_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/CTDT-CNKT-TaiNang-2025.03.30_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/IT2_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/ITE10_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/ITE15_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/ITE6_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/ITE7_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/soict/chunks_recursive_parent_child/ITEP_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/toan/chunks_recursive_parent_child/BSCS-Curriculum-2023-2024-updated_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/toan/chunks_recursive_parent_child/MI2_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/toan/chunks_recursive_parent_child/toantin_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/20231123-Khung-chuong-trinh-dao-tao-KTVDT-CNNN-cu-nhan-upload_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/Khung CTĐT_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/Khung chương trình đào tạo Công nghệ vật liệu polyme và compozit_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/MSE3 - Khung CTTT KH-KTVL_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/ctdt-cu-nhan-thac-si-kh-kt-in_song-ngu.03.03.2022_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/ctdt/vatlieu/chunks_recursive_parent_child/mse-k65-khung-ct-cu-nhan-2023-10-19-upload-web_fix_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/kehoach/chunks/kehoach_all_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/01_1 2015 TT Lien tich_QD danh gia QP-AN_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/01_3 HD hoc chuyen tiep ky su 180 TC_Final_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/06_ Quy định ngoại ngữ từ K70_chính quy_final_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/1. QĐ Học bổng KKHT 2023_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/4. QĐ thi Olympic và ĐMST 2023_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/5. Quy định QLSV nước ngoài 2023_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/ELITECH_K62_K64_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/Khung-DGRL-2020-2021_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QCDT_2025_5445_QD-DHBK_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QD NN DHCQ-2020-2021-1501_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QD ban hanh QD to chuc day hoc tren nen tang CN ket noi - truc tuyen_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QD ban hanh QD to chuc thi Truc tuyen_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QD_ngoai_ngu_tu_K68_CQ_final_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/Quy chế CTSV ĐHBK Hà Nội 2025.3.10_final_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/Quy định xét cấp HB tài trợ 2024 LasVer_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QĐ Ban hành hướng dân triển khai chính sachsHT cho SV khuyết tật_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/QĐ đánh giá điểm rèn luyện sinh viên 2023_converted_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/quydinh/olmocr/chunks_recursive_parent_child_3/chuan_tieng_anh_k63_k64_chunks.json",
            "/Users/nam.nguyen/GR/src/RAG_v2/data/stsv/chunks/stsv_all_chunks.json",
        ],
        help="Các file chunk JSON",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> EvalConfig:
    """Xây dựng EvalConfig từ args."""
    cfg = EvalConfig()
    cfg.backend = BackendType(args.backend)
    cfg.max_chunks_to_sample = args.max_chunks
    cfg.num_questions_per_chunk = args.questions_per_chunk
    cfg.output_dir = args.output_dir
    cfg.chunk_files = args.chunk_files

    if args.api_key:
        cfg.gemini.api_key = args.api_key

    return cfg


def generate_qa_dataset(cfg: EvalConfig, llm_client) -> tuple[QADataset, str]:
    """Bước 1: Sinh QA dataset từ chunks."""
    # Load và prepare chunks
    chunks = load_and_prepare_chunks(cfg)

    # Sinh QA pairs
    generator = QAGenerator(llm_client, cfg)
    dataset = generator.generate(chunks)

    # Lưu dataset
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(cfg.output_dir) / f"qa_dataset_{cfg.backend.value}_{timestamp}.json"
    dataset.save(output_path)

    return dataset, str(output_path)


def generate_qa_dataset_split_by_chunk_file(
    cfg: EvalConfig,
    llm_client,
    progress_file: str | None = None,
    resume_from_progress: bool = True,
    max_files_per_run: int = 0,
    include_existing_for_merge: bool = False,
) -> tuple[QADataset, list[str], str]:
    """Sinh QA dataset riêng cho từng file chunk và trả thêm dataset gộp."""
    output_paths: list[str] = []
    merged_dataset = QADataset()
    processed_in_this_run = 0

    progress_path = resolve_progress_file_path(cfg, progress_file)
    progress = load_progress(progress_path)
    progress_files = progress.setdefault("files", {})

    total_files = len(cfg.chunk_files)
    for idx, chunk_file in enumerate(cfg.chunk_files, 1):
        if max_files_per_run > 0 and processed_in_this_run >= max_files_per_run:
            print(f"\n⏸️ Đã đạt giới hạn --max-files-per-run={max_files_per_run}. Dừng lượt chạy hiện tại.")
            break

        entry = progress_files.get(chunk_file)
        if resume_from_progress and isinstance(entry, dict) and entry.get("status") == "done":
            saved_output = str(entry.get("output_path", "")).strip()
            if saved_output and Path(saved_output).exists():
                print(f"\n⏭️  Skip {idx}/{total_files}: đã xử lý trước đó")
                output_paths.append(saved_output)
                if include_existing_for_merge:
                    try:
                        prev_dataset = load_qa_dataset(saved_output)
                        merged_dataset.pairs.extend(prev_dataset.pairs)
                    except Exception as exc:
                        print(f"  ⚠️ Không load được output cũ ({saved_output}): {exc}")
                continue

        print(f"\n🧩 File {idx}/{total_files}: {chunk_file}")

        sub_cfg = EvalConfig()
        sub_cfg.backend = cfg.backend
        sub_cfg.max_chunks_to_sample = cfg.max_chunks_to_sample
        sub_cfg.num_questions_per_chunk = cfg.num_questions_per_chunk
        sub_cfg.output_dir = cfg.output_dir
        sub_cfg.chunk_files = [chunk_file]
        sub_cfg.min_chunk_size = cfg.min_chunk_size
        sub_cfg.question_type_ratios = cfg.question_type_ratios
        sub_cfg.ragas_metrics = cfg.ragas_metrics
        sub_cfg.lmstudio = cfg.lmstudio
        sub_cfg.gemini = cfg.gemini

        try:
            chunks = load_and_prepare_chunks(sub_cfg)
        except ValueError as exc:
            print(f"  ⚠️ Bỏ qua file này: {exc}")
            continue

        generator = QAGenerator(llm_client, sub_cfg)
        dataset = generator.generate(chunks)
        merged_dataset.pairs.extend(dataset.pairs)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = sanitize_filename_part(Path(chunk_file).stem)
        output_path = Path(cfg.output_dir) / f"qa_dataset_{cfg.backend.value}_{stem}_{timestamp}.json"
        dataset.save(output_path)
        output_paths.append(str(output_path))
        processed_in_this_run += 1

        progress_files[chunk_file] = {
            "status": "done",
            "output_path": str(output_path),
            "qa_pairs": len(dataset.pairs),
            "processed_at": datetime.now().isoformat(),
        }
        save_progress(progress_path, progress)

    if not output_paths:
        raise ValueError("Không sinh được file QA nào. Kiểm tra dữ liệu chunks hoặc bộ lọc.")

    return merged_dataset, output_paths, str(progress_path)


def load_qa_dataset(file_path: str) -> QADataset:
    """Load QA dataset từ file JSON đã lưu."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    from .qa_generator import QAPair
    pairs = []
    for item in data.get("pairs", []):
        pairs.append(QAPair(
            question=item["question"],
            ground_truth=item["ground_truth"],
            question_type=item.get("question_type", "factoid"),
            source_chunk_id=item.get("source_chunk_id", ""),
            source_file=item.get("source_file", ""),
            context=item.get("reference_contexts", [""])[0],
            hierarchy_path=item.get("hierarchy_path", ""),
        ))
    dataset = QADataset(pairs=pairs)
    print(f"✅ Loaded {len(pairs)} QA pairs từ {file_path}")
    return dataset


def run_evaluation(cfg: EvalConfig, llm_client, dataset: QADataset) -> str:
    """Bước 2: Chạy RAGAS evaluation."""
    # Sinh answers từ simple RAG (context-grounded)
    print("\n🔍 Sinh câu trả lời từ RAG pipeline...")
    answer_gen = SimpleAnswerGenerator(llm_client)
    answers = answer_gen.generate_answers(dataset.pairs)

    # Chạy RAGAS
    evaluator = RAGASEvaluator(llm_client, cfg)
    result = evaluator.evaluate(dataset, answers)

    # Lưu kết quả
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(cfg.output_dir) / f"eval_result_{cfg.backend.value}_{timestamp}.json"
    result.save(output_path)

    return str(output_path)


def print_banner(cfg: EvalConfig):
    print("""
╔══════════════════════════════════════════════════════╗
║          RAG Evaluation Pipeline - ĐHBK HN           ║
║     Tài liệu: IT Việt-Nhật + Quy định ngoại ngữ     ║
╚══════════════════════════════════════════════════════╝""")
    print(f"  Backend  : {cfg.backend.value.upper()}")
    print(f"  Chunks   : tối đa {cfg.max_chunks_to_sample}")
    print(f"  QA/chunk : {cfg.num_questions_per_chunk}")
    print(f"  Metrics  : {', '.join(cfg.ragas_metrics)}")
    print()


def main():
    args = parse_args()
    cfg = build_config(args)

    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)

    print_banner(cfg)

    # Khởi tạo LLM client
    llm_client = create_llm_client(cfg)

    # ── Bước 1: QA Dataset ──────────────────────────────────────────────────
    progress_file_path = None
    if args.qa_file:
        print(f"📂 Load QA dataset từ: {args.qa_file}")
        dataset = load_qa_dataset(args.qa_file)
        qa_file_path = args.qa_file
    else:
        print("📝 Bước 1/2: Sinh QA Dataset")
        if args.split_output_by_chunk_file:
            dataset, qa_file_paths, progress_file_path = generate_qa_dataset_split_by_chunk_file(
                cfg,
                llm_client,
                progress_file=args.progress_file,
                resume_from_progress=args.resume_from_progress,
                max_files_per_run=args.max_files_per_run,
                include_existing_for_merge=not args.generate_only,
            )
            qa_file_path = "\n             ".join(qa_file_paths)
        else:
            dataset, qa_file_path = generate_qa_dataset(cfg, llm_client)

    if args.generate_only:
        progress_info = f"\n  Progress   : {progress_file_path}" if progress_file_path else ""
        print(f"\n✅ Hoàn tất (--generate-only). QA Dataset lưu tại: {qa_file_path}{progress_info}")
        return

    # ── Bước 2: RAGAS Evaluation ────────────────────────────────────────────
    print("\n📊 Bước 2/2: Chạy RAGAS Evaluation")
    eval_file_path = run_evaluation(cfg, llm_client, dataset)

    print(f"""
╔══════════════════════════════════════════════════════╗
║                  🎉 Hoàn tất!                        ║
╚══════════════════════════════════════════════════════╝
  QA Dataset : {qa_file_path}
  Eval Result: {eval_file_path}
""")


if __name__ == "__main__":
    main()