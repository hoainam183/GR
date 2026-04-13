import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { sendMessage } from '@/services/chatApi';
import { ChatResponse } from '@/types/chat';
import PipelineTrace from '@/components/trace/PipelineTrace';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  GitBranch,
  ArrowLeft,
  Send,
  Loader2,
  Activity,
  Info,
} from 'lucide-react';

/* ── Animated pipeline skeleton while loading ── */
function LoadingSkeleton() {
  const steps = [
    'Routing query...',
    'Reflecting query...',
    'Selecting collections...',
    'Embedding (BGE-M3 + E5)...',
    'Hybrid retrieval (Qdrant + ES)...',
    'Reranking (BGE-v2-m3)...',
    'Generating answer (Gemini)...',
  ];
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
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const handleTrace = async (q?: string) => {
    const finalQ = (q ?? question).trim();
    if (!finalQ) return;
    if (q) setQuestion(q);
    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await sendMessage(finalQ, [], 10);
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
            <h1 className="text-sm font-semibold">Pipeline Trace Debugger</h1>
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
            <GitBranch className="w-3 h-3" />
            RAG v2 — 8 layers
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* ── Input card ── */}
        <div className="border rounded-xl bg-card p-5 space-y-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold">Query</h2>
            <p className="text-xs text-muted-foreground">
              Send any question and watch it flow through each layer of the RAG pipeline in real
              time.
            </p>
          </div>

          <div className="relative">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập câu hỏi để trace qua RAG pipeline..."
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

        {/* ── Error ── */}
        {error && (
          <div className="border border-red-200 bg-red-50 dark:bg-red-950/20 rounded-xl p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* ── Loading skeleton ── */}
        {isLoading && (
          <div className="border rounded-xl bg-card p-5">
            <p className="text-sm font-medium mb-2">Processing pipeline…</p>
            <LoadingSkeleton />
          </div>
        )}

        {/* ── Trace result ── */}
        {result && !isLoading && (
          <div ref={resultRef} className="space-y-1">
            <div className="flex items-center gap-2 pb-2">
              <Activity className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold">Pipeline Trace</h2>
              <span className="text-xs text-muted-foreground ml-auto">
                Click any card header to expand / collapse
              </span>
            </div>
            <PipelineTrace response={result} question={result.question} />
          </div>
        )}
      </div>
    </div>
  );
}
