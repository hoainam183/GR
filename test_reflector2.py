import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'RAG_v2'))
from query.reflection import QueryReflector

q = QueryReflector()
print(q.model, q.temperature)
print(q._client.base_url)
