import csv, io, sys

cls_raw = """id,question,question_type,difficulty,target_collections,relevant_chunk_ids,retrieved_chunk_ids,routing_time_ms,retrieval_time_ms,total_time_ms,fallback_triggered,intent,hit@3,precision@3,recall@3,mrr@3,ndcg@3,hit@5,precision@5,recall@5,mrr@5,ndcg@5,hit@7,precision@7,recall@7,mrr@7,ndcg@7
ITE6_simple_001,q,simple,easy,ctdt,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,80,4789,4869,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_002,q,simple,easy,ctdt,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,"b4ac3a41-3b25-4fa3-979c-c5463e1d2413,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",74,4431,4506,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_003,q,simple,easy,ctdt,a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc,"a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc,55194527-c15c-41ba-82a3-427365994092,774296a4-4fda-4b32-80ee-e5e64ec9ff74,979296ed-eb5c-4483-9d15-56306fd3070b,0a7cf49c-c799-4546-b690-c169d9c0afff",65,4681,4747,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_004,q,simple,easy,ctdt,5de1a805-29f4-42c6-bcc8-c946890e9e6a,"5de1a805-29f4-42c6-bcc8-c946890e9e6a,55250ef6-68c2-4f53-88d1-ed5db8b8f0e0,a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc,44e614bc-1430-4d42-b19d-3191220627a6",84,3618,3703,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_005,q,simple,easy,ctdt,c80b7a88-fe86-46cb-9753-400bfe3241f1,"55194527-c15c-41ba-82a3-427365994092,656a9517-313c-413c-80f7-36eb5d90b889,774296a4-4fda-4b32-80ee-e5e64ec9ff74,f1137bc9-d778-4e90-a26c-cbcb9dcdb34b,0a7cf49c-c799-4546-b690-c169d9c0afff",869,4585,5455,True,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_simple_006,q,simple,easy,ctdt,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,"b4ac3a41-3b25-4fa3-979c-c5463e1d2413,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",584,4077,4662,False,rag,1.0,0.3333,1.0,0.5,0.6309,1.0,0.2,1.0,0.5,0.6309,1.0,0.1429,1.0,0.5,0.6309
ITE6_simple_007,q,simple,easy,ctdt,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,"2874d4db-8be7-4c58-8328-5c07b9d8c411,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",67,5050,5117,False,rag,1.0,0.3333,1.0,0.5,0.6309,1.0,0.2,1.0,0.5,0.6309,1.0,0.1429,1.0,0.5,0.6309
ITE6_simple_008,q,simple,easy,ctdt,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,"55250ef6-68c2-4f53-88d1-ed5db8b8f0e0,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,3373e3f6-472c-4963-b101-928e3701ff68",70,4655,4726,False,rag,1.0,0.3333,1.0,0.5,0.6309,1.0,0.2,1.0,0.5,0.6309,1.0,0.1429,1.0,0.5,0.6309
ITE6_simple_009,q,simple,easy,ctdt,5df876b8-b84f-45de-beaf-503cc694c190,"b4ac3a41-3b25-4fa3-979c-c5463e1d2413,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",69,4671,4741,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_simple_010,q,simple,easy,ctdt,f0b1eec3-6326-45a5-b924-f2816e74e633,f0b1eec3-6326-45a5-b924-f2816e74e633,69,4854,4923,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_011,q,simple,easy,ctdt,f0b1eec3-6326-45a5-b924-f2816e74e633,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,732,4804,5537,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_simple_012,q,simple,easy,ctdt,2874d4db-8be7-4c58-8328-5c07b9d8c411,2874d4db-8be7-4c58-8328-5c07b9d8c411,766,3833,4600,True,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_013,q,simple,easy,ctdt,2874d4db-8be7-4c58-8328-5c07b9d8c411,"2874d4db-8be7-4c58-8328-5c07b9d8c411,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",78,4966,5045,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_014,q,simple,easy,ctdt,0b478904-c0fd-48b6-b12a-d9d929c1a3c6,"0b478904-c0fd-48b6-b12a-d9d929c1a3c6,74c8f077-a90e-4d6d-9a34-9a3e0b5b29da,6efb75c6-8aff-4841-b753-aa4ea33bd2df,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,7bd9d9bb-b603-4003-96bb-2b6d55ca2ae2",79,4718,4797,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_015,q,simple,easy,ctdt,b1721449-4322-4381-97ff-8975f3cd5364,"b1721449-4322-4381-97ff-8975f3cd5364,b0f8ab0a-9552-4f0e-bf46-0f15a2e7fb32,6efb75c6-8aff-4841-b753-aa4ea33bd2df,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",89,4395,4484,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_016,q,simple,easy,ctdt,7bd9d9bb-b603-4003-96bb-2b6d55ca2ae2,"7bd9d9bb-b603-4003-96bb-2b6d55ca2ae2,b4ac3a41-3b25-4fa3-979c-c5463e1d2413,1ab61091-ceb9-4b43-9652-de31fe92b1bf",65,4464,4530,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_simple_017,q,simple,easy,ctdt,073063fc-405f-4be2-b0c0-b753cb562614,,83,503,587,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_simple_018,q,simple,easy,ctdt,83e689ec-40bb-469b-bc89-9450a303a4c3,"83e689ec-40bb-469b-bc89-9450a303a4c3,5db606ed-62e7-4478-95ed-62f59016c811,c1a4519e-cdb0-4dad-be27-fbeb90a85e46",31,4273,4305,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_multi_hop_001,q,multi_hop,medium,ctdt,"a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc,c80b7a88-fe86-46cb-9753-400bfe3241f1,2874d4db-8be7-4c58-8328-5c07b9d8c411","55194527-c15c-41ba-82a3-427365994092,f1137bc9-d778-4e90-a26c-cbcb9dcdb34b,774296a4-4fda-4b32-80ee-e5e64ec9ff74,93f3bddc-080f-406f-aead-eaf0f456b03d,a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc",136,4437,4574,False,rag,0.0,0.0,0.0,0.0,0.0,1.0,0.2,0.3333,0.2,0.1815,1.0,0.1429,0.3333,0.2,0.1815
ITE6_multi_hop_002,q,multi_hop,medium,ctdt,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,c1a4519e-cdb0-4dad-be27-fbeb90a85e46,71,3589,3660,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_multi_hop_003,q,multi_hop,medium,ctdt,"f0b1eec3-6326-45a5-b924-f2816e74e633,2874d4db-8be7-4c58-8328-5c07b9d8c411",a3b83b7b-06b9-4faf-a59c-a0ed5ac841dc,74,4521,4595,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_multi_hop_004,q,multi_hop,medium,ctdt,"6efb75c6-8aff-4841-b753-aa4ea33bd2df,073063fc-405f-4be2-b0c0-b753cb562614","073063fc-405f-4be2-b0c0-b753cb562614,1f1630d9-4961-41f5-9e9d-5dedff69686d,161f8be9-40ab-4de6-8fb6-ece1125b3e91",83,3084,3168,False,rag,1.0,0.3333,0.5,1.0,0.6131,1.0,0.2,0.5,1.0,0.6131,1.0,0.1429,0.5,1.0,0.6131
ITE6_multi_hop_005,q,multi_hop,medium,ctdt,f9220ebd-00f6-4356-83bb-00d6e351aec2,"639e992b-0106-4e19-a283-9a3fc75c1b73,f9220ebd-00f6-4356-83bb-00d6e351aec2",71,3120,3191,False,rag,1.0,0.3333,1.0,0.5,0.6309,1.0,0.2,1.0,0.5,0.6309,1.0,0.1429,1.0,0.5,0.6309
ITE6_multi_hop_006,q,multi_hop,medium,ctdt,"b1721449-4322-4381-97ff-8975f3cd5364,83e689ec-40bb-469b-bc89-9450a303a4c3","3373e3f6-472c-4963-b101-928e3701ff68,ad1ff06c-b535-42c7-aa18-d8862bf69164,55250ef6-68c2-4f53-88d1-ed5db8b8f0e0",65,4494,4559,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
ITE6_multi_hop_007,q,multi_hop,medium,ctdt,5df876b8-b84f-45de-beaf-503cc694c190,5df876b8-b84f-45de-beaf-503cc694c190,79,4166,4245,False,rag,1.0,0.3333,1.0,1.0,1.0,1.0,0.2,1.0,1.0,1.0,1.0,0.1429,1.0,1.0,1.0
ITE6_multi_hop_008,q,multi_hop,medium,ctdt,6efb75c6-8aff-4841-b753-aa4ea33bd2df,,91,4328,4420,False,rag,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0"""

