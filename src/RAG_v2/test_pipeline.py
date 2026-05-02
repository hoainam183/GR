import sys
from pathlib import Path

# Add src/RAG_v2 to path
sys.path.insert(0, str(Path("/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")))

from retrieval.metadata_filters import strip_major_from_query_for_retrieval
from query.reflection import _extract_entities

query = "tôi muốn tìm hiểu về ngành IT1"
entities = _extract_entities(query)
print("Entities:", entities)
major_code = entities.get("major_code")
stripped = strip_major_from_query_for_retrieval(query, major_code)
print("Stripped:", stripped)
