import { useState, useEffect, useRef, useCallback, type FormEvent } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import {
  getSystemStats, triggerCrawler, getCrawlerStatus,
  toggleConfig, getLLMConfig, updateLLMConfig,
  activateApiKey, createApiKey, getApiKeys,
} from '@/services/adminApi';
import type {
  SystemStats,
  CrawlerStatus,
  LLMConfig,
  ApiKeyProvider,
  ApiKeyRecord,
  CrawlerCollectionResult,
  CrawlerSavedChunkPreview,
} from '@/types/adminStats';
import { Settings, Loader2, PlayCircle, CheckCircle2, XCircle, Save, Key, Cpu, Database, Plus, RefreshCw } from 'lucide-react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const TOGGLE_LABELS: Record<string, string> = {
  agent_enabled: 'Agent Mode',
  self_eval_enabled: 'Self Evaluation',
  tavily_fallback_enabled: 'Tavily Fallback',
  crawler_enabled: 'Auto Crawler',
  redis_enabled: 'Redis Cache',
  mongodb_enabled: 'MongoDB',
  reflection_enabled: 'Reflection',
  domain_routing_enabled: 'Domain Routing',
};

type ModelOption = { value: string; label: string };

const GEMINI_MODEL_OPTIONS: ModelOption[] = [
  { value: 'gemini-3.1-flash-lite-preview', label: 'Gemini 3.1 Flash Lite Preview' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
];

const AGENT_MODEL_OPTIONS: ModelOption[] = [
  { value: 'qwen2.5-7b-instruct', label: 'Qwen 2.5 7B Instruct' },
  ...GEMINI_MODEL_OPTIONS,
];

const API_KEY_PROVIDER_LABELS: Record<ApiKeyProvider, string> = {
  google: 'Google',
  tavily: 'Tavily',
};

function formatApiKeyDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function modelOptionsWithCurrent(options: ModelOption[], value: string) {
  if (!value || options.some((option) => option.value === value)) return options;
  return [{ value, label: `${value} (đang dùng)` }, ...options];
}

function ModelSelectField({
  id,
  label,
  options,
  value,
  onValueChange,
}: {
  id: string;
  label: string;
  options: ModelOption[];
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs">{label}</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id}>
          <SelectValue placeholder="Chọn model" />
        </SelectTrigger>
        <SelectContent>
          {modelOptionsWithCurrent(options, value).map((option) => (
            <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function numberFromUnknown(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function stringFromUnknown(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function toSavedChunkPreview(value: unknown): CrawlerSavedChunkPreview | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  return {
    chunk_id: stringFromUnknown(record.chunk_id),
    title: stringFromUnknown(record.title),
    source: stringFromUnknown(record.source),
    url: stringFromUnknown(record.url),
    section_label: stringFromUnknown(record.section_label) || undefined,
    content_preview: stringFromUnknown(record.content_preview),
  };
}

function collectCrawlerCollectionResults(value: unknown): CrawlerCollectionResult[] {
  if (Array.isArray(value)) {
    return value.flatMap(collectCrawlerCollectionResults);
  }
  if (!value || typeof value !== 'object') return [];

  const record = value as Record<string, unknown>;
  const nested = Object.values(record).flatMap(collectCrawlerCollectionResults);
  const collection = stringFromUnknown(record.collection);
  const pipeline = stringFromUnknown(record.pipeline);
  if (!collection || !pipeline) return nested;

  const savedChunks = Array.isArray(record.saved_chunks)
    ? record.saved_chunks.map(toSavedChunkPreview).filter((chunk): chunk is CrawlerSavedChunkPreview => Boolean(chunk))
    : [];

  return [{
    collection,
    pipeline,
    status: stringFromUnknown(record.status) || 'unknown',
    new_articles: numberFromUnknown(record.new_articles),
    new_chunks: numberFromUnknown(record.new_chunks),
    indexed: numberFromUnknown(record.indexed),
    expired_removed: numberFromUnknown(record.expired_removed),
    saved_chunks: savedChunks,
  }, ...nested];
}

export default function SystemTab() {
  const { data, loading, error, refetch } = useAdminFetch<SystemStats>(
    () => getSystemStats(),
    [],
  );

  const [configState, setConfigState] = useState<Record<string, boolean>>({});
  const [togglingKey, setTogglingKey] = useState<string | null>(null);

  // LLM config state
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null);
  const [llmForm, setLlmForm] = useState<Record<string, string>>({});
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmSaving, setLlmSaving] = useState(false);
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([]);
  const [fallbackProviders, setFallbackProviders] = useState<ApiKeyProvider[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [apiKeyDialogOpen, setApiKeyDialogOpen] = useState(false);
  const [apiKeyCreating, setApiKeyCreating] = useState(false);
  const [activatingApiKeyId, setActivatingApiKeyId] = useState<string | null>(null);
  const [apiKeyForm, setApiKeyForm] = useState<{
    provider: ApiKeyProvider;
    name: string;
    key: string;
  }>({ provider: 'google', name: '', key: '' });

  // Crawler state
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus | null>(null);
  const [crawlTarget, setCrawlTarget] = useState('all');
  const [triggering, setTriggering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Sync config state when data loads
  useEffect(() => {
    if (data?.config) {
      setConfigState(data.config);
    }
  }, [data]);

  // Fetch LLM config
  useEffect(() => {
    setLlmLoading(true);
    getLLMConfig()
      .then((cfg) => {
        setLlmConfig(cfg);
        setLlmForm({
          chat_model: cfg.chat_model,
          chat_temperature: String(cfg.chat_temperature),
          chat_max_tokens: String(cfg.chat_max_tokens),
          agent_model: cfg.agent_model,
          reflection_model: cfg.reflection_model,
        });
      })
      .catch(() => toast.error('Không thể tải cấu hình LLM'))
      .finally(() => setLlmLoading(false));
  }, []);

  const refreshApiKeys = useCallback(async () => {
    setApiKeysLoading(true);
    try {
      const result = await getApiKeys();
      setApiKeys(result.keys);
      setFallbackProviders(result.fallback_providers);
    } catch {
      toast.error('Không thể tải danh sách API key');
    } finally {
      setApiKeysLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshApiKeys();
  }, [refreshApiKeys]);

  // Fetch crawler status
  useEffect(() => {
    getCrawlerStatus().then(setCrawlerStatus).catch(() => {});
  }, []);

  // Poll while crawling
  useEffect(() => {
    if (crawlerStatus?.is_running) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await getCrawlerStatus();
          setCrawlerStatus(status);
          if (!status.is_running) {
            if (pollRef.current) clearInterval(pollRef.current);
            toast.success('Crawl hoàn tất');
          }
        } catch { /* ignore */ }
      }, 5000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [crawlerStatus?.is_running]);

  const handleToggle = async (key: string, newVal: boolean) => {
    setTogglingKey(key);
    try {
      await toggleConfig(key, newVal);
      setConfigState((prev) => ({ ...prev, [key]: newVal }));
      toast.success(`${TOGGLE_LABELS[key] || key}: ${newVal ? 'BẬT' : 'TẮT'}`);
    } catch {
      toast.error(`Không thể thay đổi ${key}`);
    } finally {
      setTogglingKey(null);
    }
  };

  const handleLLMSave = async () => {
    setLlmSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (llmForm.chat_model && llmForm.chat_model !== llmConfig?.chat_model)
        body.chat_model = llmForm.chat_model;
      if (llmForm.agent_model && llmForm.agent_model !== llmConfig?.agent_model)
        body.agent_model = llmForm.agent_model;
      if (llmForm.reflection_model && llmForm.reflection_model !== llmConfig?.reflection_model)
        body.reflection_model = llmForm.reflection_model;
      const temp = parseFloat(llmForm.chat_temperature);
      if (!isNaN(temp) && temp !== llmConfig?.chat_temperature)
        body.chat_temperature = temp;
      const maxTok = parseInt(llmForm.chat_max_tokens);
      if (!isNaN(maxTok) && maxTok !== llmConfig?.chat_max_tokens)
        body.chat_max_tokens = maxTok;

      if (Object.keys(body).length === 0) {
        toast.info('Không có thay đổi nào');
        return;
      }

      const res = await updateLLMConfig(body);
      toast.success(`Đã cập nhật: ${Object.keys(res.updated).join(', ')}`);
      // Refresh config
      const cfg = await getLLMConfig();
      setLlmConfig(cfg);
      setLlmForm((prev) => ({
        ...prev,
        chat_model: cfg.chat_model,
        chat_temperature: String(cfg.chat_temperature),
        chat_max_tokens: String(cfg.chat_max_tokens),
        agent_model: cfg.agent_model,
        reflection_model: cfg.reflection_model,
      }));
    } catch {
      toast.error('Không thể cập nhật cấu hình LLM');
    } finally {
      setLlmSaving(false);
    }
  };

  const resetApiKeyForm = () => {
    setApiKeyForm({ provider: 'google', name: '', key: '' });
  };

  const handleCreateApiKey = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKeyForm.name.trim() || !apiKeyForm.key.trim()) {
      toast.info('Tên hiển thị và giá trị key là bắt buộc');
      return;
    }

    setApiKeyCreating(true);
    try {
      await createApiKey({
        provider: apiKeyForm.provider,
        name: apiKeyForm.name.trim(),
        key: apiKeyForm.key.trim(),
      });
      toast.success('Đã thêm và kích hoạt API key mới');
      setApiKeyDialogOpen(false);
      resetApiKeyForm();
      await refreshApiKeys();
    } catch {
      toast.error('Không thể thêm API key');
    } finally {
      setApiKeyCreating(false);
    }
  };

  const handleActivateApiKey = async (key: ApiKeyRecord) => {
    const confirmed = window.confirm(
      `Kích hoạt ${key.name}? Key ${API_KEY_PROVIDER_LABELS[key.provider]} đang dùng sẽ chuyển sang inactive.`,
    );
    if (!confirmed) return;

    setActivatingApiKeyId(key.id);
    try {
      await activateApiKey(key.id);
      toast.success(`Đã kích hoạt ${key.name}`);
      await refreshApiKeys();
    } catch {
      toast.error('Không thể kích hoạt API key');
    } finally {
      setActivatingApiKeyId(null);
    }
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerCrawler(crawlTarget);
      toast.success('Đã khởi động crawl');
      const status = await getCrawlerStatus();
      setCrawlerStatus(status);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 429) {
          toast.error(axiosErr.response.data?.detail || 'Vui lòng đợi trước khi trigger lại');
        } else if (axiosErr.response?.status === 409) {
          toast.error('Crawl đang chạy');
        } else {
          toast.error(axiosErr.response?.data?.detail || 'Không thể trigger crawl');
        }
      } else {
        toast.error('Không thể trigger crawl');
      }
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Không thể tải thông tin hệ thống</span>
          <Button variant="outline" size="sm" onClick={refetch}>Thử lại</Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) {
    return <EmptyState icon={Settings} title="Không có dữ liệu hệ thống" />;
  }

  const docStatusData = Object.entries(data.documents_by_status).map(([status, count]) => ({ name: status, value: count }));
  const docCollData = Object.entries(data.documents_by_collection).map(([coll, count]) => ({ name: coll, value: count }));
  const crawlCollectionResults = collectCrawlerCollectionResults(crawlerStatus?.last_result);

  return (
    <div className="space-y-6">
      {/* System toggles */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <p className="text-sm font-semibold mb-4">Cấu hình hệ thống</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(configState).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between rounded-lg border border-border bg-background px-4 py-3">
              <Label htmlFor={`toggle-${key}`} className="text-xs text-muted-foreground cursor-pointer">
                {TOGGLE_LABELS[key] || key.replace(/_/g, ' ')}
              </Label>
              <Switch
                id={`toggle-${key}`}
                checked={val}
                disabled={togglingKey === key}
                onCheckedChange={(checked) => handleToggle(key, checked)}
              />
            </div>
          ))}
        </div>
      </div>

      {/* LLM Configuration */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="h-4 w-4 text-muted-foreground" />
          <p className="text-sm font-semibold">Cấu hình LLM</p>
        </div>

        {llmLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
          </div>
        ) : (
          <div className="space-y-5">
            {/* API Keys */}
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Key className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">API Keys</span>
                </div>
                <Button size="sm" variant="outline" className="gap-2" onClick={() => setApiKeyDialogOpen(true)}>
                  <Plus className="h-3.5 w-3.5" />
                  Thêm API key
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Key mới active ngay. Key cùng provider trước đó vẫn được giữ lại để kích hoạt lại khi cần.
              </p>
              {fallbackProviders.length > 0 && (
                <Alert>
                  <AlertDescription>
                    {fallbackProviders.map((provider) => API_KEY_PROVIDER_LABELS[provider]).join(', ')} đang dùng key fallback ngoài registry.
                  </AlertDescription>
                </Alert>
              )}
              {apiKeysLoading ? (
                <Skeleton className="h-32 rounded-lg" />
              ) : apiKeys.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                  Chưa có API key được quản lý trong admin.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tên</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>Fingerprint</TableHead>
                        <TableHead>Trạng thái</TableHead>
                        <TableHead>Cập nhật</TableHead>
                        <TableHead className="text-right">Thao tác</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {apiKeys.map((key) => (
                        <TableRow key={key.id}>
                          <TableCell className="min-w-[180px] font-medium">{key.name}</TableCell>
                          <TableCell>{API_KEY_PROVIDER_LABELS[key.provider]}</TableCell>
                          <TableCell className="font-mono text-xs">{key.fingerprint}</TableCell>
                          <TableCell>
                            <Badge variant={key.status === 'active' ? 'default' : 'secondary'}>
                              {key.status === 'active' ? 'Active' : 'Inactive'}
                            </Badge>
                          </TableCell>
                          <TableCell className="min-w-[150px] text-xs text-muted-foreground">
                            {formatApiKeyDate(key.updated_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            {key.status === 'inactive' ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-2"
                                disabled={activatingApiKeyId === key.id}
                                onClick={() => handleActivateApiKey(key)}
                              >
                                {activatingApiKeyId === key.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <RefreshCw className="h-3.5 w-3.5" />
                                )}
                                Kích hoạt
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">Đang dùng</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>

            {/* Model settings */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Models</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <ModelSelectField
                  id="chat-model"
                  label="Chat Model"
                  options={GEMINI_MODEL_OPTIONS}
                  value={llmForm.chat_model}
                  onValueChange={(chat_model) => setLlmForm((p) => ({ ...p, chat_model }))}
                />
                <ModelSelectField
                  id="agent-model"
                  label="Agent Model"
                  options={AGENT_MODEL_OPTIONS}
                  value={llmForm.agent_model}
                  onValueChange={(agent_model) => setLlmForm((p) => ({ ...p, agent_model }))}
                />
                <ModelSelectField
                  id="reflection-model"
                  label="Reflection Model"
                  options={GEMINI_MODEL_OPTIONS}
                  value={llmForm.reflection_model}
                  onValueChange={(reflection_model) => setLlmForm((p) => ({ ...p, reflection_model }))}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="chat-temp" className="text-xs">Temperature</Label>
                  <Input
                    id="chat-temp"
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={llmForm.chat_temperature}
                    onChange={(e) => setLlmForm((p) => ({ ...p, chat_temperature: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="chat-tokens" className="text-xs">Max Tokens</Label>
                  <Input
                    id="chat-tokens"
                    type="number"
                    step="256"
                    min="256"
                    value={llmForm.chat_max_tokens}
                    onChange={(e) => setLlmForm((p) => ({ ...p, chat_max_tokens: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            <Button onClick={handleLLMSave} disabled={llmSaving} className="gap-2">
              {llmSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Lưu cấu hình
            </Button>
          </div>
        )}
      </div>

      <Dialog
        open={apiKeyDialogOpen}
        onOpenChange={(open) => {
          setApiKeyDialogOpen(open);
          if (!open) resetApiKeyForm();
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Thêm API key</DialogTitle>
            <DialogDescription>
              Key mới sẽ active ngay. Key active hiện tại của provider này sẽ chuyển sang inactive.
            </DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleCreateApiKey}>
            <div className="space-y-1.5">
              <Label htmlFor="api-key-provider" className="text-xs">Provider</Label>
              <Select
                value={apiKeyForm.provider}
                onValueChange={(provider) => setApiKeyForm((prev) => ({
                  ...prev,
                  provider: provider as ApiKeyProvider,
                }))}
              >
                <SelectTrigger id="api-key-provider">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="google">Google</SelectItem>
                  <SelectItem value="tavily">Tavily</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="api-key-name" className="text-xs">Tên hiển thị</Label>
              <Input
                id="api-key-name"
                value={apiKeyForm.name}
                maxLength={120}
                placeholder="Production key"
                onChange={(event) => setApiKeyForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="api-key-secret" className="text-xs">API key</Label>
              <Input
                id="api-key-secret"
                type="password"
                value={apiKeyForm.key}
                placeholder="Nhập key mới..."
                onChange={(event) => setApiKeyForm((prev) => ({ ...prev, key: event.target.value }))}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setApiKeyDialogOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={apiKeyCreating} className="gap-2">
                {apiKeyCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Thêm key
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Service status */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <p className="text-sm font-semibold mb-3">Trạng thái dịch vụ</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-background px-4 py-3 flex items-center justify-between">
            <span className="text-xs">MongoDB</span>
            <Badge variant={data.mongo_status === 'ok' ? 'default' : 'destructive'}>
              {data.mongo_status}
            </Badge>
          </div>
          <div className="rounded-lg border border-border bg-background px-4 py-3 flex items-center justify-between">
            <span className="text-xs">Redis</span>
            <Badge variant={data.redis_status === 'ok' ? 'default' : 'secondary'}>
              {data.redis_status}
            </Badge>
          </div>
        </div>
      </div>

      {/* Documents charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {docStatusData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <p className="text-sm font-semibold mb-3">Tài liệu theo trạng thái</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={docStatusData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {docCollData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <p className="text-sm font-semibold mb-3">Tài liệu theo collection</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={docCollData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {docCollData.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Crawler management */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <p className="text-sm font-semibold mb-4">Crawler</p>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <Select value={crawlTarget} onValueChange={setCrawlTarget}>
            <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              <SelectItem value="kehoach">Kế hoạch</SelectItem>
              <SelectItem value="quydinh">Quy định</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={handleTrigger}
            disabled={triggering || crawlerStatus?.is_running}
            className="gap-2"
          >
            {crawlerStatus?.is_running ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Đang chạy...</>
            ) : (
              <><PlayCircle className="h-4 w-4" /> Chạy Crawl</>
            )}
          </Button>
          {data.crawler.enabled && (
            <span className="text-xs text-muted-foreground">
              Lịch tự động: {String(data.crawler.schedule_hour).padStart(2, '0')}:{String(data.crawler.schedule_minute).padStart(2, '0')} hàng ngày
            </span>
          )}
        </div>

        {/* Crawler status */}
        {crawlerStatus?.is_running && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950">
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            <span className="text-sm text-blue-700 dark:text-blue-300">Crawler đang chạy...</span>
          </div>
        )}

        {crawlerStatus?.last_result && !crawlerStatus.is_running && (
          <div className={`flex items-center gap-2 p-3 rounded-lg ${
            crawlerStatus.last_result.status === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950'
              : 'bg-red-50 dark:bg-red-950'
          }`}>
            {crawlerStatus.last_result.status === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <div className="text-sm">
              <span className="font-medium">
                {crawlerStatus.last_result.status === 'success' ? 'Thành công' : 'Lỗi'}
              </span>
              {crawlerStatus.last_result.error && (
                <span className="ml-2 text-muted-foreground">{crawlerStatus.last_result.error}</span>
              )}
              {crawlerStatus.last_result.completed_at && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {new Date(crawlerStatus.last_result.completed_at).toLocaleString('vi-VN')}
                </span>
              )}
            </div>
          </div>
        )}

        {crawlCollectionResults.length > 0 && !crawlerStatus?.is_running && (
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-semibold">Dữ liệu đã lưu vào collection</p>
            </div>

            {crawlCollectionResults.map((result) => (
              <section
                key={`${result.collection}-${result.pipeline}`}
                className="rounded-lg border border-border bg-background p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-foreground">{result.collection}</p>
                      <Badge variant={result.status === 'success' ? 'default' : 'destructive'}>
                        {result.pipeline}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {result.new_articles} bài mới, {result.new_chunks} chunks tạo, {result.indexed} chunks đã index
                    </p>
                  </div>
                  {result.expired_removed > 0 && (
                    <Badge variant="secondary">{result.expired_removed} chunks hết hạn đã xóa</Badge>
                  )}
                </div>

                {result.saved_chunks.length > 0 ? (
                  <div className="mt-3 divide-y divide-border overflow-hidden rounded-lg border border-border">
                    {result.saved_chunks.map((chunk) => (
                      <article key={chunk.chunk_id} className="bg-card px-4 py-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="break-words text-sm font-medium text-foreground">
                              {chunk.title || 'Chunk mới'}
                            </p>
                            <p className="mt-1 break-all text-xs text-muted-foreground">
                              {chunk.chunk_id}
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            {chunk.source && <Badge variant="outline">{chunk.source}</Badge>}
                            {chunk.section_label && <Badge variant="secondary">Mục {chunk.section_label}</Badge>}
                          </div>
                        </div>
                        {chunk.url && (
                          <p className="mt-2 truncate text-xs text-primary" title={chunk.url}>{chunk.url}</p>
                        )}
                        {chunk.content_preview && (
                          <p className="mt-2 break-words text-xs leading-5 text-muted-foreground">
                            {chunk.content_preview}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                    Lần crawl này không index chunk mới cho collection này.
                  </p>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
