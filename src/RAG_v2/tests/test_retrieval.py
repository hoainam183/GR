import asyncio
from retrieval.multi_collection_search import MultiCollectionSearch
from embedding.bge_m3 import BGEm3Embedder

async def main():
    embedder = BGEm3Embedder()
    search = MultiCollectionSearch.from_collection_names(["ctdt"])
    query = "Mạng máy tính ngành IT-E6 được học trong kì nào"
    bge = embedder.embed_query(query)
    
    hybrid = search.searchers[0][1]
    vecs = hybrid.qdrant.search(bge_m3_query=bge, e5_query=bge, top_k=5)
    kws = hybrid.es.keyword_search(query=query, top_k=10, collection_name="ctdt")
    
    print("--- RAW KEYWORD HITS ---")
    for k in kws:
        print(f"[{k['score']:.2f}] {k['id']} | Code: {k['metadata'].get('course_code')}")
        
    print("\n--- RAW VECTOR HITS ---")
    for v in vecs:
        print(f"[{v['score']:.2f}] {v['id']} | Code: {v['metadata'].get('course_code')}")
        
    res = search.search(query, bge_m3_query=bge, e5_query=bge, active_collections=["ctdt"], top_k=10)
    print("\n--- FULL SEARCH RESULT ---")
    for r in res:
        print(f"[{r['score']:.4f}] {r['id']} | Code: {r['metadata'].get('course_code')}")

if __name__ == "__main__":
    asyncio.run(main())
