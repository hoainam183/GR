import re

MAJOR_CODE_TO_NAME = {
    "IT-E6": "Công nghệ thông tin Việt - Nhật",
    "IT1": "Khoa học máy tính",
}

def _build_major_labels(major_code):
    return [major_code] # simplified for testing

def expand_major_in_query_for_reranking(query: str, resolved_major: str) -> str:
    major_code = resolved_major
    major_name = MAJOR_CODE_TO_NAME.get(major_code)
    if not major_name: return query
    
    if major_name.lower() in query.lower():
        return query
        
    labels = _build_major_labels(major_code)
    
    for label in labels:
        # We should match word boundaries if possible to avoid replacing sub-words
        # But major codes like "IT-E6" might have hyphens.
        # Let's just do a simple replace first.
        pattern = re.compile(r'\b' + re.escape(label) + r'\b', re.IGNORECASE)
        if pattern.search(query):
            return pattern.sub(major_name, query)
            
    return query

queries = [
    "Tôi muốn tìm hiểu về chương trình đào tạo ngành IT1",
    "ngành IT-E6 có gì khác",
]

for q in queries:
    expanded = expand_major_in_query_for_reranking(q, "IT1" if "IT1" in q else "IT-E6")
    print(f"'{q}' -> '{expanded}'")
