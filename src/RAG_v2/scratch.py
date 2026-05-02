import sys
sys.path.insert(0, "/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")
from retrieval.metadata_filters import extract_major_codes, _normalise_major_text
print("extract_major_codes:", extract_major_codes("ITE6"))
print("normalise_major_text:", _normalise_major_text("ITE6"))
print("extract_major_codes('IT-E6'):", extract_major_codes("IT-E6"))