import os

e2e_path = r"d:\GR\src\RAG_v2\evaluation\results\e2e_custom_eval\ITE6_rag_evaluation_dataset_no_parent_evidence\query_results.csv"
with open(e2e_path, encoding="utf-8-sig") as f:
    e2e_data = f.read()

e2e = {r["id"]: r for r in csv.DictReader(io.StringIO(e2e_data))}
cls = {r["id"]: r for r in csv.DictReader(io.StringIO(cls_raw))}

print(f"CLS rows: {len(cls)} | E2E rows: {len(e2e)}")
print(f"E2E columns: {list(next(iter(e2e.values())).keys())}")
print()

regressions, recoveries, shared_miss, shared_hit = [], [], [], []
for qid in sorted(e2e.keys()):
    c = cls.get(qid)
    e = e2e[qid]
    ch5 = float(c["hit@5"]) if c else -1
    eh5 = float(e["hit@5"])
    if ch5 == 1.0 and eh5 == 0.0:
        regressions.append(qid)
    elif ch5 == 0.0 and eh5 == 1.0:
        recoveries.append(qid)
    elif ch5 == 0.0 and eh5 == 0.0:
        shared_miss.append(qid)
    else:
        shared_hit.append(qid)

print("=== REGRESSIONS (Classifier HIT -> E2E MISS) ===")
for qid in regressions:
    c = cls[qid]
    e = e2e[qid]
    print(f"  {qid}")
    print(f"    relevant : {c['relevant_chunk_ids']}")
    print(f"    CLS retr : {c['retrieved_chunk_ids']}")
    print(f"    E2E retr : {e['retrieved_chunk_ids']}")
    route = e.get("route", "?")
    mode = e.get("mode", "?")
    rtms = e.get("routing_time_ms", "?")
    nsrc = e.get("num_sources", "?")
    print(
        f"    E2E route/mode: {route}/{mode} | routing_ms: {rtms} | n_src: {nsrc}"
    )
    print()

