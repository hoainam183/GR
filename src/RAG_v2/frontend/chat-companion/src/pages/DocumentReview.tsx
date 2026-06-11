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
  triggerChunk,
  triggerIndex,
  triggerFullPipeline,
  getMarkdown,
  updateMarkdown,
  getCleanedContent,
  updateCleaned,
  listConverters,
  listChunkers,
  listChunkStrategies,
  selectChunkStrategy,
  rollbackDocument,
} from '@/services/adminApi';
import type {
  DocumentDetail,
  PipelineStep,
  ConverterOption,
  ChunkerOption,
  ChunkStrategySummary,
} from '@/types/admin';
import { CHUNKER_ALTERNATIVES } from '@/types/admin';
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
  const isProcessing = doc && ['converting', 'cleaning', 'chunking', 'embedding'].includes(doc.status);

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
    const statusOrder = ['uploaded', 'converting', 'converted', 'cleaning', 'cleaned', 'chunking', 'chunked', 'embedding', 'indexed'];
    const idx = statusOrder.indexOf(doc.status);

    if (idx >= statusOrder.indexOf('converted') && mdContent === null) {
      getMarkdown(id).then((r) => setMdContent(r.content)).catch(() => {});
    }
    if (idx >= statusOrder.indexOf('cleaned') && cleanedContent === null) {
      getCleanedContent(id).then((r) => setCleanedContent(r.content)).catch(() => {});
    }
  }, [doc, id, mdContent, cleanedContent]);

  const handleTriggerStep = async (step: PipelineStep['key']) => {
    if (!id) return;
    setRetrying(step);
    try {
      if (step === 'convert') {
        await triggerConvert(id, selectedConverter);
      } else if (step === 'chunk') {
        await triggerChunk(id, selectedChunker || undefined);
      } else if (step === 'clean') {
        await triggerClean(id);
      } else if (step === 'index') {
        if (doc && !doc.chunks_reviewed) {
          toast.error('Duyệt chunks trước khi index');
          return;
        }
        await triggerIndex(id);
      }
      toast.success('Đang xử lý…');
      // Start polling
      setTimeout(fetchDoc, 1000);
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
      cleaned: 'chunk',
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
      setTimeout(fetchDoc, 1000);
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Không thể chạy pipeline'));
    }
  };

  const handleRollback = async () => {
    if (!id) return;
    if (!window.confirm('Bạn có chắc muốn rollback lại một bước? Dữ liệu của bước hiện tại/lỗi sẽ bị xóa và lùi về trạng thái trước đó.')) return;
    setRetrying('rollback');
    try {
      await rollbackDocument(id);
      toast.success('Đã rollback lại một bước thành công');
      setTimeout(async () => {
        setMdContent(null);
        setCleanedContent(null);
        setChunkSets([]);
        setViewingStrategy(undefined);
        await fetchDoc();
      }, 1000);
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

  const handleRunChunkWithStrategy = async (strategy: string) => {
    if (!id) return;
    setRetrying('chunk');
    try {
      await triggerChunk(id, strategy);
      toast.success(`Đang chunk với strategy: ${strategy}`);
      setTimeout(async () => {
        await fetchDoc();
        await fetchChunkSets();
      }, 2000);
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

  const canRunNext = ['uploaded', 'converted', 'cleaned', 'chunked'].includes(doc.status);
  const statusOrder = ['uploaded', 'converting', 'converted', 'cleaning', 'cleaned', 'chunking', 'chunked', 'embedding', 'indexed'];
  const statusIdx = statusOrder.indexOf(doc.status);
  const canConvert = doc.status === 'uploaded' || doc.status === 'failed';
  const canChunk = statusIdx >= statusOrder.indexOf('cleaned') || doc.status === 'failed';
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
