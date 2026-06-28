import os
import glob
import subprocess
import time


def main():
    data_dir = os.path.join("evaluation", "data")

    # Lấy danh sách các file dataset chính (loại bỏ các file trùng lặp có đuôi (1))
    datasets = [
        "06_Quy_dinh_ngoai_ngu_chunks.json",
        "blending_rag_dataset.json",
        "hbkkht_rag_dataset.json",
        "kehoach_rag_dataset.json",
        "Khung-DGRL-2020-2021_rag_eval_dataset.json",
        "kscs_rag_dataset.json",
        "olympic_rag_dataset.json",
        "qpan_rag_dataset.json",
        "rag_evaluation_dataset.json",
        "rag_evaluation_dataset_ELITECH.json",
        "rag_evaluation_dataset_ITE6_fix_chunks.json",
        "rag_evaluation_dataset_ITE7_fix_chunks.json",
        "rag_evaluation_dataset_k63_k64.json",
        "renluyen_rag_dataset.json",
        "svnn_rag_dataset.json",
        "thitructuyen_rag_dataset.json",
    ]

    print(f"Bắt đầu chạy đánh giá cho {len(datasets)} datasets...")

    for ds_name in datasets:
        ds_path = os.path.join(data_dir, ds_name)

        if not os.path.exists(ds_path):
            print(f"⚠️ Không tìm thấy file {ds_path}, bỏ qua.")
            continue

        print(f"\n" + "=" * 60)
        print(f"🚀 Đang đánh giá: {ds_name}")
        print("=" * 60)

        cmd = [
            "python",
            "-m",
            "evaluation.evaluate",
            "--dataset",
            ds_path,
            "--provider",
            "deepseek",
            "--vector-weight",
            "0.5",
            "--keyword-weight",
            "0.5",
        ]

        try:
            # Chạy lệnh evaluate, output sẽ in thẳng ra màn hình và file report sẽ được lưu như bình thường
            subprocess.run(cmd, check=True)
            print(f"✅ Đã hoàn thành: {ds_name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Lỗi khi chạy {ds_name}. Exit code: {e.returncode}")

        # Nghỉ 5 giây giữa các dataset để tránh rate limit của API
        time.sleep(5)

    print("\n🎉 Đã chạy xong tất cả các dataset!")


if __name__ == "__main__":
    main()
