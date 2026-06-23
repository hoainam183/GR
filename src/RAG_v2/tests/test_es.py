import json
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

print("--- ctdt: Mạng máy tính ---")
res = es.search(index="ctdt", query={"match": {"content": "Mạng máy tính"}}, size=5)
for hit in res['hits']['hits']:
    source = hit['_source']
    print(f"Content: {source.get('content')[:100]}...")
    print(f"  course_code: {source.get('course_code')}")
    print(f"  course_name: {source.get('course_name')}")
