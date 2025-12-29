import pandas as pd
import json


def create_test_dataset(csv_data):
    """
    Chuyển đổi data thô thành test dataset
    """
    df = pd.read_csv(csv_data)

    test_cases = []

    # Group theo thread_id để có full conversation
    grouped = df.groupby("thread_id")

    for thread_id, group in grouped:
        # Lấy các câu hỏi và câu trả lời
        conversations = []
        for _, row in group.iterrows():
            conversations.append(
                {
                    "question": row["questions"],
                    "answer": row["answers"],
                    "timestamp": row["created_at"],
                }
            )

        # Tạo test cases từ conversation
        for i, conv in enumerate(conversations):
            test_case = {
                "id": f"{thread_id}_{i}",
                "question": conv["question"],
                "ground_truth_answer": conv["answer"],
                "thread_id": thread_id,
                "context": "\n".join([c["answer"] for c in conversations[:i]]),
                "metadata": {
                    "student_email": group.iloc[0]["student_email"],
                    "teacher_email": group.iloc[0]["teacher_email"],
                    "timestamp": conv["timestamp"],
                },
            }
            test_cases.append(test_case)

    return test_cases


# Lưu test dataset
test_dataset = create_test_dataset("D:\GR\src\clean_data\data2.csv")
with open("test_dataset.json", "w", encoding="utf-8") as f:
    json.dump(test_dataset, f, ensure_ascii=False, indent=2)
