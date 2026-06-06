import csv, glob, json, os

BASE = r'd:\GR\src\RAG_v2\evaluation\results\e2e_custom_eval'
files = sorted(glob.glob(os.path.join(BASE, '**', 'query_results.csv'), recursive=True))

totals = dict(
    n=0, grounded=0, hallucinated=0, partially_grounded=0,
    ref_correct=0, ref_partial=0, ref_incorrect=0,
    hyde_triggered=0, self_eval_pass=0,
    hit3=0, hit5=0, hit7=0,
    prec3=0.0, prec5=0.0, prec7=0.0,
    rec3=0.0, rec5=0.0, rec7=0.0,
    mrr3=0.0, mrr5=0.0, mrr7=0.0,
    ndcg3=0.0, ndcg5=0.0, ndcg7=0.0,
    latency=0.0, routing=0.0, search=0.0, rerank=0.0, gen=0.0, selfeval=0.0,
)

per_dataset = {}

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def safe_bool(v):
    return str(v).strip().lower() in ('true', '1', 'yes')

for f in files:
    parts = os.path.normpath(f).split(os.sep)
    dataset = parts[-2] if len(parts) >= 2 else 'root'
    if dataset == 'e2e_custom_eval':
        dataset = 'root'

    ds = dict(n=0, grounded=0, hallucinated=0, partially_grounded=0,
              ref_correct=0, ref_partial=0, ref_incorrect=0,
              hit5=0, rec5=0.0, ndcg5=0.0, mrr5=0.0,
              latency=0.0, hyde_triggered=0)

    try:
        with open(f, encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                totals['n'] += 1
                ds['n'] += 1

                faith = row.get('self_eval_faithfulness', '').strip()
                if faith == 'grounded':
                    totals['grounded'] += 1; ds['grounded'] += 1
                elif faith == 'hallucinated':
                    totals['hallucinated'] += 1; ds['hallucinated'] += 1
                elif faith == 'partially_grounded':
                    totals['partially_grounded'] += 1; ds['partially_grounded'] += 1

                ref = row.get('ref_match', '').strip()
                if ref == 'correct':
                    totals['ref_correct'] += 1; ds['ref_correct'] += 1
                elif ref == 'partial':
                    totals['ref_partial'] += 1; ds['ref_partial'] += 1
                elif ref == 'incorrect':
                    totals['ref_incorrect'] += 1; ds['ref_incorrect'] += 1

                if safe_bool(row.get('hyde_triggered', '')):
                    totals['hyde_triggered'] += 1; ds['hyde_triggered'] += 1
                if safe_bool(row.get('self_eval_pass', '')):
                    totals['self_eval_pass'] += 1

                totals['hit3']   += safe_float(row.get('hit@3', 0))
                totals['hit5']   += safe_float(row.get('hit@5', 0))
                ds['hit5']       += safe_float(row.get('hit@5', 0))
                totals['hit7']   += safe_float(row.get('hit@7', 0))
                totals['prec3']  += safe_float(row.get('precision@3', 0))
                totals['prec5']  += safe_float(row.get('precision@5', 0))
                totals['prec7']  += safe_float(row.get('precision@7', 0))
                totals['rec3']   += safe_float(row.get('recall@3', 0))
                totals['rec5']   += safe_float(row.get('recall@5', 0))
                ds['rec5']       += safe_float(row.get('recall@5', 0))
                totals['rec7']   += safe_float(row.get('recall@7', 0))
                totals['mrr3']   += safe_float(row.get('mrr@3', 0))
                totals['mrr5']   += safe_float(row.get('mrr@5', 0))
                ds['mrr5']       += safe_float(row.get('mrr@5', 0))
                totals['mrr7']   += safe_float(row.get('mrr@7', 0))
                totals['ndcg3']  += safe_float(row.get('ndcg@3', 0))
                totals['ndcg5']  += safe_float(row.get('ndcg@5', 0))
                ds['ndcg5']      += safe_float(row.get('ndcg@5', 0))
                totals['ndcg7']  += safe_float(row.get('ndcg@7', 0))
                totals['latency']  += safe_float(row.get('latency_ms', 0))
                ds['latency']      += safe_float(row.get('latency_ms', 0))
                totals['routing']  += safe_float(row.get('routing_time_ms', 0))
                totals['search']   += safe_float(row.get('search_time_ms', 0))
                totals['rerank']   += safe_float(row.get('rerank_time_ms', 0))
                totals['gen']      += safe_float(row.get('generation_time_ms', 0))
                totals['selfeval'] += safe_float(row.get('self_eval_time_ms', 0))
    except Exception as e:
        print(f'ERROR {f}: {e}')

    if ds['n'] > 0:
        per_dataset[dataset] = ds

n = totals['n']
nd = len(per_dataset)
print(f"=== TOTAL QUERIES: {n} across {nd} datasets ===")
print()
print("--- GENERATION QUALITY ---")
print(f"  Grounded (Faithful):    {totals['grounded']:4d} / {n}  = {totals['grounded']/n*100:.1f}%")
print(f"  Partially Grounded:     {totals['partially_grounded']:4d} / {n}  = {totals['partially_grounded']/n*100:.1f}%")
print(f"  Hallucinated:           {totals['hallucinated']:4d} / {n}  = {totals['hallucinated']/n*100:.1f}%")
print(f"  Self-Eval Pass:         {totals['self_eval_pass']:4d} / {n}  = {totals['self_eval_pass']/n*100:.1f}%")
print(f"  Ref-Match Correct:      {totals['ref_correct']:4d} / {n}  = {totals['ref_correct']/n*100:.1f}%")
print(f"  Ref-Match Partial:      {totals['ref_partial']:4d} / {n}  = {totals['ref_partial']/n*100:.1f}%")
print(f"  Ref-Match Incorrect:    {totals['ref_incorrect']:4d} / {n}  = {totals['ref_incorrect']/n*100:.1f}%")
print(f"  HyDE Triggered:         {totals['hyde_triggered']:4d} / {n}  = {totals['hyde_triggered']/n*100:.1f}%")
print()
print("--- RETRIEVAL METRICS (avg across all queries) ---")
print(f"  hit@3={totals['hit3']/n*100:.1f}%   hit@5={totals['hit5']/n*100:.1f}%   hit@7={totals['hit7']/n*100:.1f}%")
print(f"  prec@3={totals['prec3']/n*100:.1f}%  prec@5={totals['prec5']/n*100:.1f}%  prec@7={totals['prec7']/n*100:.1f}%")
print(f"  rec@3={totals['rec3']/n*100:.1f}%   rec@5={totals['rec5']/n*100:.1f}%   rec@7={totals['rec7']/n*100:.1f}%")
print(f"  mrr@3={totals['mrr3']/n*100:.1f}%   mrr@5={totals['mrr5']/n*100:.1f}%   mrr@7={totals['mrr7']/n*100:.1f}%")
print(f"  ndcg@3={totals['ndcg3']/n*100:.1f}%  ndcg@5={totals['ndcg5']/n*100:.1f}%  ndcg@7={totals['ndcg7']/n*100:.1f}%")
print()
print("--- LATENCY (avg per query) ---")
print(f"  Total:    {totals['latency']/n/1000:.2f}s")
print(f"  Routing:  {totals['routing']/n/1000:.2f}s  ({totals['routing']/totals['latency']*100:.1f}% of total)")
print(f"  Search:   {totals['search']/n/1000:.2f}s  ({totals['search']/totals['latency']*100:.1f}% of total)")
print(f"  Rerank:   {totals['rerank']/n/1000:.2f}s  ({totals['rerank']/totals['latency']*100:.1f}% of total)")
print(f"  Gen:      {totals['gen']/n/1000:.2f}s  ({totals['gen']/totals['latency']*100:.1f}% of total)")
print(f"  SelfEval: {totals['selfeval']/n/1000:.2f}s  ({totals['selfeval']/totals['latency']*100:.1f}% of total)")
print()
print("--- WORST DATASETS BY HALLUCINATION+PARTIAL RATE (top 15) ---")
ranked = sorted(
    [(ds, v) for ds, v in per_dataset.items() if v['n'] > 0],
    key=lambda x: (x[1]['hallucinated'] + x[1]['partially_grounded']) / x[1]['n'],
    reverse=True
)[:15]
print(f"  {'Dataset':<58} N  hal  pg  rate  hit5  rec5")
print(f"  {'-'*58} --- --- --- -----  ----  ----")
for ds, v in ranked:
    rate = (v['hallucinated'] + v['partially_grounded']) / v['n'] * 100
    print(f"  {ds[:58]:<58} {v['n']:3d}  {v['hallucinated']:2d}  {v['partially_grounded']:2d}  {rate:4.0f}%  {v['hit5']/v['n']*100:4.0f}%  {v['rec5']/v['n']*100:4.0f}%")
