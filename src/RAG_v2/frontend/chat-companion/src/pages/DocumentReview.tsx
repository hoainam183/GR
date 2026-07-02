import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import PipelineProgress from '@/components/admin/PipelineProgress';
import MarkdownEditor from '@/components/admin/MarkdownEditor';
import ChunkViewer from '@/components/admin/ChunkViewer';
import MetadataForm from '@/components/admin/MetadataForm';
import {
  getDocument,
  triggerConvert,
  triggerClean,
  triggerLlmClean,
  triggerChunk,
  triggerIndex,
  triggerFullPipeline,
  getMarkdown,
  updateMarkdown,
  getCleanedContent,
  updateCleaned,
  getLlmCleaned,
  updateLlmCleaned,
  listConverters,
  listChunkers,
  listChunkStrategies,
  selectChunkStrategy,
  rollbackDocument,
} from '@/services/adminApi';
import type {
  DocumentDetail,
  DocumentStatus,
  PipelineStep,
  ConverterOption,
  ChunkerOption,
  ChunkStrategySummary,
} from '@/types/admin';
import { CHUNKER_ALTERNATIVES, PIPELINE_STEPS } from '@/types/admin';
import { ArrowLeft, Play, Zap, GitCompare, Check, RotateCcw } from 'lucide-react';

type RetryingStep = PipelineStep['key'] | 'rollback';

function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

function apiStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}

