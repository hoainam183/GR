import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import EmptyState from './EmptyState';
import { useAdminFetch } from '@/hooks/useAdminFetch';
import {
  getSystemStats, triggerCrawler, getCrawlerStatus,
  toggleConfig, getLLMConfig, updateLLMConfig,
} from '@/services/adminApi';
import type { SystemStats, CrawlerStatus, LLMConfig } from '@/types/adminStats';
import { Settings, Loader2, PlayCircle, CheckCircle2, XCircle, Save, Key, Cpu } from 'lucide-react';
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
          google_api_key: '',
          tavily_api_key: '',
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
      if (llmForm.google_api_key) body.google_api_key = llmForm.google_api_key;
      if (llmForm.tavily_api_key) body.tavily_api_key = llmForm.tavily_api_key;
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
        google_api_key: '',
        tavily_api_key: '',
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
              <div className="flex items-center gap-2">
                <Key className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">API Keys</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="google-key" className="text-xs">Google API Key</Label>
                  <Input
                    id="google-key"
                    type="password"
                    placeholder={llmConfig?.google_api_key || 'Nhập key mới...'}
                    value={llmForm.google_api_key}
                    onChange={(e) => setLlmForm((p) => ({ ...p, google_api_key: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="tavily-key" className="text-xs">Tavily API Key</Label>
                  <Input
                    id="tavily-key"
                    type="password"
                    placeholder={llmConfig?.tavily_api_key || 'Nhập key mới...'}
                    value={llmForm.tavily_api_key}
                    onChange={(e) => setLlmForm((p) => ({ ...p, tavily_api_key: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            {/* Model settings */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Models</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="chat-model" className="text-xs">Chat Model</Label>
                  <Input
                    id="chat-model"
                    value={llmForm.chat_model}
                    onChange={(e) => setLlmForm((p) => ({ ...p, chat_model: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="agent-model" className="text-xs">Agent Model</Label>
                  <Input
                    id="agent-model"
                    value={llmForm.agent_model}
                    onChange={(e) => setLlmForm((p) => ({ ...p, agent_model: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reflection-model" className="text-xs">Reflection Model</Label>
                  <Input
                    id="reflection-model"
                    value={llmForm.reflection_model}
                    onChange={(e) => setLlmForm((p) => ({ ...p, reflection_model: e.target.value }))}
                  />
                </div>
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
      </div>
    </div>
  );
}
