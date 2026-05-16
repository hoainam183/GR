import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  BarChart4,
  CheckCircle2,
  Clock,
  Database,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { getEvalDashboard, type EvalDashboardResponse, type EvalBreakdownRow } from '@/services/chatApi';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

type Suite = 'current_policy' | 'historical_email';

const formatMetric = (value: unknown): string => {
  if (typeof value !== 'number') return value == null ? 'n/a' : String(value);
  if (value > 10) return value.toFixed(0);
  return value.toFixed(3);
};

const statusVariant = (status?: string) => {
  if (status === 'passed') return 'default';
  if (status === 'warning') return 'secondary';
  return 'destructive';
};

const StatusIcon = ({ status }: { status?: string }) => {
  if (status === 'passed') return <CheckCircle2 className="h-4 w-4" />;
  if (status === 'warning') return <AlertTriangle className="h-4 w-4" />;
  return <XCircle className="h-4 w-4" />;
};

function SummaryCard({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="border rounded-lg bg-card p-4 space-y-1">
      <p className="text-[10px] text-muted-foreground uppercase font-bold">{label}</p>
      <p className="text-xl font-semibold">{formatMetric(value)}</p>
    </div>
  );
}

function BreakdownTable({ title, rows }: { title: string; rows?: EvalBreakdownRow[] }) {
  return (
    <div className="border rounded-lg bg-card p-5 space-y-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="space-y-1">
        {(rows ?? []).length === 0 && (
          <p className="text-sm text-muted-foreground">No rows.</p>
        )}
        {(rows ?? []).map((row) => (
          <div key={row.key} className="grid grid-cols-[1fr_auto_auto] gap-3 py-2 border-b last:border-b-0 text-sm">
            <span className="truncate">{row.key}</span>
            <span className="text-muted-foreground">{row.failed_cases}/{row.total_cases} fail</span>
            <span className="font-mono">{formatMetric(row.pass_rate)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EvalPage() {
  const [suite, setSuite] = useState<Suite>('current_policy');
  const { data, isLoading, error, refetch, isFetching } = useQuery<EvalDashboardResponse>({
    queryKey: ['eval-dashboard', suite],
    queryFn: () => getEvalDashboard(suite, 12),
    refetchOnWindowFocus: false,
  });

  const latest = data?.latest;
  const summary = latest?.summary ?? {};
  const baselineWarnings = Array.isArray(summary.baseline_warnings) ? summary.baseline_warnings : [];
  const keyMetrics = useMemo(() => {
    if (suite === 'current_policy') {
      return [
        ['Cases', summary.total_cases],
        ['nDCG@10', summary.ndcg_at_10 ?? summary.ndcg_at_k],
        ['MRR@10', summary.mrr_at_10 ?? summary.mrr_at_k],
        ['Recall@50', summary.recall_at_50 ?? summary.raw_recall_at_50],
        ['Context P', summary.context_precision],
        ['Citation', summary.citation_accuracy],
        ['Freshness', summary.freshness_pass_rate],
        ['Latency p95', summary.latency_p95_ms],
      ];
    }
    return [
      ['Cases', summary.total_cases],
      ['Passed', summary.passed_cases],
      ['Failed', summary.failed_cases],
      ['Judge score', summary.avg_judge_score],
      ['Latency p50', summary.latency_p50_ms],
      ['Latency p95', summary.latency_p95_ms],
    ];
  }, [suite, summary]);

  return (
    <div className="min-h-screen bg-background">
      <div className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-4">
          <Link to="/chat" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" /> Chat
          </Link>
          <div className="h-4 w-px bg-border" />
          <Link to="/retrieval" className="text-sm text-muted-foreground hover:text-foreground">Retrieval</Link>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <BarChart4 className="w-4 h-4 text-primary" />
            <h1 className="text-sm font-semibold">Evaluation Dashboard</h1>
          </div>
          <div className="ml-auto">
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
          <Tabs value={suite} onValueChange={(v) => setSuite(v as Suite)}>
            <TabsList>
              <TabsTrigger value="current_policy">Current Policy</TabsTrigger>
              <TabsTrigger value="historical_email">Historical Email</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Database className="h-3.5 w-3.5" />
            Source: {data?.source ?? 'n/a'}
          </div>
        </div>

        {isLoading && (
          <div className="border rounded-lg bg-card p-6 text-sm text-muted-foreground">
            Loading evaluation metrics...
          </div>
        )}

        {error && (
          <div className="border border-red-200 bg-red-50 dark:bg-red-950/20 rounded-lg p-4 text-sm text-red-600">
            {(error as Error).message}
          </div>
        )}

        {!isLoading && !latest && (
          <div className="border rounded-lg bg-card p-6 space-y-2">
            <p className="font-medium">No evaluation runs found.</p>
            <p className="text-sm text-muted-foreground">
              Run `python -m evaluation.two_layer_eval current --persist` from `src/RAG_v2`.
            </p>
          </div>
        )}

        {latest && (
          <>
            <div className="border rounded-lg bg-card p-5 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariant(latest.status)} className="gap-1">
                    <StatusIcon status={latest.status} />
                    {latest.status}
                  </Badge>
                  <span className="text-sm font-mono">{latest.run_id}</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  Trigger: {latest.trigger || 'manual'} | Finished: {latest.finished_at || 'n/a'}
                </p>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="h-4 w-4" />
                {summary.total_cases ?? 0} cases
              </div>
            </div>

            {baselineWarnings.length > 0 && (
              <div className="border border-amber-200 bg-amber-50 dark:bg-amber-950/20 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300">
                {baselineWarnings.join(' | ')}
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {keyMetrics.map(([label, value]) => (
                <SummaryCard key={label} label={String(label)} value={value} />
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="border rounded-lg bg-card p-5 space-y-4">
                <h2 className="text-sm font-semibold">Recent Runs</h2>
                <div className="space-y-2">
                  {(data?.runs ?? []).map((run) => (
                    <div key={run.run_id} className="flex items-center justify-between gap-3 text-sm border-b last:border-b-0 py-2">
                      <div className="min-w-0">
                        <p className="font-mono truncate">{run.run_id}</p>
                        <p className="text-xs text-muted-foreground">{run.finished_at}</p>
                      </div>
                      <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border rounded-lg bg-card p-5 space-y-4">
                <h2 className="text-sm font-semibold">Top Failures</h2>
                <div className="space-y-3 max-h-[420px] overflow-auto">
                  {(data?.failing_cases ?? []).length === 0 && (
                    <p className="text-sm text-muted-foreground">No failing cases in latest run.</p>
                  )}
                  {(data?.failing_cases ?? []).map((item) => (
                    <div key={`${item.eval_suite}-${item.case_id}`} className="py-3 border-b last:border-b-0 space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-mono">{item.case_id}</p>
                        <Badge variant="destructive">fail</Badge>
                      </div>
                      <p className="text-sm line-clamp-2">{item.question}</p>
                      <p className="text-xs text-muted-foreground">
                        {(item.fail_reasons ?? [item.error ?? 'unknown']).join(', ')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <BreakdownTable title="By Query Class" rows={data?.breakdown?.by_query_class} />
              <BreakdownTable title="By Collection" rows={data?.breakdown?.by_collection} />
            </div>

            {suite === 'current_policy' && (
              <div className="border rounded-lg bg-card p-5 space-y-4">
                <h2 className="text-sm font-semibold">Stale Source Violations</h2>
                {(data?.stale_source_violations ?? []).length === 0 && (
                  <p className="text-sm text-muted-foreground">No stale-source violations in latest run.</p>
                )}
                {(data?.stale_source_violations ?? []).map((item) => (
                  <div key={`stale-${item.case_id}`} className="py-3 border-b last:border-b-0 space-y-1">
                    <p className="text-xs font-mono">{item.case_id}</p>
                    <p className="text-sm">{item.question}</p>
                    <p className="text-xs text-muted-foreground">
                      {(item.fail_reasons ?? []).join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
