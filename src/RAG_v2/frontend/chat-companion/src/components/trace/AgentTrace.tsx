import type { AgentToolCall, ChatV3Response } from '@/types/chat';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  ListChecks,
  Route,
  Wrench,
  Search,
} from 'lucide-react';
import { DocRow } from './DocRow';

interface AgentTraceProps {
  response: ChatV3Response;
  question: string;
}

const formatMs = (value?: number): string | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null;
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(2)} s`;
};

const resolveToolCalls = (response: ChatV3Response): AgentToolCall[] => {
  if (Array.isArray(response.tool_calls)) {
    return response.tool_calls;
  }
  if (Array.isArray(response.agent_trace?.tool_calls)) {
    return response.agent_trace.tool_calls;
  }
  return [];
};

const resolveToolsUsed = (response: ChatV3Response): string[] => {
  if (Array.isArray(response.tools_used)) {
    return response.tools_used;
  }
  if (Array.isArray(response.agent_trace?.tool_names_sequence)) {
    return response.agent_trace.tool_names_sequence;
  }
  return [];
};

const traceList = (value: unknown): Array<Record<string, unknown>> =>
  Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    : [];

const traceText = (value: unknown): string | null => {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return null;
};

const PlannerExecutorTrace = ({ response }: { response: ChatV3Response }) => {
  const trace = response.agent_trace;
  const plannerTrace = trace?.planner_trace ?? {};
  const planSteps = traceList(
    trace?.retrieval_plan?.steps ?? plannerTrace.steps,
  );
  const executorResults = traceList(trace?.executor_results);
  const synthesisTrace = trace?.synthesis_trace ?? {};

  if (!planSteps.length && !executorResults.length && !trace?.sub_questions?.length) {
    return null;
  }

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <ListChecks className="h-4 w-4 text-primary" />
        Planner / Executor path
      </div>

      {trace?.sub_questions && trace.sub_questions.length > 0 && (
        <div className="mb-3 rounded-md bg-muted/30 p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Sub-questions</p>
          <ol className="ml-4 list-decimal space-y-1 text-xs">
            {trace.sub_questions.map((question, index) => (
              <li key={`${question}-${index}`}>{question}</li>
            ))}
          </ol>
        </div>
      )}

      {planSteps.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Planner queries</p>
          {planSteps.map((step, index) => {
            const query = traceText(step.query) ?? '(missing query)';
            const collection = traceText(step.collection);
            const topK = traceText(step.top_k);
            const label = traceText(step.label);
            return (
              <div key={`${query}-${index}`} className="rounded-md border bg-muted/20 p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">#{index + 1}</Badge>
                  {label && <Badge variant="outline">{label}</Badge>}
                  {collection && <Badge variant="outline">{collection}</Badge>}
                  {topK && <Badge variant="outline">top_k {topK}</Badge>}
                </div>
                <p className="mt-2 whitespace-pre-wrap leading-relaxed">{query}</p>
              </div>
            );
          })}
        </div>
      )}

      {executorResults.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Executor results</p>
          {executorResults.map((result, index) => {
            const query = traceText(result.query);
            const collection = traceText(result.collection);
            const latency = typeof result.latency_ms === 'number' ? formatMs(result.latency_ms) : null;
            const resultChars = traceText(result.result_chars);
            const empty = result.empty_result === true;
            return (
              <div key={`${query ?? index}-${index}`} className="rounded-md border bg-muted/20 p-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">#{index + 1}</Badge>
                  {collection && <Badge variant="outline">{collection}</Badge>}
                  {latency && <Badge variant="outline">{latency}</Badge>}
                  {resultChars && <Badge variant="outline">{resultChars} chars</Badge>}
                  <Badge className={empty ? 'bg-amber-500/15 text-amber-700' : 'bg-emerald-500/15 text-emerald-700'} variant="outline">
                    {empty ? 'empty' : 'has result'}
                  </Badge>
                </div>
                {query && <p className="mt-2 whitespace-pre-wrap leading-relaxed">{query}</p>}
              </div>
            );
          })}
        </div>
      )}

      {typeof synthesisTrace.context_chars === 'number' && (
        <div className="mt-3 rounded-md bg-muted/30 p-3 text-xs text-muted-foreground">
          Synthesis context: {synthesisTrace.context_chars} chars
          {typeof synthesisTrace.answer_chars === 'number' && ` · answer ${synthesisTrace.answer_chars} chars`}
        </div>
      )}
    </div>
  );
};

const ToolCallCard = ({
  call,
  index,
}: {
  call: AgentToolCall;
  index: number;
}) => {
  const serializedArgs = JSON.stringify(call.args ?? {}, null, 2);
  const trimmedResult =
    typeof call.result === 'string' ? call.result.trim() : '';

  return (
    <details className="rounded-lg border bg-card/50 p-3" open={index === 0}>
      <summary className="cursor-pointer list-none">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-mono text-xs text-muted-foreground">
            #{index + 1}
          </span>
          <Wrench className="h-4 w-4 text-primary" />
          <span className="font-medium">{call.tool || 'unknown_tool'}</span>
          <Badge variant="secondary" className="ml-auto text-xs">
            iteration {call.iteration + 1}
          </Badge>
        </div>
      </summary>

      <div className="mt-3 space-y-3 text-xs">
        <div>
          <p className="mb-1 font-medium text-muted-foreground">Arguments</p>
          <pre className="max-h-48 overflow-auto rounded-md bg-muted/40 p-2 leading-relaxed">
            {serializedArgs}
          </pre>
        </div>

        <div>
          <p className="mb-1 font-medium text-muted-foreground">Tool output</p>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted/40 p-2 leading-relaxed">
            {trimmedResult || '(empty output)'}
          </pre>
        </div>
      </div>
    </details>
  );
};

export default function AgentTrace({ response, question }: AgentTraceProps) {
  const toolCalls = resolveToolCalls(response);
  const toolsUsed = resolveToolsUsed(response);
  const iterations =
    response.iterations ?? response.agent_trace?.iterations ?? toolCalls.length;
  const route = response.route ?? response.agent_trace?.route ?? 'complex';
  const latencyLabel = formatMs(response.agent_trace?.latency_ms);
  const finalError =
    response.error ?? response.agent_error ?? response.agent_trace?.error ?? null;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Agent Execution Summary</h3>
          </div>

          <Badge variant="outline" className="ml-auto">
            mode {response.mode || 'agent'}
          </Badge>
          <Badge variant="secondary">route {route}</Badge>
          <Badge variant="secondary">iterations {iterations || 0}</Badge>
          {latencyLabel && (
            <Badge variant="secondary" className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {latencyLabel}
            </Badge>
          )}
          {!finalError ? (
            <Badge className="bg-emerald-500/15 text-emerald-700" variant="outline">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              completed
            </Badge>
          ) : (
            <Badge className="bg-amber-500/15 text-amber-700" variant="outline">
              <AlertTriangle className="mr-1 h-3 w-3" />
              fallback/error
            </Badge>
          )}
        </div>

        <div className="mt-3 rounded-md border bg-muted/20 p-3 text-sm">
          <p className="text-xs text-muted-foreground">Question</p>
          <p className="mt-1">{question}</p>
        </div>

        {finalError && (
          <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {finalError}
          </div>
        )}
      </div>

      <div className="rounded-xl border bg-card p-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <Route className="h-4 w-4 text-primary" />
          Tool sequence
        </div>

        {toolsUsed.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {toolsUsed.map((toolName, index) => (
              <Badge key={`${toolName}-${index}`} variant="secondary" className="font-mono text-[11px]">
                #{index + 1} {toolName}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No tools were called in this run.</p>
        )}
      </div>

      <PlannerExecutorTrace response={response} />

      <div className="rounded-xl border bg-card p-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <Wrench className="h-4 w-4 text-primary" />
          Tool call details
        </div>

        {toolCalls.length > 0 ? (
          <div className="space-y-2">
            {toolCalls.map((call, index) => (
              <ToolCallCard key={`${call.tool}-${index}`} call={call} index={index} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Detailed tool payload is not available for this run.
          </p>
        )}
      </div>

      {response.retrieved_documents && response.retrieved_documents.length > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Search className="h-4 w-4 text-primary" />
            Retrieved Documents ({response.num_documents || response.retrieved_documents.length})
          </div>
          <div className="space-y-2">
            {response.retrieved_documents.map((doc, index) => (
              <DocRow
                key={doc.rank ?? index}
                doc={doc}
                rank={index + 1}
                showRerank={doc.rerank_score !== undefined}
              />
            ))}
          </div>
        </div>
      )}

      <details className="rounded-xl border bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium">Raw agent trace payload</summary>
        <pre className="mt-3 max-h-72 overflow-auto rounded-md bg-muted/40 p-3 text-[11px] leading-5">
          {JSON.stringify(response.agent_trace ?? null, null, 2)}
        </pre>
      </details>
    </div>
  );
}
