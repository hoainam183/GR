import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { retrievalSearch, RetrievalSearchResponse } from '@/services/chatApi';
import { DocRow } from '@/components/trace/DocRow';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Search,
  ArrowLeft,
  Loader2,
  Info,
  Database,
  Filter,
  BarChart4,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const COLLECTIONS = ['ctdt', 'quydinh', 'stsv', 'kehoach', 'test'];

const safeNumber = (value: unknown, fallback = 0): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback;

const formatWeight = (value: unknown): string => {
  if (typeof value === 'number' && Number.isFinite(value)) return value.toFixed(2);
  if (typeof value === 'string' && value.trim()) return value;
  return '-';
};

export default function RetrievalPage() {
  const [query, setQuery] = useState('');
  const [selectedCollections, setSelectedCollections] = useState<string[]>(['ctdt']);
  const [major, setMajor] = useState('');
  const [cohort, setCohort] = useState('');
  const [topK, setTopK] = useState(5);
  const [rerank, setRerank] = useState(true);
  
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RetrievalSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await retrievalSearch(
        query,
        selectedCollections,
        major || undefined,
        cohort || undefined,
        topK,
        rerank
      );
      setResult(res);
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Search failed');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleCollection = (col: string) => {
    setSelectedCollections(prev =>
      prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
    );
  };

  const normalizedResult = result
    ? {
        latencyMs: safeNumber(result.latency_ms),
        totalFound: safeNumber(result.total_found, Array.isArray(result.results) ? result.results.length : 0),
        fusionWeights:
          result.fusion_weights && typeof result.fusion_weights === 'object'
            ? result.fusion_weights
            : {},
        appliedFilters: Array.isArray(result.applied_filters) ? result.applied_filters : [],
        collectionResults: Array.isArray(result.collection_results) ? result.collection_results : [],
        results: Array.isArray(result.results) ? result.results : [],
      }
    : null;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center gap-4">
          <Link to="/chat" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" /> Chat
          </Link>
          <div className="h-4 w-px bg-border" />
          <Link to="/trace" className="text-sm text-muted-foreground hover:text-foreground">Trace</Link>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-primary" />
            <h1 className="text-sm font-semibold">Retrieval Sandbox</h1>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Controls Column */}
          <div className="md:col-span-1 space-y-6">
            <div className="border rounded-xl bg-card p-5 space-y-4">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <Database className="w-4 h-4" /> Collections
              </h2>
              <div className="space-y-2">
                {COLLECTIONS.map(col => (
                  <div key={col} className="flex items-center space-x-2">
                    <Checkbox 
                      id={`col-${col}`} 
                      checked={selectedCollections.includes(col)}
                      onCheckedChange={() => toggleCollection(col)}
                    />
                    <label 
                      htmlFor={`col-${col}`} 
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 capitalize"
                    >
                      {col}
                    </label>
                  </div>
                ))}
              </div>

              <div className="pt-4 space-y-4 border-t">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <Filter className="w-4 h-4" /> Filters
                </h2>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground uppercase font-semibold">Major Code</label>
                  <Input 
                    placeholder="e.g. IT1, IT-E7" 
                    value={major} 
                    onChange={e => setMajor(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground uppercase font-semibold">Cohort</label>
                  <Input 
                    placeholder="e.g. K67" 
                    value={cohort} 
                    onChange={e => setCohort(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>

              <div className="pt-4 space-y-4 border-t">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4" /> Options
                </h2>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium">Top K</label>
                  <Input 
                    type="number" 
                    value={topK} 
                    onChange={e => setTopK(parseInt(e.target.value) || 5)}
                    className="h-8 w-16 text-xs text-center"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="rerank" 
                    checked={rerank}
                    onCheckedChange={(checked) => setRerank(!!checked)}
                  />
                  <label htmlFor="rerank" className="text-sm font-medium">Enable Reranking</label>
                </div>
              </div>
            </div>
          </div>

          {/* Search Column */}
          <div className="md:col-span-2 space-y-6">
            <div className="border rounded-xl bg-card p-5 space-y-4">
              <div className="space-y-1">
                <h2 className="text-base font-semibold">Query</h2>
                <p className="text-xs text-muted-foreground">Directly test the retrieval engine without generating an LLM response.</p>
              </div>
              <div className="relative">
                <Textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSearch())}
                  placeholder="Enter query to test retrieval..."
                  className="min-h-[100px] resize-none pr-12 text-sm"
                  disabled={isLoading}
                />
                <Button
                  className="absolute bottom-3 right-3"
                  onClick={handleSearch}
                  disabled={isLoading || !query.trim()}
                >
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                  {isLoading ? 'Searching...' : 'Search'}
                </Button>
              </div>
            </div>

            {error && (
              <div className="border border-red-200 bg-red-50 dark:bg-red-950/20 rounded-xl p-4 text-sm text-red-600">
                {error}
              </div>
            )}

            {normalizedResult && (
              <div ref={resultRef} className="space-y-6">
                {/* Stats Row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="border rounded-xl bg-card p-3 space-y-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-bold">Latency</p>
                    <p className="text-lg font-semibold text-primary">{normalizedResult.latencyMs.toFixed(0)}ms</p>
                  </div>
                  <div className="border rounded-xl bg-card p-3 space-y-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-bold">Total Docs</p>
                    <p className="text-lg font-semibold">{normalizedResult.totalFound}</p>
                  </div>
                  <div className="border rounded-xl bg-card p-3 space-y-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-bold">Fusion</p>
                    <p className="text-xs font-mono">
                      V:{formatWeight(normalizedResult.fusionWeights.vector)} K:{formatWeight(normalizedResult.fusionWeights.keyword)}
                    </p>
                  </div>
                  <div className="border rounded-xl bg-card p-3 space-y-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-bold">Filters</p>
                    <div className="flex gap-1 flex-wrap">
                      {normalizedResult.appliedFilters.map(f => (
                        <Badge key={f.collection} variant={f.applied ? "default" : "outline"} className="text-[9px] px-1 h-4">
                          {f.collection}:{f.applied ? '✓' : '✗'}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Filter Details */}
                {normalizedResult.appliedFilters.some(f => f.applied) && (
                  <div className="border rounded-xl bg-muted/30 p-4 space-y-2">
                    <h3 className="text-xs font-bold uppercase flex items-center gap-2">
                      <Filter className="w-3 h-3" /> Metadata Pre-filters Applied
                    </h3>
                    <div className="space-y-1">
                      {normalizedResult.appliedFilters.filter(f => f.applied).map(f => (
                        <div key={f.collection} className="text-xs flex items-center gap-2">
                          <span className="font-semibold w-20">{f.collection}:</span>
                          <span className="text-muted-foreground">{f.filter_desc}</span>
                          <Badge variant="secondary" className="ml-auto">{safeNumber(f.matched_ids)} IDs</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Collection Counts */}
                <div className="border rounded-xl bg-card p-4 space-y-2">
                  <h3 className="text-xs font-bold uppercase flex items-center gap-2">
                    <BarChart4 className="w-3 h-3" /> Raw Retrieval Counts
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {normalizedResult.collectionResults.map(cr => (
                      <div key={cr.collection} className="space-y-1">
                        <p className="text-[11px] font-semibold capitalize">{cr.collection}</p>
                        <div className="flex gap-2">
                          <div className="text-[10px] bg-violet-500/10 text-violet-600 px-1.5 rounded">V: {safeNumber(cr.vector_count)}</div>
                          <div className="text-[10px] bg-amber-500/10 text-amber-600 px-1.5 rounded">K: {safeNumber(cr.keyword_count)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Results List */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold">Retrieved Documents</h3>
                  <div className="space-y-3">
                    {normalizedResult.results.map((doc, i) => (
                      <DocRow key={i} doc={doc} rank={i + 1} showRerank={rerank} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