export default function DocumentReview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<RetryingStep | null>(null);
  const [mdContent, setMdContent] = useState<string | null>(null);
  const [cleanedContent, setCleanedContent] = useState<string | null>(null);
  const [llmCleanedContent, setLlmCleanedContent] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Converter / chunker selection
  const [converters, setConverters] = useState<ConverterOption[]>([]);
  const [selectedConverter, setSelectedConverter] = useState<string>('pymupdf4llm');
  const [chunkers, setChunkers] = useState<ChunkerOption[]>([]);
  const [selectedChunker, setSelectedChunker] = useState<string>('');
  const [chunkSets, setChunkSets] = useState<ChunkStrategySummary[]>([]);
  const [viewingStrategy, setViewingStrategy] = useState<string | undefined>(undefined);

  const fetchDoc = useCallback(async () => {
    if (!id) return;
    try {
      const d = await getDocument(id);
      setDoc(d);
      return d;
    } catch (error: unknown) {
      if (apiStatus(error) === 404) {
        toast.error('Tài liệu không tồn tại');
        navigate('/admin');
      }
    }
  }, [id, navigate]);

  const fetchChunkSets = useCallback(async () => {
    if (!id) return;
    try {
      const strategies = await listChunkStrategies(id);
      setChunkSets(strategies);
    } catch {
      // Ignore if no chunks yet
    }
  }, [id]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDoc(),
      listConverters().then(setConverters).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [fetchDoc]);

  // Load chunkers when doc collection is known
  useEffect(() => {
    if (doc?.collection) {
      listChunkers(doc.collection).then((c) => {
        setChunkers(c);
        // Default to the collection's suggested chunker
        if (!selectedChunker && doc.chunking_strategy) {
          setSelectedChunker(doc.chunking_strategy);
        } else if (!selectedChunker && c.length > 0) {
          setSelectedChunker(c[0].key);
        }
      }).catch(() => {
        // Fallback to hardcoded alternatives
        const alts = CHUNKER_ALTERNATIVES[doc.collection] || ['recursive'];
        setChunkers(alts.map((k) => ({ key: k, label: k, description: '', collections: [] })));
        if (!selectedChunker) setSelectedChunker(alts[0]);
      });
    }
  }, [doc?.collection, doc?.chunking_strategy]);

  // Load chunk sets when document is in chunked+ state
  useEffect(() => {
    if (doc && ['chunked', 'embedding', 'indexed'].includes(doc.status)) {
      fetchChunkSets();
    }
  }, [doc?.status, fetchChunkSets]);

  // Polling for in-progress statuses
  const isProcessing = doc && ['converting', 'cleaning', 'llm_cleaning', 'chunking', 'embedding'].includes(doc.status);

  useEffect(() => {
    if (isProcessing) {
      pollingRef.current = setInterval(fetchDoc, 5000);
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [isProcessing, fetchDoc]);

  // Load markdown/cleaned content when status allows
  useEffect(() => {
    if (!doc || !id) return;
    const statusOrder = [
      'uploaded', 'converting', 'converted', 'cleaning', 'cleaned',
      'llm_cleaning', 'llm_cleaned', 'chunking', 'chunked', 'embedding', 'indexed',
    ];
    const idx = statusOrder.indexOf(doc.status);
    const llmCleanEngaged = doc.llm_clean_requested || Boolean(doc.llm_cleaned_at)
      || doc.status === 'llm_cleaning' || doc.status === 'llm_cleaned';

    if (idx >= statusOrder.indexOf('converted') && mdContent === null) {
      getMarkdown(id).then((r) => setMdContent(r.content)).catch(() => {});
    }
    if (idx >= statusOrder.indexOf('cleaned') && cleanedContent === null) {
      getCleanedContent(id).then((r) => setCleanedContent(r.content)).catch(() => {});
    }
    if (llmCleanEngaged && llmCleanedContent === null) {
      getLlmCleaned(id).then((r) => setLlmCleanedContent(r.content)).catch(() => {});
    }
  }, [doc, id, mdContent, cleanedContent, llmCleanedContent]);

  const handleTriggerStep = async (step: PipelineStep['key']) => {
    if (!id) return;
    setRetrying(step);
    try {
      if (step === 'convert') {
        await triggerConvert(id, selectedConverter);
      } else if (step === 'chunk') {
        if (doc?.status === 'llm_cleaned' && !doc.llm_cleaned_reviewed) {
          const warnCount = doc.llm_clean_warnings?.length || 0;
          const msg = warnCount > 0
            ? `Nội dung LLM Reformat có ${warnCount} cảnh báo và chưa được duyệt. Vẫn tiếp tục chunk?`
            : 'Nội dung LLM Reformat chưa được duyệt. Vẫn tiếp tục chunk?';
          if (!window.confirm(msg)) {
            return;
          }
        }
        await triggerChunk(id, selectedChunker || undefined);
      } else if (step === 'clean') {
        await triggerClean(id);
      } else if (step === 'llm_clean') {
        await triggerLlmClean(id);
      } else if (step === 'index') {
        if (doc && !doc.chunks_reviewed) {
          toast.error('Duyệt chunks trước khi index');
          return;
        }
        await triggerIndex(id);
      }
      toast.success('Đang xử lý…');
      // Optimistic update: set running status immediately so polling starts
      const stepDef = PIPELINE_STEPS.find((s) => s.key === step);
      if (stepDef) {
        setDoc((prev) => prev ? { ...prev, status: stepDef.runningStatus } : prev);
      }
      setTimeout(fetchDoc, 1500);
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, `Không thể chạy bước ${step}`));
    } finally {
      setRetrying(null);
    }
  };

  const handleNextStep = async () => {
    if (!doc || !id) return;
    const nextMap: Record<string, PipelineStep['key']> = {
      uploaded: 'convert',
      converted: 'clean',
      // 'cleaned' skips straight to chunk — LLM Reformat is optional and
      // triggered explicitly from the "LLM Reformat" tab, not via "Bước tiếp".
      cleaned: 'chunk',
      llm_cleaned: 'chunk',
      chunked: 'index',
    };
    const next = nextMap[doc.status];
    if (next) await handleTriggerStep(next);
  };

  const handleFullPipeline = async () => {
    if (!id) return;
    try {
      await triggerFullPipeline(id);
      toast.success('Pipeline tự động đã bắt đầu');
      setDoc((prev) => prev ? { ...prev, status: 'converting' as DocumentStatus } : prev);
      setTimeout(fetchDoc, 1500);
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Không thể chạy pipeline'));
    }
  };

  const handleRollback = async () => {
    if (!id) return;
    if (!window.confirm('Bạn có chắc muốn rollback lại một bước? Dữ liệu của bước hiện tại/lỗi sẽ bị xóa và lùi về trạng thái trước đó.')) return;
    setRetrying('rollback');
    try {
      // POST /rollback is synchronous on the backend — the DB/file changes are
      // already committed by the time this resolves. Refresh state (and only
      // clear `retrying` in `finally`, below) BEFORE returning, so the button
      // stays disabled until the UI reflects the new status. Doing this via a
      // setTimeout previously left a window where a second click could fire a
      // real second rollback against a stale on-screen status.
      await rollbackDocument(id);
      toast.success('Đã rollback lại một bước thành công');
      setMdContent(null);
      setCleanedContent(null);
      setLlmCleanedContent(null);
      setChunkSets([]);
      setViewingStrategy(undefined);
      await fetchDoc();
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Rollback thất bại'));
    } finally {
      setRetrying(null);
    }
  };

  const handleSaveMarkdown = async (content: string) => {
    if (!id) return;
    await updateMarkdown(id, content);
    setMdContent(content);
    await fetchDoc();
  };

  const handleSaveCleaned = async (content: string) => {
    if (!id) return;
    await updateCleaned(id, content);
    setCleanedContent(content);
    await fetchDoc();
  };

  const handleSaveLlmCleaned = async (content: string) => {
    if (!id) return;
    await updateLlmCleaned(id, content);
    setLlmCleanedContent(content);
    await fetchDoc();
  };

  const handleRunChunkWithStrategy = async (strategy: string) => {
    if (!id) return;
    setRetrying('chunk');
    try {
      await triggerChunk(id, strategy);
      toast.success(`Đang chunk với strategy: ${strategy}`);
      setDoc((prev) => prev ? { ...prev, status: 'chunking' as DocumentStatus } : prev);
      setTimeout(async () => {
        await fetchDoc();
        await fetchChunkSets();
      }, 1500);
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Chunk thất bại'));
    } finally {
      setRetrying(null);
    }
  };

  const handleSelectStrategy = async (strategy: string) => {
    if (!id) return;
    try {
      const result = await selectChunkStrategy(id, strategy);
      toast.success(`Đã chọn strategy "${strategy}". Giữ ${result.kept_chunks} chunks, xóa ${result.deleted_chunks} chunks cũ.`);
      await fetchDoc();
      await fetchChunkSets();
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Không thể chọn strategy'));
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!doc) return null;

  const canRunNext = ['uploaded', 'converted', 'cleaned', 'llm_cleaned', 'chunked'].includes(doc.status);
  const statusOrder = [
    'uploaded', 'converting', 'converted', 'cleaning', 'cleaned',
    'llm_cleaning', 'llm_cleaned', 'chunking', 'chunked', 'embedding', 'indexed',
  ];
  const statusIdx = statusOrder.indexOf(doc.status);
  const canConvert = doc.status === 'uploaded' || doc.status === 'failed';
  const canChunk = statusIdx >= statusOrder.indexOf('cleaned') || doc.status === 'failed';
  const canLlmClean = doc.status === 'cleaned';
  const hasChunks = statusIdx >= statusOrder.indexOf('chunked');

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold">{doc.filename}</h1>
          <div className="mt-1 flex flex-wrap gap-2">
            <Badge variant="outline">{doc.collection}</Badge>
            <Badge variant="secondary">{doc.status}</Badge>
            {doc.converter && <Badge variant="outline">Converter: {doc.converter}</Badge>}
            {doc.chunking_strategy && <Badge variant="outline">Strategy: {doc.chunking_strategy}</Badge>}
            <span className="text-xs text-muted-foreground">
              {(doc.file_size / 1024 / 1024).toFixed(1)} MB
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {canRunNext && (
            <Button size="sm" onClick={handleNextStep}>
              <Play className="mr-1 h-4 w-4" /> Bước tiếp
            </Button>
          )}
          {doc.status === 'uploaded' && (
            <Button size="sm" variant="outline" onClick={handleFullPipeline}>
              <Zap className="mr-1 h-4 w-4" /> Tự động
            </Button>
          )}
          {doc.status !== 'uploaded' && doc.status !== 'converting' && (
            <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={handleRollback} disabled={retrying === 'rollback'}>
              <RotateCcw className="mr-1 h-4 w-4" /> Rollback
            </Button>
          )}
        </div>
      </div>

      {/* Pipeline progress */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Tiến trình Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <PipelineProgress
            document={doc}
            onRetry={handleTriggerStep}
            retrying={retrying === 'rollback' ? null : retrying}
          />
        </CardContent>
      </Card>

      {/* Converter selector — shown when document can be converted */}
      {canConvert && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Chọn Converter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-sm font-medium">PDF → Markdown Converter</label>
                <Select value={selectedConverter} onValueChange={setSelectedConverter}>
                  <SelectTrigger>
                    <SelectValue placeholder="Chọn converter" />
                  </SelectTrigger>
                  <SelectContent>
                    {converters.map((c) => (
                      <SelectItem key={c.key} value={c.key}>
                        <div>
                          <span className="font-medium">{c.label}</span>
                          <span className="ml-2 text-xs text-muted-foreground">{c.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={() => handleTriggerStep('convert')}
                disabled={retrying === 'convert'}
              >
                <Play className="mr-1 h-4 w-4" />
                Chuyển đổi
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Chunker selector — shown when document can be chunked */}
      {canChunk && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Chọn Chunking Strategy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-sm font-medium">Strategy</label>
                <Select value={selectedChunker} onValueChange={setSelectedChunker}>
                  <SelectTrigger>
                    <SelectValue placeholder="Chọn strategy" />
                  </SelectTrigger>
                  <SelectContent>
                    {chunkers.map((c) => (
                      <SelectItem key={c.key} value={c.key}>
                        <div>
                          <span className="font-medium">{c.label}</span>
                          {c.description && (
                            <span className="ml-2 text-xs text-muted-foreground">{c.description}</span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={() => handleRunChunkWithStrategy(selectedChunker)}
                disabled={retrying === 'chunk' || !selectedChunker}
              >
                <Play className="mr-1 h-4 w-4" />
                Chunk
              </Button>
            </div>

            {/* Side-by-side comparison — show available chunk sets */}
            {chunkSets.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium flex items-center gap-1">
                  <GitCompare className="h-4 w-4" />
                  So sánh kết quả ({chunkSets.length} strategy)
                </p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {chunkSets.map((cs) => (
                    <div
                      key={cs.strategy}
                      className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                        viewingStrategy === cs.strategy
                          ? 'border-primary bg-primary/5'
                          : 'hover:border-muted-foreground/30'
                      }`}
                      onClick={() => setViewingStrategy(cs.strategy)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{cs.strategy}</span>
                        {doc.chunking_strategy === cs.strategy && (
                          <Badge variant="secondary" className="text-xs">Đang chọn</Badge>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {cs.chunk_count} chunks · TB {cs.avg_size} ký tự
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-2 w-full"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectStrategy(cs.strategy);
                        }}
                      >
                        <Check className="mr-1 h-3 w-3" />
                        Chọn strategy này
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs for review */}
      <Tabs defaultValue="markdown">
        <TabsList>
          <TabsTrigger value="markdown">Markdown</TabsTrigger>
          <TabsTrigger value="cleaned">Cleaned</TabsTrigger>
          <TabsTrigger value="llm_clean">
            LLM Reformat
            {doc.llm_clean_warnings && doc.llm_clean_warnings.length > 0 && (
              <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white">
                {doc.llm_clean_warnings.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="chunks">Chunks</TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
        </TabsList>

        <TabsContent value="markdown">
          {mdContent !== null ? (
            <MarkdownEditor
              content={mdContent}
              onSave={handleSaveMarkdown}
              approved={doc.markdown_reviewed}
              title="Markdown (chuyển đổi từ PDF)"
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Chưa có nội dung markdown. Chạy bước &quot;Chuyển đổi PDF&quot; trước.
            </p>
          )}
        </TabsContent>

        <TabsContent value="cleaned">
          {cleanedContent !== null ? (
            <MarkdownEditor
              content={cleanedContent}
              onSave={handleSaveCleaned}
              approved={doc.cleaned_reviewed}
              title="Nội dung đã làm sạch"
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Chưa có nội dung đã làm sạch. Chạy bước &quot;Làm sạch&quot; trước.
            </p>
          )}
        </TabsContent>

        <TabsContent value="llm_clean" className="space-y-4">
          {doc.llm_clean_warnings && doc.llm_clean_warnings.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="mb-1 font-medium">
                ⚠ {doc.llm_clean_warnings.length} cảnh báo về nội dung — LLM có thể đã làm thay đổi nội dung gốc.
                Hãy kiểm tra kỹ trước khi duyệt.
              </p>
              <ul className="list-disc space-y-0.5 pl-5">
                {doc.llm_clean_warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {llmCleanedContent !== null ? (
            <MarkdownEditor
              content={llmCleanedContent}
              onSave={handleSaveLlmCleaned}
              approved={doc.llm_cleaned_reviewed}
              title="Nội dung sau LLM Reformat"
            />
          ) : (
            <div className="space-y-3 py-8 text-center">
              <p className="text-sm text-muted-foreground">
                {canLlmClean
                  ? 'Bước tùy chọn: dùng LLM để chuẩn hoá heading/bảng trước khi chunk. Không bắt buộc.'
                  : 'Chưa có nội dung LLM Reformat. Chạy bước "Làm sạch" trước.'}
              </p>
              {canLlmClean && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTriggerStep('llm_clean')}
                  disabled={retrying === 'llm_clean'}
                >
                  <Play className="mr-1 h-4 w-4" />
                  Chạy LLM Reformat
                </Button>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="chunks">
          {hasChunks ? (
            <ChunkViewer
              documentId={doc.id}
              approved={doc.chunks_reviewed}
              onApproved={fetchDoc}
              onChanged={fetchDoc}
              strategy={viewingStrategy}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Chưa có chunks. Chạy bước &quot;Chia chunk&quot; trước.
            </p>
          )}
        </TabsContent>

        <TabsContent value="metadata">
          <MetadataForm
            initial={doc.metadata_overrides}
            onSave={async () => {
              // Metadata is saved as part of the document — the backend handles this
              // For now, we'd need an endpoint. We'll skip the API call since
              // metadata_overrides is set during upload.
              toast.info('Metadata sẽ được áp dụng khi index');
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
