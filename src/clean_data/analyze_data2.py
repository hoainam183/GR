import csv
import re
from collections import Counter, defaultdict
from datetime import datetime

# Read data
with open(r'D:\GR\src\clean_data\data2.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"=" * 70)
print(f"PHÂN TÍCH DỮ LIỆU data2.csv - Email Tư Vấn Học Tập")
print(f"=" * 70)

# Basic stats
print(f"\n--- THỐNG KÊ CƠ BẢN ---")
print(f"Tổng số dòng (cặp Q&A): {len(rows)}")
unique_threads = set(r['thread_id'] for r in rows)
print(f"Số thread (cuộc hội thoại) duy nhất: {len(unique_threads)}")
unique_students = set(r['student_email'] for r in rows)
print(f"Số sinh viên duy nhất: {len(unique_students)}")
unique_teachers = set(r['teacher_email'] for r in rows)
print(f"Số giáo viên/email trả lời duy nhất: {len(unique_teachers)}")

# Thread analysis
thread_counts = Counter(r['thread_id'] for r in rows)
thread_lengths = list(thread_counts.values())
avg_thread = sum(thread_lengths) / len(thread_lengths)
print(f"\n--- PHÂN TÍCH THREAD ---")
print(f"Trung bình số lượt trao đổi/thread: {avg_thread:.2f}")
print(f"Min lượt trao đổi/thread: {min(thread_lengths)}")
print(f"Max lượt trao đổi/thread: {max(thread_lengths)}")
print(f"Median lượt trao đổi/thread: {sorted(thread_lengths)[len(thread_lengths)//2]}")

# Distribution of thread lengths
dist = Counter(thread_lengths)
print(f"\nPhân bố số lượt trao đổi/thread:")
for k in sorted(dist.keys()):
    print(f"  {k} lượt: {dist[k]} threads ({dist[k]/len(thread_lengths)*100:.1f}%)")

# Token analysis (approximate by word count for Vietnamese)
def count_tokens_approx(text):
    """Approximate token count - split by whitespace"""
    if not text:
        return 0
    return len(text.split())

def count_chars(text):
    if not text:
        return 0
    return len(text)

question_tokens = [count_tokens_approx(r['questions']) for r in rows]
answer_tokens = [count_tokens_approx(r['answers']) for r in rows]
question_chars = [count_chars(r['questions']) for r in rows]
answer_chars = [count_chars(r['answers']) for r in rows]

print(f"\n--- PHÂN TÍCH TOKEN (ước lượng theo word) ---")
print(f"Câu hỏi:")
print(f"  Trung bình: {sum(question_tokens)/len(question_tokens):.1f} words")
print(f"  Min: {min(question_tokens)} words")
print(f"  Max: {max(question_tokens)} words")
print(f"  Median: {sorted(question_tokens)[len(question_tokens)//2]} words")
print(f"  Trung bình ký tự: {sum(question_chars)/len(question_chars):.0f} chars")

print(f"Câu trả lời:")
print(f"  Trung bình: {sum(answer_tokens)/len(answer_tokens):.1f} words")
print(f"  Min: {min(answer_tokens)} words")
print(f"  Max: {max(answer_tokens)} words")
print(f"  Median: {sorted(answer_tokens)[len(answer_tokens)//2]} words")
print(f"  Trung bình ký tự: {sum(answer_chars)/len(answer_chars):.0f} chars")

# Combined Q+A per row
combined_tokens = [q + a for q, a in zip(question_tokens, answer_tokens)]
print(f"\nQ+A kết hợp:")
print(f"  Trung bình: {sum(combined_tokens)/len(combined_tokens):.1f} words")
print(f"  Tổng tokens toàn bộ dataset: {sum(combined_tokens):,}")

# Check for duplicate questions
question_texts = [r['questions'].strip() for r in rows]
unique_questions = set(question_texts)
print(f"\n--- DUPLICATE ANALYSIS ---")
print(f"Tổng câu hỏi: {len(question_texts)}")
print(f"Câu hỏi unique (text): {len(unique_questions)}")
print(f"Tỉ lệ trùng lặp: {(1 - len(unique_questions)/len(question_texts))*100:.1f}%")

# Same question with multiple answers (within same thread)
thread_question_answers = defaultdict(list)
for r in rows:
    key = (r['thread_id'], r['questions'].strip())
    thread_question_answers[key].append(r['answers'])

multi_answer = sum(1 for v in thread_question_answers.values() if len(v) > 1)
print(f"Câu hỏi có nhiều câu trả lời (cùng thread): {multi_answer}")

# Topic classification (keyword-based)
print(f"\n--- PHÂN LOẠI CHỦ ĐỀ (keyword-based) ---")

topic_keywords = {
    "Đăng ký học phần / Lịch học": ["đăng ký", "đăng kí", "học phần", "lịch học", "trùng lịch", "mã lớp", "mở lớp"],
    "Học phần tương đương / Thay thế": ["tương đương", "thay thế", "chuyển đổi", "chuyển điểm"],
    "Đồ án / Project / ĐATN": ["đồ án", "project", "đatn", "tốt nghiệp", "đồ an", "bảo vệ"],
    "Thực tập": ["thực tập", "it4992", "internship"],
    "Điểm số / GPA / CPA": ["điểm", "gpa", "cpa", "chấm điểm", "điểm cuối kỳ", "điểm thi"],
    "Chương trình đào tạo": ["chương trình", "đào tạo", "ctđt", "chuyên ngành", "định hướng"],
    "Bảo lưu / Gia hạn": ["bảo lưu", "gia hạn", "nghỉ học", "hết hạn"],
    "Học phí / Tài chính": ["học phí", "phí", "nộp tiền", "hoàn phí", "tài chính"],
    "Giấy tờ / Thủ tục": ["giấy", "đơn", "xác nhận", "thủ tục", "biểu mẫu", "chứng nhận"],
    "Thạc sĩ / Sau đại học": ["thạc sĩ", "thạc sỹ", "sau đại học", "cao học"],
    "Kỹ sư / Cử nhân": ["kỹ sư", "cử nhân", "ks", "cn"],
    "Rèn luyện / Hoạt động": ["rèn luyện", "hoạt động", "sinh hoạt", "điểm rèn"],
    "Tín chỉ": ["tín chỉ", "tín", "tc"],
    "Tiếng Anh / Ngoại ngữ": ["tiếng anh", "toeic", "ngoại ngữ", "english"],
    "KTX / Nhà ở": ["ký túc", "ktx", "nhà trọ", "chỗ ở"],
    "Lịch thi / Thi": ["lịch thi", "thi lại", "phúc tra", "phúc khảo"],
}

topic_counts = Counter()
uncategorized = 0

for r in rows:
    q = r['questions'].lower()
    matched = False
    for topic, keywords in topic_keywords.items():
        if any(kw in q for kw in keywords):
            topic_counts[topic] += 1
            matched = True
    if not matched:
        uncategorized += 1

print(f"{'Chủ đề':<45} {'Số lượng':>8} {'Tỉ lệ':>8}")
print("-" * 65)
for topic, count in topic_counts.most_common():
    print(f"  {topic:<43} {count:>8} {count/len(rows)*100:>7.1f}%")
print(f"  {'Chưa phân loại':<43} {uncategorized:>8} {uncategorized/len(rows)*100:>7.1f}%")

# Time analysis
print(f"\n--- PHÂN TÍCH THỜI GIAN ---")
response_times = []
for r in rows:
    try:
        q_time = datetime.strptime(r['created_at'].strip(), "%m/%d/%Y %H:%M")
        a_time = datetime.strptime(r['answer_created_at'].strip(), "%m/%d/%Y %H:%M")
        diff = (a_time - q_time).total_seconds() / 3600  # hours
        if diff > 0:
            response_times.append(diff)
    except:
        pass

if response_times:
    print(f"Thời gian phản hồi trung bình: {sum(response_times)/len(response_times):.1f} giờ")
    print(f"Median: {sorted(response_times)[len(response_times)//2]:.1f} giờ")
    print(f"Min: {min(response_times):.1f} giờ")
    print(f"Max: {max(response_times):.1f} giờ")
    within_24h = sum(1 for t in response_times if t <= 24)
    within_48h = sum(1 for t in response_times if t <= 48)
    print(f"Phản hồi trong 24h: {within_24h} ({within_24h/len(response_times)*100:.1f}%)")
    print(f"Phản hồi trong 48h: {within_48h} ({within_48h/len(response_times)*100:.1f}%)")

# Year distribution
print(f"\n--- PHÂN BỐ THEO NĂM ---")
year_counts = Counter()
for r in rows:
    try:
        dt = datetime.strptime(r['created_at'].strip(), "%m/%d/%Y %H:%M")
        year_counts[dt.year] += 1
    except:
        pass
for year in sorted(year_counts.keys()):
    print(f"  {year}: {year_counts[year]} dòng ({year_counts[year]/len(rows)*100:.1f}%)")

# Answer quality metrics
print(f"\n--- CHẤT LƯỢNG CÂU TRẢ LỜI ---")
# Check for forwarding (teacher forwarding to another teacher)
forwarded = sum(1 for r in rows if any(kw in r['answers'].lower() for kw in ['kính gửi', 'kính chuyển', 'nhờ thầy', 'nhờ cô', 'chuyển cho']))
direct_answer = len(rows) - forwarded
print(f"Trả lời trực tiếp: {direct_answer} ({direct_answer/len(rows)*100:.1f}%)")
print(f"Chuyển tiếp/nhờ người khác: {forwarded} ({forwarded/len(rows)*100:.1f}%)")

# Answers with URLs
has_url = sum(1 for r in rows if 'http' in r['answers'].lower())
print(f"Câu trả lời có URL: {has_url} ({has_url/len(rows)*100:.1f}%)")

# Empty/very short answers
short_answers = sum(1 for r in rows if count_tokens_approx(r['answers']) < 10)
print(f"Câu trả lời ngắn (<10 words): {short_answers} ({short_answers/len(rows)*100:.1f}%)")

# Teacher distribution
print(f"\n--- PHÂN BỐ GIÁO VIÊN TRẢ LỜI ---")
teacher_counts = Counter(r['teacher_email'] for r in rows)
for teacher, count in teacher_counts.most_common(10):
    print(f"  {teacher:<45} {count:>5} ({count/len(rows)*100:.1f}%)")

# RAG-specific metrics
print(f"\n--- METRICS CHO HỆ THỐNG RAG ---")
print(f"Tổng số cặp Q&A có thể dùng training: {len(rows)}")
print(f"Số unique questions: {len(unique_questions)}")

# Questions that need context from previous messages in thread
multi_turn_threads = {tid for tid, count in thread_counts.items() if count > 1}
context_dependent = 0
for r in rows:
    if r['thread_id'] in multi_turn_threads:
        q = r['questions'].lower()
        if any(kw in q for kw in ['dạ', 'vâng', 'em đã', 'như trên', 'em hỏi thêm', 'thêm', 'đó', 'ở trên', 'như vậy']):
            context_dependent += 1

print(f"Câu hỏi phụ thuộc ngữ cảnh (cần context trước): {context_dependent} ({context_dependent/len(rows)*100:.1f}%)")
print(f"Threads đa lượt (multi-turn): {len(multi_turn_threads)} ({len(multi_turn_threads)/len(unique_threads)*100:.1f}%)")

# Estimate chunk sizes needed
avg_qa_length = sum(combined_tokens) / len(combined_tokens)
print(f"\nƯớc lượng chunk size phù hợp:")
print(f"  Trung bình Q+A: {avg_qa_length:.0f} words ≈ {avg_qa_length*1.5:.0f} tokens (Vietnamese)")
print(f"  P90 Q+A: {sorted(combined_tokens)[int(len(combined_tokens)*0.9)]} words")
print(f"  P95 Q+A: {sorted(combined_tokens)[int(len(combined_tokens)*0.95)]} words")
print(f"  P99 Q+A: {sorted(combined_tokens)[int(len(combined_tokens)*0.99)]} words")

# Full thread token analysis
thread_tokens = defaultdict(int)
for r in rows:
    thread_tokens[r['thread_id']] += count_tokens_approx(r['questions']) + count_tokens_approx(r['answers'])

thread_token_list = list(thread_tokens.values())
print(f"\nToken per full thread:")
print(f"  Trung bình: {sum(thread_token_list)/len(thread_token_list):.0f} words")
print(f"  Max: {max(thread_token_list)} words")
print(f"  P90: {sorted(thread_token_list)[int(len(thread_token_list)*0.9)]} words")
print(f"  P95: {sorted(thread_token_list)[int(len(thread_token_list)*0.95)]} words")

print(f"\n{'=' * 70}")
print(f"KẾT THÚC PHÂN TÍCH")
print(f"{'=' * 70}")
