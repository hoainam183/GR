import { useState, useEffect, useRef, useCallback, type FormEvent } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
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
  getCrawlerRunChunks, updateCrawlerRunChunk, indexCrawlerRun, deleteCrawlerRun,
  toggleConfig, getLLMConfig, updateLLMConfig,
  activateApiKey, createApiKey, getApiKeys,
  getEnvConfig, updateEnvConfig,
} from '@/services/adminApi';
import type {
  SystemStats,
  CrawlerStatus,
  LLMConfig,
  ApiKeyProvider,
  ApiKeyRecord,
  CrawlerCollectionResult,
  CrawlerSavedChunkPreview,
  CrawlerChunkDetail,
  EnvConfigItem,
} from '@/types/adminStats';
import {
  Settings, Loader2, PlayCircle, CheckCircle2, XCircle, Save, Key, Cpu, Database,
  Plus, RefreshCw, ChevronDown, ChevronRight, ExternalLink, Trash2,
} from 'lucide-react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
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

const LLM_PROVIDER_OPTIONS: ModelOption[] = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'lm_studio', label: 'LM Studio' },
];

const AUX_PROVIDER_OPTIONS: ModelOption[] = [
  { value: 'gemini', label: 'Gemini' },
  { value: 'lm_studio', label: 'LM Studio' },
  { value: 'ollama', label: 'Ollama' },
];

const DEEPSEEK_MODEL_OPTIONS: ModelOption[] = [
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
];

const GEMINI_MODEL_OPTIONS: ModelOption[] = [
  { value: 'gemini-3.1-flash-lite', label: 'Gemini 3.1 Flash Lite' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'gemini-3.1-flash-lite-lite', label: 'Gemini 2.5 Flash Lite' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
];

const AGENT_MODEL_OPTIONS: ModelOption[] = [
  { value: 'qwen2.5-7b-instruct', label: 'Qwen 2.5 7B Instruct' },
  ...GEMINI_MODEL_OPTIONS,
];

function chatModelOptionsForProvider(provider: string) {
  if (provider === 'deepseek') return DEEPSEEK_MODEL_OPTIONS;
  if (provider === 'gemini') return GEMINI_MODEL_OPTIONS;
  return [...DEEPSEEK_MODEL_OPTIONS, ...AGENT_MODEL_OPTIONS];
}

function auxModelOptionsForProvider(provider: string) {
  if (provider === 'gemini') return GEMINI_MODEL_OPTIONS;
  return AGENT_MODEL_OPTIONS;
}

const API_KEY_PROVIDER_LABELS: Record<ApiKeyProvider, string> = {
  deepseek: 'DeepSeek',
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
    run_id: stringFromUnknown(record.run_id) || undefined,
    chunk_id: stringFromUnknown(record.chunk_id),
    chunk_index: numberFromUnknown(record.chunk_index) || undefined,
    title: stringFromUnknown(record.title),
    source: stringFromUnknown(record.source),
    url: stringFromUnknown(record.url),
    section_label: stringFromUnknown(record.section_label) || undefined,
    content_preview: stringFromUnknown(record.content_preview),
    content_length: numberFromUnknown(record.content_length) || undefined,
    edited: Boolean(record.edited),
    index_status: stringFromUnknown(record.index_status) || undefined,
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
    run_id: stringFromUnknown(record.run_id) || undefined,
    review_run_id: stringFromUnknown(record.review_run_id) || undefined,
    collection,
    pipeline,
    status: stringFromUnknown(record.status) || 'unknown',
    review_status: stringFromUnknown(record.review_status) || undefined,
    can_edit: typeof record.can_edit === 'boolean' ? record.can_edit : undefined,
    can_index: typeof record.can_index === 'boolean' ? record.can_index : undefined,
    new_articles: numberFromUnknown(record.new_articles),
    new_chunks: numberFromUnknown(record.new_chunks),
    indexed: numberFromUnknown(record.indexed),
    expired_removed: numberFromUnknown(record.expired_removed),
    saved_chunks: savedChunks,
    created_at: stringFromUnknown(record.created_at) || undefined,
    updated_at: stringFromUnknown(record.updated_at) || undefined,
    indexed_at: stringFromUnknown(record.indexed_at) || null,
    error_message: stringFromUnknown(record.error_message) || null,
  }, ...nested];
}

