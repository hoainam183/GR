import type { AgentToolCall, ChatV3Response } from '@/types/chat';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
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
