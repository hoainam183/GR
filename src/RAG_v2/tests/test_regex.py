import re

text1 = "Kế hoạch năm học 2025-2026: Học kỳ I bắt đầu từ..."
text2 = "Đăng ký học tập HK2 năm 2023 - 2024"

# regex for semester
sem_regex = re.compile(r'(học kỳ\s*(?:[IVX]+|\d+)|\bhk\s*\d+|kỳ\s*\d+)', re.IGNORECASE)
year_regex = re.compile(r'(năm học\s*\d{4}\s*-\s*\d{4}|năm\s*\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*\d{4})', re.IGNORECASE)

for t in [text1, text2]:
    s = sem_regex.search(t)
    y = year_regex.search(t)
    print(t)
    if s: print("  Sem:", s.group(0))
    if y: print("  Year:", y.group(0))

