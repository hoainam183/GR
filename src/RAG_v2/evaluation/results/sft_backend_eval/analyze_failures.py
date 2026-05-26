"""Analyze failure patterns in incorrect_results.json"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import Counter, defaultdict

with open("incorrect_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total incorrect items: {len(data)}")

# 1. Judge match distribution
judge_matches = Counter(item.get("judge_match", "unknown") for item in data)
print(f"\n=== Judge Match Distribution ===")
for k, v in judge_matches.most_common():
    print(f"  {k}: {v}")

# 2. Root cause analysis from rerank_trace
rerank_zero = 0
rerank_low = 0
rerank_ok = 0
no_sources_pregeneration = 0
web_fallback_used = 0
self_eval_failed_count = 0
context_zero_chars = 0

for item in data:
    trace = item.get("response_trace") or {}
    rerank = trace.get("rerank_trace") or {}
    qgate = trace.get("answer_quality_gate") or {}
    ctx = trace.get("context_trace") or {}
    
    passing = rerank.get("rerank_passing_count", -1)
    if passing == 0:
        rerank_zero += 1
    elif passing <= 2:
        rerank_low += 1
    else:
        rerank_ok += 1
    
    pre_reasons = qgate.get("pre_generation_reasons", [])
    if "no_sources" in pre_reasons:
        no_sources_pregeneration += 1
    
    if qgate.get("pre_generation_web_used"):
        web_fallback_used += 1
    
    if qgate.get("self_eval_failed"):
        self_eval_failed_count += 1
    
    if ctx.get("context_chars", 1) == 0:
        context_zero_chars += 1

print(f"\n=== Retrieval Quality ===")
print(f"  Rerank passing=0 (total retrieval failure): {rerank_zero}")
print(f"  Rerank passing<=2 (low retrieval): {rerank_low}")
print(f"  Rerank passing>2 (adequate retrieval): {rerank_ok}")
print(f"  Context chars = 0 (no context given to LLM): {context_zero_chars}")
print(f"  Pre-gen 'no_sources' triggered: {no_sources_pregeneration}")
print(f"  Pre-gen web fallback used: {web_fallback_used}")
print(f"  Self-eval failed: {self_eval_failed_count}")

# 3. Fusion weight distribution
fusion_reasons = Counter()
for item in data:
    trace = item.get("response_trace") or {}
    fw = trace.get("fusion_weights") or {}
    reason = fw.get("reason", "unknown")
    fusion_reasons[reason] += 1

print(f"\n=== Fusion Weight Reasons ===")
for k, v in fusion_reasons.most_common():
    print(f"  {k}: {v}")

# 4. Source freshness (expected_doc_hit)
doc_hit_false = sum(1 for item in data if not item.get("metrics", {}).get("expected_doc_hit", True))
article_hit_false = sum(1 for item in data if not item.get("metrics", {}).get("expected_article_hit", True))
print(f"\n=== Source Accuracy ===")
print(f"  expected_doc_hit = false: {doc_hit_false}")
print(f"  expected_article_hit = false: {article_hit_false}")
print(f"  citation_text_hit = false: {sum(1 for item in data if not item.get('metrics', {}).get('citation_text_hit', True))}")

# 5. Web fallback patterns
tools_used = Counter()
for item in data:
    trace = item.get("response_trace") or {}
    used = trace.get("tools_used") or []
    for t in used:
        tools_used[t] += 1
    if not used:
        tools_used["none"] += 1

print(f"\n=== Tools Used ===")
for k, v in tools_used.most_common():
    print(f"  {k}: {v}")

# 6. Doc type distribution  
doc_types = Counter(item.get("doc_type", "unknown") for item in data)
print(f"\n=== Doc Type Distribution ===")
for k, v in doc_types.most_common():
    print(f"  {k}: {v}")

# 7. Answer quality gate status
answer_statuses = Counter()
for item in data:
    trace = item.get("response_trace") or {}
    qgate = trace.get("answer_quality_gate") or {}
    status = qgate.get("answer_status", "unknown")
    answer_statuses[status] += 1

print(f"\n=== Answer Status ===")
for k, v in answer_statuses.most_common():
    print(f"  {k}: {v}")

# 8. Judge reason keyword analysis
reason_keywords = Counter()
for item in data:
    reason = item.get("judge_reason", "")
    if "quy chế năm 2023" in reason.lower() or "quy chế 2023" in reason.lower() or "năm 2023" in reason.lower():
        reason_keywords["wrong_year_2023"] += 1
    if "mâu thuẫn" in reason.lower():
        reason_keywords["contradictory"] += 1
    if "không tìm thấy" in reason.lower() or "không cung cấp" in reason.lower() or "không nêu rõ" in reason.lower():
        reason_keywords["missing_info"] += 1
    if "thêm thông tin" in reason.lower() or "mở rộng" in reason.lower() or "ngoại lệ" in reason.lower():
        reason_keywords["excessive_info"] += 1
    if "cũ" in reason.lower() or "2019" in reason or "năm 2022" in reason:
        reason_keywords["outdated_source"] += 1
    if "chung chung" in reason.lower() or "không chính xác" in reason.lower():
        reason_keywords["vague_inaccurate"] += 1
    if "web" in reason.lower() or "trang web" in reason.lower():
        reason_keywords["web_source_issue"] += 1
    if "halluc" in reason.lower() or "bịa" in reason.lower() or "sai" in reason.lower():
        reason_keywords["hallucination"] += 1

print(f"\n=== Judge Reason Keywords ===")
for k, v in reason_keywords.most_common():
    print(f"  {k}: {v}")

# 9. Collection routing analysis
routing_targets = Counter()
for item in data:
    targets = item.get("target_collections") or []
    routing_targets[tuple(sorted(targets))] += 1

print(f"\n=== Target Collections ===")
for k, v in routing_targets.most_common(10):
    print(f"  {list(k)}: {v}")

# 10. Atomic fact coverage distribution
afc_bins = defaultdict(int)
for item in data:
    afc = item.get("metrics", {}).get("atomic_fact_coverage", -1)
    if afc == 0.0:
        afc_bins["0.0 (no facts)"] += 1
    elif afc <= 0.5:
        afc_bins["0.01-0.5 (low)"] += 1
    elif afc <= 0.99:
        afc_bins["0.5-0.99 (partial)"] += 1
    elif afc == 1.0:
        afc_bins["1.0 (full)"] += 1

print(f"\n=== Atomic Fact Coverage ===")
for k, v in sorted(afc_bins.items()):
    print(f"  {k}: {v}")
