"""Quick smoke tests for new metadata_filters implementation."""
import sys
import json
sys.path.insert(0, '/Users/nam.nguyen/GR')

from src.RAG_v2.retrieval.metadata_filters import (
    build_collection_filters,
    CollectionFilter,
    CtdtFilterExtractor,
    KeHoachFilterExtractor,
    kehoach_recency_bonus,
)

PASS = "\u2713"
FAIL = "\u2717"


def check(label, cond):
    print(f"  [{PASS if cond else FAIL}] {label}")
    if not cond:
        raise AssertionError(label)


print("=== metadata_filters tests ===")

# 1. ctdt with explicit major code in resolved_major
cf = CtdtFilterExtractor().extract("chuong trinh hoc nhu the nao?", resolved_major="IT-E6")
check("ctdt: resolved_major=IT-E6 → 2 queries (major_code + major_name fallback)", len(cf.metadata_es_queries) == 2)
q0 = cf.metadata_es_queries[0]
check("ctdt: first query is null_or_term on major_code", "IT-E6" in json.dumps(q0))
q1 = cf.metadata_es_queries[1]
check("ctdt: second query is null_or_match on major_name", "Vi&#x1ec7;t" in json.dumps(q1, ensure_ascii=False) or "Nhật" in json.dumps(q1, ensure_ascii=False) or "Nh" in json.dumps(q1, ensure_ascii=False))

# 2. ctdt resolved_major as name string
cf2 = CtdtFilterExtractor().extract("", resolved_major="Viet Nhat")
check("ctdt: resolved_major as partial name 'Viet Nhat' → no match → falls back to query regex (empty query → no filter)", cf2.is_empty)

# resolved major with Vietnamese
cf2b = CtdtFilterExtractor().extract("", resolved_major="việt nhật")
check("ctdt: resolved_major='việt nhật' → detects IT-E6", not cf2b.is_empty)

# 3. ctdt with no major → no filter
cf3 = CtdtFilterExtractor().extract("dieu kien tot nghiep")
check("ctdt: no major in query → is_empty", cf3.is_empty)

# 4. kehoach - no date → no filter (default search all)
cf4 = KeHoachFilterExtractor().extract("thong bao hoc bong")
check("kehoach: no date → is_empty", cf4.is_empty)

# 5. kehoach - year only
cf5 = KeHoachFilterExtractor().extract("hoc bong nam 2025")
check("kehoach: year 2025 → has filter", not cf5.is_empty)
check("kehoach: year wildcard contains 2025", "2025" in json.dumps(cf5.metadata_es_queries[0]))

# 6. kehoach - month + year
cf6 = KeHoachFilterExtractor().extract("thong bao thang 3 nam 2026")
check("kehoach: month+year → has filter", not cf6.is_empty)
check("kehoach: wildcard */3/2026", "*/3/2026" in json.dumps(cf6.metadata_es_queries[0]))

# 7. kehoach recency bonus
from datetime import datetime
today = datetime.now()
doc_new = {"collection": "kehoach", "metadata": {"date_str": f"1/{today.month}/{today.year}"}}
doc_old = {"collection": "kehoach", "metadata": {"date_str": "1/1/2020"}}
doc_other = {"collection": "stsv", "metadata": {}}
check("recency: today's doc has max bonus", kehoach_recency_bonus(doc_new) > 0.04)
check("recency: 5yr-old doc has near-zero bonus", kehoach_recency_bonus(doc_old) < 0.01)
check("recency: non-kehoach doc = 0", kehoach_recency_bonus(doc_other) == 0.0)

# 8. build_collection_filters with resolved_major
filters = build_collection_filters("tin chi", ["ctdt", "quydinh", "stsv", "kehoach"], resolved_major="IT1")
check("build: ctdt filtered with IT1", not filters["ctdt"].is_empty)
check("build: quydinh filtered with IT1", not filters["quydinh"].is_empty)
check("build: stsv not filtered", filters["stsv"].is_empty)
check("build: kehoach not filtered (no date in query)", filters["kehoach"].is_empty)

# 9. quydinh null-or-term
from src.RAG_v2.retrieval.metadata_filters import QuyDinhFilterExtractor
cf9 = QuyDinhFilterExtractor().extract("quy dinh ngoai ngu", resolved_major="IT-E15")
check("quydinh: resolved_major=IT-E15 → 1 query", len(cf9.metadata_es_queries) == 1)
check("quydinh: query contains IT-E15", "IT-E15" in json.dumps(cf9.metadata_es_queries[0]))

print()
print("All tests PASSED!")