print("=== RECOVERIES (Classifier MISS -> E2E HIT) ===")
for qid in recoveries:
    c = cls[qid]
    e = e2e[qid]
    print(f"  {qid}")
    print(f"    relevant : {c['relevant_chunk_ids']}")
    print(f"    CLS retr : {c['retrieved_chunk_ids']}")
    print(f"    E2E retr : {e['retrieved_chunk_ids']}")
    nsrc = e.get("num_sources", "?")
    print(f"    n_src: {nsrc}")
    print()

print("=== SHARED MISSES (both miss) ===")
for qid in shared_miss:
    c = cls[qid]
    e = e2e[qid]
    print(f"  {qid}")
    print(f"    relevant : {c['relevant_chunk_ids']}")
    print(f"    CLS retr : {c['retrieved_chunk_ids']}")
    print(f"    E2E retr : {e['retrieved_chunk_ids']}")
    print()

cls_hit = sum(1 for qid in e2e if float(cls[qid]["hit@5"]) == 1.0)
e2e_hit = sum(1 for qid in e2e if float(e2e[qid]["hit@5"]) == 1.0)
print(
    f"Summary: Regressions={len(regressions)}, Recoveries={len(recoveries)}, Shared_miss={len(shared_miss)}, Shared_hit={len(shared_hit)}"
)
print(f"Classifier hit@5: {cls_hit}/{len(e2e)} = {cls_hit/len(e2e):.1%}")
print(f"E2E hit@5:        {e2e_hit}/{len(e2e)} = {e2e_hit/len(e2e):.1%}")
