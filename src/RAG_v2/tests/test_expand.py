import sys
sys.path.insert(0, "/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")

from retrieval.metadata_filters import expand_major_in_query_for_reranking

# Original code expands if not replaced
print("With IT-E6 in string:", expand_major_in_query_for_reranking("môn mạng máy tính IT-E6", "IT-E6"))
print("Without IT-E6 in string:", expand_major_in_query_for_reranking("môn mạng máy tính", "IT-E6"))

