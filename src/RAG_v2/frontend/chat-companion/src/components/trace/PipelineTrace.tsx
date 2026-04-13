/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from 'react';
import { ChatResponse, RetrievedDocument } from '@/types/chat';
import { Badge } from '@/components/ui/badge';
import {
  MessageSquare,
  GitBranch,
  RefreshCw,
  Layers,
  Cpu,
  Search,
  ArrowDownUp,
  Sparkles,
  ShieldCheck,
  Clock,
  ChevronDown,
  ChevronUp,
  ArrowDown,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ─────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────── */

const COLLECTION_COLORS: Record<string, string> = {
  quydinh: 'bg-blue-500',
  ctdt: 'bg-violet-500',
  kehoach: 'bg-amber-500',
  stsv: 'bg-emerald-500',
};
const COLLECTION_LABELS: Record<string, string> = {
  quydinh: 'Quy Định',
  ctdt: 'Chương Trình ĐT',
  kehoach: 'Kế Hoạch',
  stsv: 'Sinh Viên',
};

function fmtMs(ms?: number) {
  if (ms === undefined || ms === null) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function TimingBadge({ ms }: { ms?: number }) {
  const label = fmtMs(ms);
  if (!label) return null;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
      <Clock className="w-3 h-3" />
      {label}
    </span>
  );
}

function StatusDot({ status }: { status: 'done' | 'skipped' | 'triggered' }) {
  if (status === 'done')
    return <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />;
  if (status === 'triggered')
    return <CheckCircle2 className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />;
  return <MinusCircle className="w-4 h-4 text-muted-foreground/40 shrink-0 mt-0.5" />;
}

function ScoreBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
      <div
        className="h-full bg-primary rounded-full transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Single layer card
───────────────────────────────────────────────────────── */

interface LayerCardProps {
  icon: React.ReactNode;
  title: string;
  badge?: React.ReactNode;
  timing?: number;
  status: 'done' | 'skipped' | 'triggered';
  children: React.ReactNode;
  defaultOpen?: boolean;
  visible?: boolean;
}

function LayerCard({
  icon,
  title,
  badge,
  timing,
  status,
  children,
  defaultOpen = true,
  visible = true,
}: LayerCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={cn(
        'border rounded-xl overflow-hidden transition-all duration-500',
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none',
        status === 'skipped' && 'opacity-50',
      )}
    >
      {/* Header */}
      <button
        className="w-full flex items-center gap-3 p-4 bg-card hover:bg-muted/50 transition-colors text-left"
        onClick={() => setOpen(!open)}
        disabled={status === 'skipped'}
      >
        <StatusDot status={status} />
        <span className="text-muted-foreground shrink-0">{icon}</span>
        <span className="font-medium text-sm flex-1">{title}</span>
        {badge}
        <TimingBadge ms={timing} />
        {status !== 'skipped' && (
          open ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
          )
        )}
      </button>

      {/* Body */}
      {status !== 'skipped' && open && (
        <div className="p-4 border-t bg-background text-sm space-y-3">{children}</div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Document pill
───────────────────────────────────────────────────────── */

function DocRow({
  doc,
  rank,
  showRerank,
}: {
  doc: RetrievedDocument;
  rank: number;
  showRerank: boolean;
}) {
  const [open, setOpen] = useState(false);
  const collection = (doc.metadata?.collection as string) || '';
  const color = COLLECTION_COLORS[collection] || 'bg-gray-500';
  const title = (doc.metadata?.title as string) || doc.metadata?.source || '—';
  const score = doc.score ?? 0;

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-muted/30 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="text-xs font-mono text-muted-foreground w-5 text-right shrink-0">
          #{rank}
        </span>
        <span className={cn('w-2 h-2 rounded-full shrink-0', color)} />
        <span className="flex-1 truncate text-xs">{title}</span>
        <span className="text-xs text-muted-foreground shrink-0 font-mono">
          {showRerank ? `rerank: ${score.toFixed(4)}` : `score: ${score.toFixed(4)}`}
        </span>
        {collection && (
          <Badge variant="secondary" className="text-xs shrink-0 capitalize">
            {COLLECTION_LABELS[collection] || collection}
          </Badge>
        )}
        {open ? (
          <ChevronUp className="w-3 h-3 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 text-xs text-muted-foreground space-y-1 border-t bg-muted/20">
          <div className="max-h-40 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
            {doc.content}
          </div>
          {Object.keys(doc.metadata || {}).length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {Object.entries(doc.metadata).map(([k, v]) => (
                <span key={k} className="bg-muted px-1.5 py-0.5 rounded text-xs">
                  <span className="font-medium">{k}:</span>{' '}
                  {Array.isArray(v) ? v.join(', ') : String(v ?? '—')}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Main PipelineTrace component
───────────────────────────────────────────────────────── */

interface Props {
  response: ChatResponse;
  question: string;
}

export default function PipelineTrace({ response, question }: Props) {
  const t = response.timings_ms ?? {};

  // Determine which layers are present
  const hasTier3 = !!t['tier3_domain_fallback'];
  const hasReflection = !!response.reflected_question && response.reflected_question !== question;
  const hasEmbedding = !!(t['embed_bge'] || t['embed_e5']);
  const hasRetrieval = !!t['search'];
  const hasRerank = !!t['rerank'];
  const hasSelfEval = !!t['self_eval'];
  const selfEvalSkipped = !!t['self_eval_skipped'];
  const hasTavily = !!t['tavily_total'];

  // Animate layers in with a stagger
  const [visibleCount, setVisibleCount] = useState(0);
  const TOTAL_LAYERS = 10;
  useEffect(() => {
    setVisibleCount(0);
    const id = setInterval(() => {
      setVisibleCount((c) => {
        if (c >= TOTAL_LAYERS) {
          clearInterval(id);
          return c;
        }
        return c + 1;
      });
    }, 110);
    return () => clearInterval(id);
  }, [response]);

  const isVisible = (n: number) => visibleCount >= n;

  // Collection scores sorted
  const sortedScores = [...(response.collection_scores ?? [])].sort((a, b) => b.score - a.score);
  const maxScore = sortedScores[0]?.score || 1;

  // All docs (post-rerank)
  const docs = response.retrieved_documents ?? [];

  return (
    <div className="space-y-1">
      {/* ── LAYER 0: User Query ────────────────────────────── */}
      <LayerCard
        icon={<MessageSquare className="w-4 h-4" />}
        title="User Query"
        status="done"
        defaultOpen
        visible={isVisible(1)}
      >
        <p className="text-base font-medium">{question}</p>
      </LayerCard>

      <ConnectorArrow visible={isVisible(2)} />

      {/* ── LAYER 1: Query Routing ─────────────────────────── */}
      <LayerCard
        icon={<GitBranch className="w-4 h-4" />}
        title="Query Routing"
        status="done"
        timing={t['routing']}
        badge={
          <Badge
            variant={response.intent === 'rag' ? 'default' : 'secondary'}
            className="capitalize"
          >
            {response.intent}
          </Badge>
        }
        visible={isVisible(2)}
      >
        <div className="space-y-3">
          {/* Intent */}
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-24 shrink-0">Intent</span>
            <Badge
              className={cn(
                'capitalize',
                response.intent === 'rag' ? 'bg-green-500/20 text-green-700' : 'bg-slate-200',
              )}
              variant="outline"
            >
              {response.intent}
            </Badge>
            {hasTier3 && (
              <span className="text-xs text-amber-500 flex items-center gap-1">
                <RefreshCw className="w-3 h-3" /> LLM tier-3 fallback used
                <TimingBadge ms={t['tier3_domain_fallback']} />
              </span>
            )}
          </div>

          {/* Domain probabilities */}
          {sortedScores.length > 0 && (
            <div className="space-y-2">
              <p className="text-muted-foreground text-xs uppercase tracking-wide">
                Collection Scores
              </p>
              {sortedScores.map((cs) => {
                const selected = (response.target_collections ?? []).includes(cs.collection);
                return (
                  <div key={cs.collection} className="flex items-center gap-3">
                    <div
                      className={cn(
                        'w-2 h-2 rounded-full shrink-0',
                        COLLECTION_COLORS[cs.collection] || 'bg-gray-400',
                      )}
                    />
                    <span
                      className={cn(
                        'w-32 text-xs shrink-0',
                        selected ? 'font-semibold' : 'text-muted-foreground',
                      )}
                    >
                      {COLLECTION_LABELS[cs.collection] || cs.collection}
                    </span>
                    <ScoreBar value={cs.score} max={maxScore} />
                    <span className="text-xs font-mono w-12 text-right shrink-0">
                      {(cs.score * 100).toFixed(1)}%
                    </span>
                    {selected && (
                      <Badge variant="secondary" className="text-xs shrink-0">
                        ✓
                      </Badge>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </LayerCard>

      <ConnectorArrow visible={isVisible(3)} />

      {/* ── LAYER 2: Query Reflection ──────────────────────── */}
      <LayerCard
        icon={<RefreshCw className="w-4 h-4" />}
        title="Query Reflection"
        status={hasReflection ? 'done' : 'skipped'}
        timing={t['reflection']}
        visible={isVisible(3)}
      >
        {hasReflection ? (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Original</p>
              <p className="text-sm">{question}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Rewritten</p>
              <p className="text-sm font-medium">{response.reflected_question}</p>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground text-xs">
            Query was not rewritten (no context or already clear).
          </p>
        )}
      </LayerCard>

      <ConnectorArrow visible={isVisible(4)} />

      {/* ── LAYER 3: Collection Selection ──────────────────── */}
      <LayerCard
        icon={<Layers className="w-4 h-4" />}
        title="Collection Selection"
        status="done"
        timing={t['collection_routing']}
        visible={isVisible(4)}
      >
        <div className="flex flex-wrap gap-2">
          {(['quydinh', 'ctdt', 'kehoach', 'stsv'] as const).map((col) => {
            const selected = (response.target_collections ?? []).includes(col);
            return (
              <div
                key={col}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-all',
                  selected
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-muted bg-muted/30 text-muted-foreground opacity-50',
                )}
              >
                <span
                  className={cn(
                    'w-2 h-2 rounded-full',
                    selected ? COLLECTION_COLORS[col] : 'bg-muted-foreground/30',
                  )}
                />
                {COLLECTION_LABELS[col]}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          {(response.target_collections ?? []).length} of 4 collections will be searched.
        </p>
      </LayerCard>

      <ConnectorArrow visible={isVisible(5)} />

      {/* ── LAYER 4: Metadata Filters ─────────────────────── */}
      <LayerCard
        icon={<Filter className="w-4 h-4" />}
        title="Metadata Pre-Filters"
        status={(response.applied_filters ?? []).some((f) => f.applied) ? 'done' : 'skipped'}
        badge={
          (response.applied_filters ?? []).some((f) => f.applied) ? (
            <span className="text-xs text-muted-foreground">
              {(response.applied_filters ?? []).filter((f) => f.applied).length} filter(s) active
            </span>
          ) : undefined
        }
        visible={isVisible(5)}
      >
        {(response.applied_filters ?? []).length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              ES metadata pre-search narrows the Qdrant vector search to matching doc IDs.
            </p>
            <div className="space-y-1.5">
              {(response.applied_filters ?? []).map((f) => (
                <div
                  key={f.collection}
                  className={cn(
                    'flex items-start gap-3 px-3 py-2 rounded-lg border text-xs',
                    f.applied
                      ? 'border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/30'
                      : 'border-muted bg-muted/20 opacity-60',
                  )}
                >
                  <span
                    className={cn(
                      'w-2 h-2 rounded-full shrink-0 mt-0.5',
                      COLLECTION_COLORS[f.collection] || 'bg-gray-400',
                    )}
                  />
                  <div className="flex-1 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">
                        {COLLECTION_LABELS[f.collection] || f.collection}
                      </span>
                      {f.applied ? (
                        <Badge variant="secondary" className="text-xs bg-green-100 text-green-700">
                          {f.matched_ids} IDs
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">
                          no filter
                        </Badge>
                      )}
                    </div>
                    {f.filter_desc && (
                      <p className="text-muted-foreground">{f.filter_desc}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {(response.collection_results ?? []).length > 0 && (
              <div className="pt-1">
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                  Raw retrieval counts (before fusion)
                </p>
                <div className="flex flex-wrap gap-2">
                  {(response.collection_results ?? []).map((cr) => (
                    <span key={cr.collection} className="text-xs bg-muted px-2 py-0.5 rounded">
                      <span className="font-medium">{COLLECTION_LABELS[cr.collection] || cr.collection}</span>
                      {': '}{cr.vector_count}v + {cr.keyword_count}k
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground text-xs">No metadata pre-filters applied.</p>
        )}
      </LayerCard>

      <ConnectorArrow visible={isVisible(6)} />

      {/* ── LAYER 5: Embedding ─────────────────────────── */}
      <LayerCard
        icon={<Cpu className="w-4 h-4" />}
        title="Embedding"
        status={hasEmbedding ? 'done' : 'skipped'}
        visible={isVisible(6)}
      >
        <div className="grid grid-cols-2 gap-4">
          <EmbedBox
            name="BGE-M3"
            model="BAAI/bge-m3"
            dim={1024}
            ms={t['embed_bge']}
            color="blue"
          />
          <EmbedBox
            name="E5-Multilingual"
            model="intfloat/multilingual-e5-large"
            dim={1024}
            ms={t['embed_e5']}
            color="violet"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Query is encoded into two dense vector spaces for hybrid search.
        </p>
      </LayerCard>

      <ConnectorArrow visible={isVisible(6)} />

      {/* ── LAYER 5: Hybrid Retrieval ──────────────────────── */}
      <LayerCard
        icon={<Search className="w-4 h-4" />}
        title="Hybrid Retrieval"
        status={hasRetrieval ? 'done' : 'skipped'}
        timing={t['search']}
        badge={
          docs.length > 0 ? (
            <span className="text-xs text-muted-foreground">{docs.length} docs retrieved</span>
          ) : undefined
        }
        defaultOpen={false}
        visible={isVisible(6)}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-3 text-xs text-muted-foreground pb-1">
            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              Qdrant Vector (BGE + E5 fused)
            </span>
            <span className="text-muted-foreground">+</span>
            <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">
              Elasticsearch BM25
            </span>
            <span className="text-muted-foreground ml-auto">→ min-max score fusion</span>
          </div>
          {docs.map((doc, i) => (
            <DocRow key={doc.rank ?? i} doc={doc} rank={i + 1} showRerank={false} />
          ))}
          {docs.length === 0 && (
            <p className="text-xs text-muted-foreground">No documents retrieved.</p>
          )}
        </div>
      </LayerCard>

      <ConnectorArrow visible={isVisible(8)} />

      {/* ── LAYER 7: Reranking ─────────────────────────── */}
      <LayerCard
        icon={<ArrowDownUp className="w-4 h-4" />}
        title="BGE Reranking"
        status={hasRerank ? 'done' : 'skipped'}
        timing={t['rerank']}
        badge={
          <span className="text-xs text-muted-foreground">BAAI/bge-reranker-v2-m3</span>
        }
        defaultOpen={false}
        visible={isVisible(8)}
      >
        <p className="text-xs text-muted-foreground pb-1">
          Cross-encoder scores each (query, doc) pair; docs are re-sorted by rerank_score.
        </p>
        <div className="space-y-1">
          {docs.map((doc, i) => (
            <DocRow key={doc.rank ?? i} doc={doc} rank={i + 1} showRerank={true} />
          ))}
        </div>
      </LayerCard>

      <ConnectorArrow visible={isVisible(9)} />

      {/* ── LAYER 8: LLM Generation ────────────────────── */}
      <LayerCard
        icon={<Sparkles className="w-4 h-4" />}
        title="LLM Generation"
        status="done"
        timing={t['generate']}
        badge={
          <span className="text-xs text-muted-foreground font-mono">{response.model_name}</span>
        }
        visible={isVisible(9)}
      >
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">Context budget:</span>
            <span className="text-xs bg-muted px-2 py-0.5 rounded">8 000 chars</span>
            <span className="text-xs text-muted-foreground">Docs used:</span>
            <span className="text-xs bg-muted px-2 py-0.5 rounded">{response.num_documents}</span>
          </div>
          <div className="p-3 bg-muted/30 rounded-lg text-sm leading-relaxed whitespace-pre-wrap border">
            {response.answer}
          </div>
        </div>
      </LayerCard>

      {/* ── LAYER 9: Self-Evaluation (conditional) ─────────── */}
      {(hasSelfEval || selfEvalSkipped || hasTavily) && (
        <>
          <ConnectorArrow visible={isVisible(10)} />
          <LayerCard
            icon={<ShieldCheck className="w-4 h-4" />}
            title="Self-Evaluation"
            status={selfEvalSkipped ? 'skipped' : hasTavily ? 'triggered' : 'done'}
            timing={t['self_eval'] ?? t['self_eval_skipped']}
            visible={isVisible(10)}
          >
            {selfEvalSkipped ? (
              <p className="text-xs text-muted-foreground">
                Skipped — top rerank score exceeded threshold (≥ 0.72), answer quality assumed
                good.
              </p>
            ) : hasTavily ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-amber-600 text-xs font-medium">
                  <XCircle className="w-4 h-4" />
                  Self-eval FAILED — triggered Tavily web search fallback
                </div>
                <div className="flex gap-2 flex-wrap">
                  <TimingBadge ms={t['tavily_search']} />
                  <span className="text-xs text-muted-foreground">web search</span>
                  <TimingBadge ms={t['tavily_generate']} />
                  <span className="text-xs text-muted-foreground">re-generate</span>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-green-600 text-xs font-medium">
                <CheckCircle2 className="w-4 h-4" />
                Self-eval PASSED — answer quality verified.
              </div>
            )}
          </LayerCard>
        </>
      )}

      {/* ── Totals ─────────────────────────────────────────── */}
      {isVisible(10) && (
        <TotalsBar timings={t} intent={response.intent} />
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Helper sub-components
───────────────────────────────────────────────────────── */

function ConnectorArrow({ visible }: { visible: boolean }) {
  return (
    <div
      className={cn(
        'flex justify-center py-0.5 transition-all duration-300',
        visible ? 'opacity-100' : 'opacity-0',
      )}
    >
      <ArrowDown className="w-4 h-4 text-muted-foreground/50" />
    </div>
  );
}

function EmbedBox({
  name,
  model,
  dim,
  ms,
  color,
}: {
  name: string;
  model: string;
  dim: number;
  ms?: number;
  color: string;
}) {
  const colorClass =
    color === 'blue'
      ? 'border-blue-200 bg-blue-50 dark:bg-blue-950/20'
      : 'border-violet-200 bg-violet-50 dark:bg-violet-950/20';
  return (
    <div className={cn('border rounded-lg p-3 space-y-1', colorClass)}>
      <div className="flex items-center justify-between">
        <span className="font-medium text-xs">{name}</span>
        <TimingBadge ms={ms} />
      </div>
      <p className="text-xs text-muted-foreground font-mono">{model}</p>
      <p className="text-xs text-muted-foreground">{dim}-dim dense vector</p>
    </div>
  );
}

function TotalsBar({ timings, intent }: { timings: Record<string, number>; intent: string }) {
  const stages = [
    { key: 'routing', label: 'Routing', color: 'bg-blue-400' },
    { key: 'reflection', label: 'Reflection', color: 'bg-purple-400' },
    { key: 'embed_bge', label: 'Embed', color: 'bg-pink-400' },
    { key: 'search', label: 'Search', color: 'bg-amber-400' },
    { key: 'rerank', label: 'Rerank', color: 'bg-orange-400' },
    { key: 'generate', label: 'Generate', color: 'bg-green-400' },
    { key: 'self_eval', label: 'Self-eval', color: 'bg-teal-400' },
  ].filter((s) => !!timings[s.key]);

  const total = timings['pipeline_total'] ?? timings['flow_total'];
  const stagesTotal = stages.reduce((sum, s) => sum + (timings[s.key] ?? 0), 0);

  return (
    <div className="border rounded-xl p-4 bg-card mt-2 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">Total Latency</span>
        <span className="text-lg font-bold font-mono">{fmtMs(total)}</span>
      </div>

      {/* Stacked timing bar */}
      <div className="space-y-1">
        <div className="flex h-4 rounded-full overflow-hidden gap-0.5">
          {stages.map((s) => {
            const pct = ((timings[s.key] ?? 0) / stagesTotal) * 100;
            return (
              <div
                key={s.key}
                className={cn('h-full transition-all duration-700', s.color)}
                style={{ width: `${pct}%` }}
                title={`${s.label}: ${fmtMs(timings[s.key])}`}
              />
            );
          })}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {stages.map((s) => (
            <div key={s.key} className="flex items-center gap-1 text-xs text-muted-foreground">
              <span className={cn('w-2 h-2 rounded-full shrink-0', s.color)} />
              {s.label}
              <span className="font-mono">{fmtMs(timings[s.key])}</span>
            </div>
          ))}
        </div>
      </div>

      {intent === 'chitchat' && (
        <p className="text-xs text-muted-foreground italic">
          Chitchat intent — retrieval layers were bypassed.
        </p>
      )}
    </div>
  );
}