function EnvConfigSection() {
  const [configs, setConfigs] = useState<EnvConfigItem[]>([]);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  useEffect(() => {
    getEnvConfig()
      .then((res) => {
        setConfigs(res.configs);
        const values: Record<string, string> = {};
        res.configs.forEach((c) => { values[c.key] = String(c.value); });
        setFormValues(values);
        // Expand all categories by default
        const cats = new Set(res.configs.map((c) => c.category));
        setExpandedCategories(cats);
      })
      .catch(() => toast.error('Không thể tải cấu hình'))
      .finally(() => setLoadingConfig(false));
  }, []);

  const toggleCategory = (cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      for (const c of configs) {
        const raw = formValues[c.key];
        if (raw !== String(c.value)) {
          payload[c.key] = raw;
        }
      }
      if (Object.keys(payload).length === 0) {
        toast.info('Không có thay đổi');
        return;
      }
      await updateEnvConfig(payload);
      toast.success('Cấu hình đã được lưu');
      // Refresh configs
      const res = await getEnvConfig();
      setConfigs(res.configs);
      const values: Record<string, string> = {};
      res.configs.forEach((c) => { values[c.key] = String(c.value); });
      setFormValues(values);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Lưu thất bại';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loadingConfig) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  const grouped = configs.reduce<Record<string, EnvConfigItem[]>>((acc, item) => {
    (acc[item.category] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-muted-foreground" />
          <p className="text-sm font-semibold">Cấu hình nâng cao</p>
        </div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
          Lưu cấu hình
        </Button>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Thay đổi các thông số hệ thống tại đây. Giá trị được áp dụng ngay lập tức và lưu vào database.
      </p>

      <div className="space-y-3">
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category} className="rounded-lg border border-border overflow-hidden">
            <button
              type="button"
              onClick={() => toggleCategory(category)}
              className="flex w-full items-center justify-between px-4 py-2.5 bg-secondary/50 hover:bg-secondary transition-colors text-left"
            >
              <span className="text-xs font-medium text-foreground">{category}</span>
              {expandedCategories.has(category) ? (
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              )}
            </button>
            {expandedCategories.has(category) && (
              <div className="divide-y divide-border">
                {items.map((item) => (
                  <div key={item.key} className="flex items-center gap-4 px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <Label className="text-xs font-medium">{item.label}</Label>
                      <p className="text-[10px] text-muted-foreground truncate">{item.description}</p>
                    </div>
                    <Input
                      className="w-28 h-8 text-xs"
                      type={item.type === 'str' ? 'text' : 'number'}
                      step={item.type === 'float' ? '0.01' : '1'}
                      value={formValues[item.key] ?? ''}
                      onChange={(e) => setFormValues((prev) => ({ ...prev, [item.key]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
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
  const [expandedChunkKey, setExpandedChunkKey] = useState<string | null>(null);
  const [expandedIndexedRuns, setExpandedIndexedRuns] = useState<Set<string>>(new Set());
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);
  const [savingChunkKey, setSavingChunkKey] = useState<string | null>(null);
  const [indexingRunId, setIndexingRunId] = useState<string | null>(null);
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
  const [runChunks, setRunChunks] = useState<Record<string, CrawlerChunkDetail[]>>({});
  const [chunkDrafts, setChunkDrafts] = useState<Record<string, string>>({});
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
          llm_provider: cfg.llm_provider,
          chat_model: cfg.chat_model,
          chat_temperature: String(cfg.chat_temperature),
          chat_max_tokens: String(cfg.chat_max_tokens),
          agent_model: cfg.agent_model,
          agent_synthesis_provider: cfg.agent_synthesis_provider,
          agent_synthesis_model: cfg.agent_synthesis_model,
          reflection_provider: cfg.reflection_provider,
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

  const refreshCrawlerStatus = useCallback(async () => {
    const status = await getCrawlerStatus();
    setCrawlerStatus(status);
    return status;
  }, []);

  // Fetch crawler status
  useEffect(() => {
    refreshCrawlerStatus().catch(() => {});
  }, [refreshCrawlerStatus]);

  // Poll while crawling
  useEffect(() => {
    if (crawlerStatus?.is_running) {
      pollRef.current = setInterval(async () => {
        try {
          const status = await refreshCrawlerStatus();
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
  }, [crawlerStatus?.is_running, refreshCrawlerStatus]);

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

  const handleLLMProviderChange = (llm_provider: string) => {
    setLlmForm((prev) => {
      const next = { ...prev, llm_provider };
      const options = chatModelOptionsForProvider(llm_provider);
      if (!options.some((option) => option.value === next.chat_model)) {
        next.chat_model = options[0]?.value ?? next.chat_model;
      }
      return next;
    });
  };

  const handleAgentProviderChange = (agent_synthesis_provider: string) => {
    setLlmForm((prev) => {
      const next = { ...prev, agent_synthesis_provider };
      const options = auxModelOptionsForProvider(agent_synthesis_provider);
      if (!options.some((option) => option.value === next.agent_synthesis_model)) {
        next.agent_synthesis_model = options[0]?.value ?? next.agent_synthesis_model;
      }
      return next;
    });
  };

  const handleReflectionProviderChange = (reflection_provider: string) => {
    setLlmForm((prev) => {
      const next = { ...prev, reflection_provider };
      const options = auxModelOptionsForProvider(reflection_provider);
      if (!options.some((option) => option.value === next.reflection_model)) {
        next.reflection_model = options[0]?.value ?? next.reflection_model;
      }
      return next;
    });
  };

  const handleLLMSave = async () => {
    setLlmSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (llmForm.llm_provider && llmForm.llm_provider !== llmConfig?.llm_provider)
        body.llm_provider = llmForm.llm_provider;
      if (llmForm.chat_model && llmForm.chat_model !== llmConfig?.chat_model)
        body.chat_model = llmForm.chat_model;
      if (llmForm.agent_model && llmForm.agent_model !== llmConfig?.agent_model)
        body.agent_model = llmForm.agent_model;
      if (
        llmForm.agent_synthesis_provider
        && llmForm.agent_synthesis_provider !== llmConfig?.agent_synthesis_provider
      )
        body.agent_synthesis_provider = llmForm.agent_synthesis_provider;
      if (
        llmForm.agent_synthesis_model
        && llmForm.agent_synthesis_model !== llmConfig?.agent_synthesis_model
      )
        body.agent_synthesis_model = llmForm.agent_synthesis_model;
      if (llmForm.reflection_provider && llmForm.reflection_provider !== llmConfig?.reflection_provider)
        body.reflection_provider = llmForm.reflection_provider;
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
        llm_provider: cfg.llm_provider,
        chat_model: cfg.chat_model,
        chat_temperature: String(cfg.chat_temperature),
        chat_max_tokens: String(cfg.chat_max_tokens),
        agent_model: cfg.agent_model,
        agent_synthesis_provider: cfg.agent_synthesis_provider,
        agent_synthesis_model: cfg.agent_synthesis_model,
        reflection_provider: cfg.reflection_provider,
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
      await refreshCrawlerStatus();
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

  const ensureRunChunks = async (runId: string) => {
    if (runChunks[runId]) return runChunks[runId];

    setLoadingRunId(runId);
    try {
      const response = await getCrawlerRunChunks(runId);
      setRunChunks((prev) => ({ ...prev, [runId]: response.chunks }));
      setChunkDrafts((prev) => {
        const next = { ...prev };
        response.chunks.forEach((chunk) => {
          next[`${runId}:${chunk.chunk_id}`] = chunk.content;
        });
        return next;
      });
      return response.chunks;
    } catch {
      toast.error('KhÃ´ng thá»ƒ táº£i ná»™i dung chunk');
      return [];
    } finally {
      setLoadingRunId(null);
    }
  };

  const handleExpandChunk = async (runId: string, chunkId: string) => {
    const key = `${runId}:${chunkId}`;
    if (expandedChunkKey === key) {
      setExpandedChunkKey(null);
      return;
    }
    await ensureRunChunks(runId);
    setExpandedChunkKey(key);
  };

  const handleSaveCrawlerChunk = async (runId: string, chunk: CrawlerChunkDetail) => {
    const key = `${runId}:${chunk.chunk_id}`;
    const content = chunkDrafts[key] ?? chunk.content;
    setSavingChunkKey(key);
    try {
      const updated = await updateCrawlerRunChunk(runId, chunk.chunk_id, content);
      setRunChunks((prev) => ({
        ...prev,
        [runId]: (prev[runId] || []).map((item) => (
          item.chunk_id === updated.chunk_id ? updated : item
        )),
      }));
      setChunkDrafts((prev) => ({ ...prev, [key]: updated.content }));
      toast.success('ÄÃ£ lÆ°u chunk');
      await refreshCrawlerStatus();
    } catch {
      toast.error('KhÃ´ng thá»ƒ lÆ°u chunk');
    } finally {
      setSavingChunkKey(null);
    }
  };

  const handleIndexCrawlerRun = async (runId: string) => {
    setIndexingRunId(runId);
    try {
      await indexCrawlerRun(runId);
      toast.success('ÄÃ£ báº¯t Ä‘áº§u index run');
      await refreshCrawlerStatus();
    } catch {
      toast.error('KhÃ´ng thá»ƒ index run');
    } finally {
      setIndexingRunId(null);
    }
  };

  const handleDeleteCrawlerRun = async (runId: string) => {
    if (!confirm('Xác nhận xóa crawl run này? Dữ liệu sẽ bị xóa khỏi JSON và MongoDB.')) return;
    setDeletingRunId(runId);
    try {
      const res = await deleteCrawlerRun(runId);
      toast.success(`Đã xóa: ${res.deleted_articles} bài, ${res.deleted_chunks} chunks`);
      await refreshCrawlerStatus();
    } catch {
      toast.error('Không thể xóa crawl run');
    } finally {
      setDeletingRunId(null);
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
  const crawlCollectionResults = crawlerStatus?.runs?.length
    ? crawlerStatus.runs
    : collectCrawlerCollectionResults(crawlerStatus?.last_result);
  const lastCrawlerStatus = crawlerStatus?.last_result?.status;
  const lastCrawlerOk = lastCrawlerStatus === 'success' || lastCrawlerStatus === 'pending_review';

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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <ModelSelectField
                  id="llm-provider"
                  label="Chat Provider"
                  options={LLM_PROVIDER_OPTIONS}
                  value={llmForm.llm_provider}
                  onValueChange={handleLLMProviderChange}
                />
                <ModelSelectField
                  id="chat-model"
                  label="Chat Model"
                  options={chatModelOptionsForProvider(llmForm.llm_provider)}
                  value={llmForm.chat_model}
                  onValueChange={(chat_model) => setLlmForm((p) => ({ ...p, chat_model }))}
                />
                <ModelSelectField
                  id="agent-provider"
                  label="Agent Provider"
                  options={AUX_PROVIDER_OPTIONS}
                  value={llmForm.agent_synthesis_provider}
                  onValueChange={handleAgentProviderChange}
                />
                <ModelSelectField
                  id="agent-model"
                  label="Agent Model"
                  options={auxModelOptionsForProvider(llmForm.agent_synthesis_provider)}
                  value={llmForm.agent_synthesis_model}
                  onValueChange={(agent_synthesis_model) => setLlmForm((p) => ({ ...p, agent_synthesis_model }))}
                />
                <ModelSelectField
                  id="reflection-provider"
                  label="Reflection Provider"
                  options={AUX_PROVIDER_OPTIONS}
                  value={llmForm.reflection_provider}
                  onValueChange={handleReflectionProviderChange}
                />
                <ModelSelectField
                  id="reflection-model"
                  label="Reflection Model"
                  options={auxModelOptionsForProvider(llmForm.reflection_provider)}
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
                  <SelectItem value="deepseek">DeepSeek</SelectItem>
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

      {/* Documents charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {docStatusData.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <p className="text-sm font-semibold mb-3">Tài liệu theo trạng thái</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={docStatusData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={40} />
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
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={docCollData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={false}
                >
                  {docCollData.map((_, idx) => (
                    <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [value, 'Số lượng']} />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: '11px', lineHeight: '20px' }}
                />
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
            lastCrawlerOk
              ? 'bg-emerald-50 dark:bg-emerald-950'
              : 'bg-red-50 dark:bg-red-950'
          }`}>
            {lastCrawlerOk ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            <div className="text-sm">
              <span className="font-medium">
                {lastCrawlerStatus === 'pending_review' ? 'Chờ duyệt' : lastCrawlerOk ? 'Thành công' : 'Lỗi'}
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

            {crawlCollectionResults.map((result) => {
              const runId = result.review_run_id || result.run_id || '';
              const status = result.review_status || result.status;
              const canIndex = Boolean(runId && result.can_index && !crawlerStatus?.is_running);
              const isIndexing = status === 'indexing' || indexingRunId === runId;
              const canDelete = Boolean(runId && result.can_delete);
              const isDeleting = deletingRunId === runId;
              const isIndexed = status === 'indexed';
              const sectionKey = runId || `${result.collection}-${result.pipeline}-${status}`;
              const isRunExpanded = expandedIndexedRuns.has(sectionKey);

              return (
              <section
                key={sectionKey}
                className="rounded-lg border border-border bg-background p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    {isIndexed && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 mt-0.5"
                        onClick={() => setExpandedIndexedRuns((prev) => {
                          const next = new Set(prev);
                          if (next.has(sectionKey)) next.delete(sectionKey);
                          else next.add(sectionKey);
                          return next;
                        })}
                      >
                        {isRunExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </Button>
                    )}
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
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={status === 'indexed' ? 'default' : status === 'index_failed' ? 'destructive' : 'secondary'}>
                      {status}
                    </Badge>
                    {result.expired_removed > 0 && (
                    <Badge variant="secondary">{result.expired_removed} chunks hết hạn đã xóa</Badge>
                    )}
                    {runId && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-2"
                        disabled={!canIndex || isIndexing}
                        onClick={() => handleIndexCrawlerRun(runId)}
                      >
                        {isIndexing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
                        Index
                      </Button>
                    )}
                    {runId && canDelete && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-2 text-destructive hover:bg-destructive/10"
                        disabled={isDeleting}
                        onClick={() => handleDeleteCrawlerRun(runId)}
                      >
                        {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        Xóa
                      </Button>
                    )}
                  </div>
                </div>

                {(!isIndexed || isRunExpanded) && (
                  <>
                {result.saved_chunks.length > 0 ? (
                  <div className="mt-3 divide-y divide-border overflow-hidden rounded-lg border border-border">
                    {result.saved_chunks.map((chunk) => {
                      const chunkKey = `${runId}:${chunk.chunk_id}`;
                      const isExpanded = expandedChunkKey === chunkKey;
                      const fullChunk = runChunks[runId]?.find((item) => item.chunk_id === chunk.chunk_id);
                      const draft = chunkDrafts[chunkKey] ?? fullChunk?.content ?? '';

                      return (
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
                            {runId && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-8 w-8 p-0"
                                disabled={loadingRunId === runId}
                                onClick={() => handleExpandChunk(runId, chunk.chunk_id)}
                                title="Xem/sá»­a chunk"
                              >
                                {loadingRunId === runId ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : isExpanded ? (
                                  <ChevronDown className="h-3.5 w-3.5" />
                                ) : (
                                  <ChevronRight className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            )}
                            {chunk.source && <Badge variant="outline">{chunk.source}</Badge>}
                            {chunk.section_label && <Badge variant="secondary">Mục {chunk.section_label}</Badge>}
                          </div>
                        </div>
                        {chunk.url && (
                          <a
                            className="mt-2 inline-flex max-w-full items-center gap-1 truncate text-xs text-primary hover:underline"
                            href={chunk.url}
                            title={chunk.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <span className="truncate">{chunk.url}</span>
                            <ExternalLink className="h-3 w-3 shrink-0" />
                          </a>
                        )}
                        {chunk.content_preview && (
                          <p className="mt-2 break-words text-xs leading-5 text-muted-foreground">
                            {chunk.content_preview}
                          </p>
                        )}
                        {isExpanded && (
                          <div className="mt-3 space-y-2 rounded-lg border border-border bg-background p-3">
                            {fullChunk ? (
                              <>
                                <Textarea
                                  className="min-h-[180px] resize-y text-xs leading-5"
                                  value={draft}
                                  readOnly={!result.can_edit}
                                  onChange={(event) => setChunkDrafts((prev) => ({
                                    ...prev,
                                    [chunkKey]: event.target.value,
                                  }))}
                                />
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    {fullChunk.edited && <Badge variant="secondary">edited</Badge>}
                                    {fullChunk.content_length !== undefined && (
                                      <span className="text-xs text-muted-foreground">
                                        {fullChunk.content_length} chars
                                      </span>
                                    )}
                                  </div>
                                  {result.can_edit && (
                                    <Button
                                      size="sm"
                                      className="gap-2"
                                      disabled={savingChunkKey === chunkKey}
                                      onClick={() => handleSaveCrawlerChunk(runId, fullChunk)}
                                    >
                                      {savingChunkKey === chunkKey ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                      ) : (
                                        <Save className="h-3.5 w-3.5" />
                                      )}
                                      Save
                                    </Button>
                                  )}
                                </div>
                              </>
                            ) : (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Loading chunk...
                              </div>
                            )}
                          </div>
                        )}
                      </article>
                      );
                    })}
                  </div>
                ) : (
                  <p className="mt-3 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                    Lần crawl này không index chunk mới cho collection này.
                  </p>
                )}
                  </>
                )}
              </section>
              );
            })}
          </div>
        )}
      </div>

      {/* Advanced Config Table */}
      <EnvConfigSection />
    </div>
  );
}
