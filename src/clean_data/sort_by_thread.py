import pandas as pd
import os

# Đường dẫn file CSV
CSV_PATH = os.path.join(os.path.dirname(__file__), "../../data.csv")

# Bước 1: Đọc file CSV
print("Đang đọc file data.csv...")
df = pd.read_csv(CSV_PATH, encoding='utf-8')
print(f"✓ Đã đọc {len(df)} dòng")

# Bước 2: Làm sạch thread_id (loại bỏ khoảng trắng thừa)
print("\nĐang làm sạch thread_id...")
df['thread_id'] = df['thread_id'].astype(str).str.strip()

# Bước 3: Chuyển đổi created_at sang datetime
print("Đang chuyển đổi định dạng thời gian...")
df['created_at'] = pd.to_datetime(df['created_at'])

# Bước 4: Sắp xếp theo thread_id và created_at
print("Đang sắp xếp dữ liệu...")
df_sorted = df.sort_values(by=['thread_id', 'created_at'], ascending=[True, True])

# Bước 5: Sửa lỗi encoding tiếng Việt
print("Đang sửa lỗi encoding tiếng Việt...")

def fix_encoding(text):
    """Sửa lỗi encoding từ latin-1 về utf-8"""
    if pd.isna(text):
        return text
    if isinstance(text, str):
        try:
            # Thử chuyển đổi từ latin-1 về utf-8
            return text.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Nếu không được, giữ nguyên
            return text
    return text

# Áp dụng sửa lỗi encoding cho các cột text
text_columns = ['student_email', 'questions', 'teacher_email', 'answers']
for col in text_columns:
    if col in df_sorted.columns:
        df_sorted[col] = df_sorted[col].apply(fix_encoding)

# Bước 6: Xuất ra file mới
print("\nĐang xuất file data2.csv...")
df_sorted.to_csv('data2.csv', index=False, encoding='utf-8-sig')

# Bước 7: Hiển thị thông tin tổng kết
print("\n" + "="*50)
print("✅ HOÀN THÀNH!")
print("="*50)
print(f"Tổng số dòng: {len(df_sorted)}")
print(f"Số thread_id unique: {df_sorted['thread_id'].nunique()}")
print(f"\nTop 5 thread_id có nhiều câu hỏi nhất:")
print(df_sorted['thread_id'].value_counts().head(5))
print(f"\nMột vài dòng đầu tiên trong data2.csv:")
print(df_sorted[['thread_id', 'created_at', 'student_email']].head(10).to_string())