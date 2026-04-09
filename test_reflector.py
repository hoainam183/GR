import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'RAG_v2'))
from query.reflection import QueryReflector
from config.settings import Settings

settings = Settings(reflection_provider='lm_studio', reflection_model='test-m', reflection_temperature=0.7)
q = QueryReflector(settings=settings)
print(q.model, q.temperature)
print(q._client.base_url)
