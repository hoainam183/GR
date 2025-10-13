import pandas as pd 
import os

# Đường dẫn file CSV
CSV_PATH = os.path.join(os.path.dirname(__file__), "../../clean_data.csv")

def append_records(new_records: list):
    """
    Thêm nhiều record mới vào file clean_data.csv
    new_records: list chứa dict dữ liệu mới, phải khớp cột với file csv
    """
    df_new = pd.DataFrame(new_records)
    df_new.to_csv(CSV_PATH, mode="a", header=False, index=False, encoding="utf-8-sig")
    print(f"✔️ Đã thêm {len(new_records)} record vào clean_data.csv")

if __name__ == "__main__":
    # Danh sách record thật
    new_records = [
        {
            "id": 3,
            "question": "Em muốn hỏi ngành Công nghệ thông tin Việt Nhật đầu ra có yêu cầu tiếng Anh không ạ? Và thời gian đào tạo là bao lâu ạ?",
            "answer": "Chào em,\n\nNgành Công nghệ thông tin Việt Nhật có thời gian đào tạo là 5 năm và ra trường với bằng kỹ sư. Chương trình này không yêu cầu điều kiện đầu ra cho tiếng Anh.\n\nChúc em thành công!",
            "category_main": "CHƯƠNG TRÌNH ĐÀO TẠO",
            "category_sub": "Thông tin chương trình; Điều kiện đầu ra",
            "tags": "Công nghệ thông tin Việt Nhật;thời gian đào tạo;điều kiện đầu ra;tiếng Anh;5 năm;bằng kỹ sư",
            "program": "Công nghệ thông tin Việt Nhật",
            "course_codes": "",
            "year": "",
            "complexity": "low",
            "requires_admin": "false",
            "solution_type": "direct"
        }
    ]

    append_records(new_records)