import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RetrievedDocument } from '@/types/chat';

export const COLLECTION_COLORS: Record<string, string> = {
  quydinh: 'bg-blue-500',
  ctdt: 'bg-violet-500',
  kehoach: 'bg-amber-500',
  stsv: 'bg-emerald-500',
};

export const COLLECTION_LABELS: Record<string, string> = {
  quydinh: 'Quy Định',
  ctdt: 'Chương Trình ĐT',
  kehoach: 'Kế Hoạch',
  stsv: 'Sinh Viên',
};

export function DocRow({
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
  const title = (doc.metadata?.title as string) || (doc.metadata?.source as string) || '—';
  const score = doc.score ?? 0;

  return (
    <div className="border rounded-lg overflow-hidden bg-background">
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
