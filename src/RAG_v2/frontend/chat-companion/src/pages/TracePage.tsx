import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { sendMessageV3, resolveChatIdentity } from '@/services/chatApi';
import type { ChatV3Response } from '@/types/chat';
import AgentTrace from '@/components/trace/AgentTrace';
import PipelineTrace from '@/components/trace/PipelineTrace';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Brain,
  GitBranch,
  ArrowLeft,
  Send,
  Loader2,
  Activity,
  Info,
  Layers,
} from 'lucide-react';

type TraceMode = 'auto' | 'rag' | 'agent';

const TRACE_MODES: Array<{ value: TraceMode; label: string; help: string }> = [
  {
    value: 'auto',
    label: 'Auto',
    help: 'Router tu dong chon rag/chitchat/agent',
  },
  {
    value: 'rag',
    label: 'Force RAG',
    help: 'Bat buoc chay pipeline RAG v2',
  },
  {
    value: 'agent',
    label: 'Force Agent',
    help: 'Bat buoc chay LangGraph agent',
  },
];

/* ── Animated pipeline skeleton while loading ── */
function LoadingSkeleton({ mode }: { mode: TraceMode }) {
  const stepsByMode: Record<TraceMode, string[]> = {
    auto: [
      'Routing query (simple/chitchat/complex)...',
      'If complex: agent plans next action...',
      'Tool execution loop or RAG retrieval...',
      'Synthesizing final answer...',
    ],
    rag: [
      'Routing query...',
      'Reflecting query...',
      'Selecting collections...',
      'Embedding (BGE-M3 + E5)...',
      'Hybrid retrieval (Qdrant + ES)...',
      'Reranking (BGE-v2-m3)...',
      'Generating answer...',
    ],
    agent: [
      'Agent receives question...',
      'LLM decides tool call...',
      'Executing tools via adapters...',
      'Loop detection / max-iteration guard...',
      'Synthesizing final answer...',
    ],
  };

  const steps = stepsByMode[mode];
  const [activeIdx, setActiveIdx] = useState(0);

  React.useEffect(() => {
    const id = setInterval(() => {
      setActiveIdx((i) => Math.min(i + 1, steps.length - 1));
    }, 700);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-2 py-4">
      {steps.map((step, i) => (
        <div
          key={step}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-500 ${
            i < activeIdx
              ? 'opacity-100 border-green-200 bg-green-50 dark:bg-green-950/20'
              : i === activeIdx
              ? 'opacity-100 border-primary bg-primary/5'
              : 'opacity-30 border-muted bg-muted/10'
          }`}
        >
          {i < activeIdx ? (
            <span className="w-4 h-4 text-green-500 shrink-0">✓</span>
          ) : i === activeIdx ? (
            <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
          ) : (
            <span className="w-4 h-4 shrink-0 text-muted-foreground/30">○</span>
          )}
          <span className={`text-sm ${i === activeIdx ? 'font-medium' : 'text-muted-foreground'}`}>
            {step}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Example queries ── */
const EXAMPLES = [
  'Điều kiện để được nhận học bổng khuyến khích học tập là gì?',
  'Sinh viên K67 ngành CNTT cần học bao nhiêu tín chỉ?',
  'Quy định về đánh giá điểm rèn luyện sinh viên 2023',
  'Xin chào, bạn có thể giúp gì cho tôi?',
];

export default function TracePage() {
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<TraceMode>('auto');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ChatV3Response | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const identity = resolveChatIdentity();

  const debugPayload = {
    requested_mode: mode,
    source: identity.source,
    user_id: identity.userId ?? null,
    user_context: identity.userContext ?? null,
  };

  const handleTrace = async (q?: string) => {
    const finalQ = (q ?? question).trim();
    if (!finalQ) return;
    if (q) setQuestion(q);
    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const liveIdentity = resolveChatIdentity();
      const res = await sendMessageV3(
        finalQ,
        [],
        10,
        mode,
        undefined,
        liveIdentity.userContext,
        liveIdentity.userId,
      );
      setResult(res);
      // Scroll to results after a short delay
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (e: any) {
      setError(
        e?.response?.data?.detail || e?.message || 'Request failed. Is the backend running?',
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTrace();
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* ── Header ── */}
      <div className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center gap-4">
          <Link
            to="/chat"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Chat
          </Link>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h1 className="text-sm font-semibold">Trace and Debug Console</h1>
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
            <GitBranch className="w-3 h-3" />
            RAG v2 + Agent
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* ── Input card ── */}
        <div className="border rounded-xl bg-card p-5 space-y-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold">Query</h2>
            <p className="text-xs text-muted-foreground">
              Send a question to inspect routing, tools, and internals for both RAG pipeline and
              LangGraph agent.
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Execution Mode
            </p>
            <div className="flex flex-wrap gap-2">
              {TRACE_MODES.map((option) => {
                const selected = mode === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setMode(option.value)}
                    disabled={isLoading}
                    className={`rounded-lg border px-3 py-1.5 text-left transition-colors ${
                      selected
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border bg-muted/20 text-muted-foreground hover:bg-muted/50'
                    }`}
                  >
                    <p className="text-xs font-semibold">{option.label}</p>
                    <p className="text-[11px]">{option.help}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="relative">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhap cau hoi de trace qua RAG/Agent..."
              className="min-h-[80px] resize-none pr-12 text-sm"
              disabled={isLoading}
            />
            <Button
              size="icon"
              className="absolute bottom-3 right-3"
              onClick={() => handleTrace()}
              disabled={isLoading || !question.trim()}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          {/* Example queries */}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Info className="w-3 h-3" /> Try an example:
            </p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  className="text-xs border rounded-full px-3 py-1 hover:bg-muted transition-colors text-left"
                  onClick={() => handleTrace(ex)}
                  disabled={isLoading}
                >
                  {ex.length > 55 ? ex.slice(0, 52) + '…' : ex}
                </button>
              ))}
            </div>
          </div>
        </div>

        <details className="border rounded-xl bg-card px-5 py-4">
          <summary className="cursor-pointer select-none text-sm font-medium">
            Debug user info
          </summary>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2 text-xs">
              <span className="text-muted-foreground">Identity source</span>
              <span className="font-medium text-foreground">{identity.source}</span>
            </div>
            <pre className="max-h-56 overflow-auto rounded-md bg-muted/40 p-3 text-[11px] leading-5 text-foreground">
              {JSON.stringify(debugPayload, null, 2)}
            </pre>
          </div>
        </details>

        {/* ── Error ── */}
        {error && (
          <div className="border border-red-200 bg-red-50 dark:bg-red-950/20 rounded-xl p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* ── Loading skeleton ── */}
        {isLoading && (
          <div className="border rounded-xl bg-card p-5">
            <p className="text-sm font-medium mb-2">Processing request...</p>
            <LoadingSkeleton mode={mode} />
          </div>
        )}

        {/* ── Trace result ── */}
        {result && !isLoading && (
          <div ref={resultRef} className="space-y-1">
            <div className="flex items-center gap-2 pb-2 flex-wrap">
              <Activity className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold">Execution Trace</h2>
              <span className="text-xs text-muted-foreground ml-auto">
                Click any card header to expand / collapse
              </span>
            </div>

            <div className="border rounded-xl bg-card p-4 flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <Layers className="h-3.5 w-3.5" />
                requested: {mode}
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <Brain className="h-3.5 w-3.5" />
                actual: {result.mode || 'unknown'}
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <GitBranch className="h-3.5 w-3.5" />
                route: {result.route || result.intent || 'n/a'}
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                iteration: {result.iterations ?? 0}
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                tools: {(result.tools_used ?? []).length}
              </Button>
            </div>

            {(result.mode === 'agent' || result.mode === 'rag_v2_fallback' || !!result.agent_trace) && (
              <AgentTrace response={result} question={result.question || question} />
            )}

            {result.mode !== 'agent' && (
              <PipelineTrace response={result} question={result.question || question} />
            )}

            <details className="border rounded-xl bg-card px-5 py-4">
              <summary className="cursor-pointer select-none text-sm font-medium">
                Raw response payload
              </summary>
              <pre className="mt-3 max-h-[420px] overflow-auto rounded-md bg-muted/40 p-3 text-[11px] leading-5 text-foreground">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
