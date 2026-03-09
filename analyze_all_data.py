import json
import os
import glob
import csv
from collections import Counter, defaultdict
from datetime import datetime

results = {}

# ========== 1. Email Q&A (data2.csv) ==========
rows = []
with open(r"D:\GR\src\clean_data\data2.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


def wc(t):
    return len(t.split()) if t else 0


qtokens = [wc(r["questions"]) for r in rows]
atokens = [wc(r["answers"]) for r in rows]
combined = [q + a for q, a in zip(qtokens, atokens)]
thread_counts = Counter(r["thread_id"] for r in rows)
thread_lens = list(thread_counts.values())
sorted_tl = sorted(thread_lens)
unique_q = len(set(r["questions"].strip() for r in rows))
fwd = sum(
    1
    for r in rows
    if any(
        k in r["answers"].lower()
        for k in ["kính gửi", "kính chuyển", "nhờ thầy", "nhờ cô", "chuyển cho"]
    )
)
has_url = sum(1 for r in rows if "http" in r["answers"].lower())

# Response times
resp_times = []
for r in rows:
    try:
        q_t = datetime.strptime(r["created_at"].strip(), "%m/%d/%Y %H:%M")
        a_t = datetime.strptime(
            r["answer_created_at"].strip(), "%m/%d/%Y %H:%M"
        )
        diff = (a_t - q_t).total_seconds() / 3600
        if diff > 0:
            resp_times.append(diff)
    except:
        pass

year_dist = Counter()
for r in rows:
    try:
        dt = datetime.strptime(r["created_at"].strip(), "%m/%d/%Y %H:%M")
        year_dist[dt.year] += 1
    except:
        pass

# Topic classification
topic_kw = {
    "Đăng ký học phần / Lịch học": [
        "đăng ký",
        "đăng kí",
        "học phần",
        "lịch học",
        "trùng lịch",
        "mã lớp",
        "mở lớp",
    ],
    "Chương trình đào tạo": [
        "chương trình",
        "đào tạo",
        "ctđt",
        "chuyên ngành",
        "định hướng",
    ],
    "Đồ án / Project / ĐATN": [
        "đồ án",
        "project",
        "đatn",
        "tốt nghiệp",
        "bảo vệ",
    ],
    "Học phần tương đương / Thay thế": [
        "tương đương",
        "thay thế",
        "chuyển đổi",
        "chuyển điểm",
    ],
    "Kỹ sư / Cử nhân": ["kỹ sư", "cử nhân"],
    "Tín chỉ": ["tín chỉ", "tín", " tc "],
    "Điểm số / GPA / CPA": ["điểm", "gpa", "cpa", "chấm điểm", "điểm cuối kỳ"],
    "Giấy tờ / Thủ tục": ["giấy", "đơn", "xác nhận", "thủ tục", "biểu mẫu"],
    "Thực tập": ["thực tập", "it4992"],
    "Thạc sĩ / Sau đại học": ["thạc sĩ", "thạc sỹ", "sau đại học", "cao học"],
    "Tiếng Anh / Ngoại ngữ": ["tiếng anh", "toeic", "ngoại ngữ"],
    "Học phí / Tài chính": ["học phí", "phí", "nộp tiền"],
    "Bảo lưu / Gia hạn": ["bảo lưu", "gia hạn", "hết hạn"],
    "Rèn luyện / Hoạt động": ["rèn luyện", "hoạt động", "sinh hoạt"],
    "Lịch thi / Thi": ["lịch thi", "thi lại", "phúc tra"],
}
topic_cnts = Counter()
uncategorized = 0
for r in rows:
    q = r["questions"].lower()
    matched = False
    for topic, kws in topic_kw.items():
        if any(k in q for k in kws):
            topic_cnts[topic] += 1
            matched = True
    if not matched:
        uncategorized += 1

results["email"] = {
    "total_rows": len(rows),
    "total_threads": len(thread_counts),
    "unique_students": len(set(r["student_email"] for r in rows)),
    "unique_teachers": len(set(r["teacher_email"] for r in rows)),
    "avg_q_words": round(sum(qtokens) / len(qtokens), 1),
    "median_q_words": sorted(qtokens)[len(qtokens) // 2],
    "max_q_words": max(qtokens),
    "avg_a_words": round(sum(atokens) / len(atokens), 1),
    "median_a_words": sorted(atokens)[len(atokens) // 2],
    "avg_combined": round(sum(combined) / len(combined), 1),
    "p90_combined": sorted(combined)[int(len(combined) * 0.9)],
    "p95_combined": sorted(combined)[int(len(combined) * 0.95)],
    "p99_combined": sorted(combined)[int(len(combined) * 0.99)],
    "total_words": sum(combined),
    "avg_turns": round(sum(thread_lens) / len(thread_lens), 2),
    "max_turns": max(thread_lens),
    "single_turn": thread_lens.count(1),
    "multi_turn": sum(1 for v in thread_lens if v > 1),
    "unique_questions": unique_q,
    "dup_rate": round((1 - unique_q / len(rows)) * 100, 1),
    "forwarded": fwd,
    "forwarded_pct": round(fwd / len(rows) * 100, 1),
    "has_url": has_url,
    "avg_response_hours": (
        round(sum(resp_times) / len(resp_times), 1) if resp_times else 0
    ),
    "median_response_hours": (
        round(sorted(resp_times)[len(resp_times) // 2], 1) if resp_times else 0
    ),
    "within_24h": sum(1 for t in resp_times if t <= 24),
    "within_48h": sum(1 for t in resp_times if t <= 48),
    "year_dist": dict(sorted(year_dist.items())),
    "topic_counts": dict(topic_cnts.most_common()),
    "uncategorized": uncategorized,
}

# ========== 2. Chunk files (CTDT - recursive chunker) ==========
chunk_dirs = {
    "cokhi": r"D:\GR\src\RAG\data\ctdt\cokhi\chunks_recursive",
    "dien-dientu": r"D:\GR\src\RAG\data\ctdt\dien-dientu\clean_data",
    "soict": r"D:\GR\src\RAG\data\ctdt\soict\clean_data",
    "toan": r"D:\GR\src\RAG\data\ctdt\toan",
    "hoa": r"D:\GR\src\RAG\data\ctdt\hoa",
    "vatlieu": r"D:\GR\src\RAG\data\ctdt\vatlieu",
}

print("=== CHUNK FILES (CTDT recursive) ===")
all_chunks = []
file_stats = []

for vienvien, dirpath in chunk_dirs.items():
    if not os.path.exists(dirpath):
        continue
    json_files = glob.glob(
        os.path.join(dirpath, "**/*.json"), recursive=True
    ) + glob.glob(os.path.join(dirpath, "*.json"))
    for fp in json_files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data and "chunk_id" in data[0]:
                sizes = [
                    c.get("metadata", {}).get(
                        "chunk_size", wc(c.get("content", ""))
                    )
                    for c in data
                ]
                has_table = sum(
                    1
                    for c in data
                    if c.get("metadata", {}).get("has_table", False)
                )
                file_stats.append(
                    {
                        "file": os.path.basename(fp),
                        "school": vienvien,
                        "chunks": len(data),
                        "avg_size": (
                            round(sum(sizes) / len(sizes)) if sizes else 0
                        ),
                        "min_size": min(sizes) if sizes else 0,
                        "max_size": max(sizes) if sizes else 0,
                        "has_table_pct": (
                            round(has_table / len(data) * 100) if data else 0
                        ),
                        "doc_type": (
                            data[0]
                            .get("metadata", {})
                            .get("doc_type", "unknown")
                            if data
                            else "unknown"
                        ),
                    }
                )
                all_chunks.extend(data)
        except Exception as e:
            pass

print(f"Total CTDT chunk files analyzed: {len(file_stats)}")
print(f"Total chunks: {len(all_chunks)}")

# ========== 3. olmocr_chunks (quydinh) ==========
print("\n=== OLMOCR CHUNKS (quydinh) ===")
olmocr_files = glob.glob(r"D:\GR\src\RAG\olmocr_chunks\*.json")
olmocr_chunks = []
olmocr_stats = []
for fp in olmocr_files:
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            sizes = [wc(c.get("content", "")) for c in data]
            olmocr_stats.append(
                {
                    "file": os.path.basename(fp),
                    "chunks": len(data),
                    "avg_size": round(sum(sizes) / len(sizes)) if sizes else 0,
                    "max_size": max(sizes) if sizes else 0,
                }
            )
            olmocr_chunks.extend(data)
    except:
        pass

print(f"Total olmocr files: {len(olmocr_stats)}")
for s in olmocr_stats:
    print(
        f"  {s['file']}: {s['chunks']} chunks, avg={s['avg_size']} words, max={s['max_size']} words"
    )

# ========== 4. chunks_by_articles (quydinh) ==========
print("\n=== CHUNKS BY ARTICLES (quydinh) ===")
art_files = glob.glob(r"D:\GR\src\RAG\chunks_by_articles\*.json")
art_chunks = []
art_stats = []
for fp in art_files:
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            sizes = [wc(c.get("content", "")) for c in data]
            art_stats.append(
                {
                    "file": os.path.basename(fp),
                    "chunks": len(data),
                    "avg_size": round(sum(sizes) / len(sizes)) if sizes else 0,
                    "max_size": max(sizes) if sizes else 0,
                }
            )
            art_chunks.extend(data)
    except:
        pass
print(f"Total article files: {len(art_stats)}")
for s in art_stats:
    print(
        f"  {s['file']}: {s['chunks']} chunks, avg={s['avg_size']} words, max={s['max_size']} words"
    )

# ========== 5. Output JSON (crawled web) ==========
print("\n=== OUTPUT JSON (web crawl) ===")
out_files = glob.glob(r"D:\GR\output\*.json")
out_stats = []
total_out_words = 0
for fp in out_files:
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        content = ""
        if isinstance(data, dict):
            content = (
                str(data.get("content", ""))
                + str(data.get("text", ""))
                + str(data.get("body", ""))
            )
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    content += str(item.get("content", "")) + str(
                        item.get("text", "")
                    )
        w = wc(content)
        total_out_words += w
        out_stats.append({"file": os.path.basename(fp), "words": w})
    except:
        pass

out_stats.sort(key=lambda x: x["words"], reverse=True)
print(f"Total web JSON files: {len(out_stats)}")
print(f"Total words in web data: {total_out_words:,}")
print(
    f"Avg words per file: {total_out_words//len(out_stats) if out_stats else 0}"
)
print(f"Top 5 largest files:")
for s in out_stats[:5]:
    print(f"  {s['file']}: {s['words']:,} words")

# ========== 6. Evaluate data ==========
print("\n=== EVALUATE DATA ===")
eval_files = glob.glob(r"D:\GR\evaluate_data\*.csv")
for fp in eval_files:
    try:
        with open(fp, encoding="utf-8-sig") as f:
            erows = list(csv.DictReader(f))
        cols = list(erows[0].keys()) if erows else []
        print(f"  {os.path.basename(fp)}: {len(erows)} rows, cols={cols}")
    except Exception as e:
        print(f"  {os.path.basename(fp)}: ERROR {e}")

# ========== 7. CTDT chunk summary ==========
print("\n=== CTDT CHUNK SUMMARY ===")
all_sizes = [
    c.get("metadata", {}).get("chunk_size", wc(c.get("content", "")))
    for c in all_chunks
]
if all_sizes:
    sorted_s = sorted(all_sizes)
    print(f"Total CTDT chunks: {len(all_chunks)}")
    print(f"Avg chunk size: {sum(all_sizes)/len(all_sizes):.0f} chars")
    print(f"Min: {min(all_sizes)}, Max: {max(all_sizes)}")
    print(
        f"P50: {sorted_s[len(sorted_s)//2]}, P90: {sorted_s[int(len(sorted_s)*0.9)]}, P95: {sorted_s[int(len(sorted_s)*0.95)]}"
    )
    has_table_total = sum(
        1 for c in all_chunks if c.get("metadata", {}).get("has_table", False)
    )
    print(
        f"Chunks with table: {has_table_total} ({has_table_total/len(all_chunks)*100:.1f}%)"
    )

print("\n=== FILE BREAKDOWN BY SCHOOL ===")
school_data = defaultdict(list)
for fs in file_stats:
    school_data[fs["school"]].append(fs)

for school, files in sorted(school_data.items()):
    tot = sum(f["chunks"] for f in files)
    print(f"  {school}: {len(files)} docs, {tot} total chunks")
    for f in files:
        print(
            f"    - {f['file']}: {f['chunks']} chunks, avg={f['avg_size']} chars, has_table={f['has_table_pct']}%"
        )

print("\n=== ALL OLMOCR FILES WITH SIZE ===")
if all_chunks or olmocr_chunks or art_chunks:
    all_qd = olmocr_chunks + art_chunks
    all_qd_sizes = [wc(c.get("content", "")) for c in all_qd]
    if all_qd_sizes:
        sorted_qd = sorted(all_qd_sizes)
        print(f"Total quydinh chunks: {len(all_qd)}")
        print(
            f"Avg: {sum(all_qd_sizes)/len(all_qd_sizes):.0f} words, P90: {sorted_qd[int(len(sorted_qd)*0.9)]}, P95: {sorted_qd[int(len(sorted_qd)*0.95)]}"
        )
