import axios from 'axios';
import { getStoredToken } from '@/services/authStorage';
import { installAuthInterceptors } from '@/services/authSession';
import type {
  DocumentDetail,
  DocumentListResponse,
  ChunkPreview,
  ChunksResponse,
  MarkdownContent,
  CleanedContent,
  ConverterOption,
  ChunkerOption,
  ChunkStrategySummary,
} from '@/types/admin';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const adminClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
  withCredentials: true,
});

installAuthInterceptors(adminClient);

function authHeaders() {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ──────────────────── Documents CRUD ────────────────────

export async function uploadDocuments(
  files: File[],
  collection: string,
  chunkingStrategy?: string,
  metadataOverrides?: Record<string, unknown>,
  onProgress?: (pct: number) => void,
): Promise<DocumentDetail[]> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  form.append('collection', collection);
  if (chunkingStrategy) form.append('chunking_strategy', chunkingStrategy);
  if (metadataOverrides) form.append('metadata_overrides', JSON.stringify(metadataOverrides));

  const { data } = await adminClient.post<DocumentDetail[]>('/admin/documents', form, {
    headers: { ...authHeaders(), 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return data;
}

export async function listDocuments(
  page = 1,
  limit = 20,
  status?: string,
  collection?: string,
): Promise<DocumentListResponse> {
  const params: Record<string, string | number> = { page, limit };
  if (status) params.status = status;
  if (collection) params.collection = collection;
  const { data } = await adminClient.get<DocumentListResponse>('/admin/documents', {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function getDocument(id: string): Promise<DocumentDetail> {
  const { data } = await adminClient.get<DocumentDetail>(`/admin/documents/${id}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await adminClient.delete(`/admin/documents/${id}`, { headers: authHeaders() });
}

// ──────────────────── Pipeline steps ────────────────────

export async function triggerConvert(id: string, converter?: string): Promise<void> {
  const params = converter ? { converter } : {};
  await adminClient.post(`/admin/documents/${id}/convert`, null, {
    headers: authHeaders(),
    params,
  });
}

export async function triggerClean(id: string): Promise<void> {
  await adminClient.post(`/admin/documents/${id}/clean`, null, { headers: authHeaders() });
}

export async function triggerChunk(id: string, strategy?: string): Promise<void> {
  const params = strategy ? { strategy } : {};
  await adminClient.post(`/admin/documents/${id}/chunk`, null, { headers: authHeaders(), params });
}

export async function triggerIndex(id: string): Promise<void> {
  await adminClient.post(`/admin/documents/${id}/index`, null, { headers: authHeaders() });
}

export async function triggerFullPipeline(id: string): Promise<void> {
  await adminClient.post(`/admin/documents/${id}/pipeline`, null, { headers: authHeaders() });
}

export async function rollbackDocument(id: string): Promise<void> {
  await adminClient.post(`/admin/documents/${id}/rollback`, null, { headers: authHeaders() });
}

// ──────────────────── Review endpoints ──────────────────

export async function getMarkdown(id: string): Promise<MarkdownContent> {
  const { data } = await adminClient.get<MarkdownContent>(`/admin/documents/${id}/markdown`, {
    headers: authHeaders(),
  });
  return data;
}

export async function updateMarkdown(id: string, content: string): Promise<void> {
  await adminClient.put(`/admin/documents/${id}/markdown`, { content }, { headers: authHeaders() });
}

export async function getCleanedContent(id: string): Promise<CleanedContent> {
  const { data } = await adminClient.get<CleanedContent>(`/admin/documents/${id}/cleaned`, {
    headers: authHeaders(),
  });
  return data;
}

export async function updateCleaned(id: string, content: string): Promise<void> {
  await adminClient.put(`/admin/documents/${id}/cleaned`, { content }, { headers: authHeaders() });
}

export async function getChunks(
  id: string,
  page = 1,
  limit = 20,
  strategy?: string,
): Promise<ChunksResponse> {
  const params: Record<string, string | number> = { page, limit };
  if (strategy) params.strategy = strategy;
  const { data } = await adminClient.get<ChunksResponse>(`/admin/documents/${id}/chunks`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function approveChunks(id: string): Promise<void> {
  await adminClient.put(`/admin/documents/${id}/chunks`, null, { headers: authHeaders() });
}

export async function updateDocumentChunk(
  id: string,
  chunkId: string,
  content: string,
): Promise<ChunkPreview> {
  const { data } = await adminClient.patch<ChunkPreview>(
    `/admin/documents/${id}/chunks/${chunkId}`,
    { content },
    { headers: authHeaders() },
  );
  return data;
}

export async function deleteDocumentChunk(
  id: string,
  chunkId: string,
): Promise<{ deleted_chunk_id: string; remaining_chunks: number }> {
  const { data } = await adminClient.delete<{
    deleted_chunk_id: string;
    remaining_chunks: number;
  }>(
    `/admin/documents/${id}/chunks/${chunkId}`,
    { headers: authHeaders() },
  );
  return data;
}

// ──────────────────── Converter / Chunker listing ──────────────────

export async function listConverters(): Promise<ConverterOption[]> {
  const { data } = await adminClient.get<{ converters: ConverterOption[] }>('/admin/converters', {
    headers: authHeaders(),
  });
  return data.converters;
}

export async function listChunkers(collection?: string): Promise<ChunkerOption[]> {
  const params = collection ? { collection } : {};
  const { data } = await adminClient.get<{ chunkers: ChunkerOption[] }>('/admin/chunkers', {
    headers: authHeaders(),
    params,
  });
  return data.chunkers;
}

// ──────────────────── Chunk comparison ──────────────────

export async function listChunkStrategies(id: string): Promise<ChunkStrategySummary[]> {
  const { data } = await adminClient.get<{ strategies: ChunkStrategySummary[] }>(
    `/admin/documents/${id}/chunk-strategies`,
    { headers: authHeaders() },
  );
  return data.strategies;
}

export async function selectChunkStrategy(
  id: string,
  strategy: string,
): Promise<{ kept_chunks: number; deleted_chunks: number }> {
  const { data } = await adminClient.post(
    `/admin/documents/${id}/chunks/select`,
    null,
    { headers: authHeaders(), params: { strategy } },
  );
  return data;
}

// ──────────────────── Polling helper ────────────────────

/**
 * Poll document status until it matches one of `targetStatuses` or hits max attempts.
 */
export async function pollDocumentStatus(
  id: string,
  targetStatuses: string[],
  interval = 5_000,
  maxAttempts = 60,
): Promise<DocumentDetail> {
  for (let i = 0; i < maxAttempts; i++) {
    const doc = await getDocument(id);
    if (targetStatuses.includes(doc.status) || doc.status === 'failed') {
      return doc;
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  // Final attempt
  return getDocument(id);
}

// ──────────────────── Admin Stats API ────────────────────

import type {
  OverviewStats,
  AdminUsersResponse,
  UserBreakdown,
  QueryAnalytics,
  AgentAnalytics,
  FeedbackTopics,
  SystemStats,
  UserStatusResponse,
  CrawlerTriggerResponse,
  CrawlerStatus,
  CrawlerRunChunksResponse,
  CrawlerChunkDetail,
  CrawlerIndexResponse,
  ConfigToggleResponse,
  LLMConfig,
  LLMConfigUpdateBody,
  LLMConfigUpdateResponse,
  ApiKeyListResponse,
  ApiKeyMutationResponse,
  CreateApiKeyBody,
  EnvConfigResponse,
  EnvConfigUpdateResponse,
} from '@/types/adminStats';

export async function getOverviewStats(): Promise<OverviewStats> {
  const { data } = await adminClient.get<OverviewStats>('/admin/stats/overview', {
    headers: authHeaders(),
  });
  return data;
}

export async function getAdminUsers(params: {
  page?: number;
  limit?: number;
  search?: string;
  sort_by?: string;
  order?: string;
  days?: number;
} = {}): Promise<AdminUsersResponse> {
  const { data } = await adminClient.get<AdminUsersResponse>('/admin/stats/users', {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function getUserBreakdown(days = 30): Promise<UserBreakdown> {
  const { data } = await adminClient.get<UserBreakdown>('/admin/stats/users/breakdown', {
    headers: authHeaders(),
    params: { days },
  });
  return data;
}

export async function getQueryAnalytics(days = 30, top_questions_limit = 15): Promise<QueryAnalytics> {
  const { data } = await adminClient.get<QueryAnalytics>('/admin/stats/queries', {
    headers: authHeaders(),
    params: { days, top_questions_limit },
  });
  return data;
}

export async function getAgentAnalytics(days = 30): Promise<AgentAnalytics> {
  const { data } = await adminClient.get<AgentAnalytics>('/admin/stats/agent', {
    headers: authHeaders(),
    params: { days },
  });
  return data;
}

export async function getFeedbackTopics(days = 30, limit = 20): Promise<FeedbackTopics> {
  const { data } = await adminClient.get<FeedbackTopics>('/admin/stats/feedback/topics', {
    headers: authHeaders(),
    params: { days, limit },
  });
  return data;
}

export async function getSystemStats(): Promise<SystemStats> {
  const { data } = await adminClient.get<SystemStats>('/admin/stats/system', {
    headers: authHeaders(),
  });
  return data;
}

export async function toggleUserStatus(userId: string, isActive: boolean): Promise<UserStatusResponse> {
  const { data } = await adminClient.patch<UserStatusResponse>(
    `/admin/users/${userId}/status`,
    { is_active: isActive },
    { headers: authHeaders() },
  );
  return data;
}

export async function triggerCrawler(pipeline: string = 'all'): Promise<CrawlerTriggerResponse> {
  const { data } = await adminClient.post<CrawlerTriggerResponse>(
    '/admin/crawler/trigger',
    null,
    { headers: authHeaders(), params: { pipeline_target: pipeline } },
  );
  return data;
}

export async function getCrawlerStatus(): Promise<CrawlerStatus> {
  const { data } = await adminClient.get<CrawlerStatus>('/admin/crawler/status', {
    headers: authHeaders(),
  });
  return data;
}

export async function getCrawlerRunChunks(runId: string): Promise<CrawlerRunChunksResponse> {
  const { data } = await adminClient.get<CrawlerRunChunksResponse>(
    `/admin/crawler/runs/${runId}/chunks`,
    { headers: authHeaders() },
  );
  return data;
}

export async function updateCrawlerRunChunk(
  runId: string,
  chunkId: string,
  content: string,
): Promise<CrawlerChunkDetail> {
  const { data } = await adminClient.patch<CrawlerChunkDetail>(
    `/admin/crawler/runs/${runId}/chunks/${chunkId}`,
    { content },
    { headers: authHeaders() },
  );
  return data;
}

export async function indexCrawlerRun(runId: string): Promise<CrawlerIndexResponse> {
  const { data } = await adminClient.post<CrawlerIndexResponse>(
    `/admin/crawler/runs/${runId}/index`,
    null,
    { headers: authHeaders() },
  );
  return data;
}

// ──────────────────── Config toggle ────────────────────

export async function toggleConfig(key: string, value: boolean): Promise<ConfigToggleResponse> {
  const { data } = await adminClient.patch<ConfigToggleResponse>(
    '/admin/config',
    { key, value },
    { headers: authHeaders() },
  );
  return data;
}

// ──────────────────── LLM config ────────────────────

export async function getLLMConfig(): Promise<LLMConfig> {
  const { data } = await adminClient.get<LLMConfig>('/admin/config/llm', {
    headers: authHeaders(),
  });
  return data;
}

export async function updateLLMConfig(body: LLMConfigUpdateBody): Promise<LLMConfigUpdateResponse> {
  const { data } = await adminClient.put<LLMConfigUpdateResponse>(
    '/admin/config/llm',
    body,
    { headers: authHeaders() },
  );
  return data;
}

export async function getApiKeys(): Promise<ApiKeyListResponse> {
  const { data } = await adminClient.get<ApiKeyListResponse>('/admin/config/api-keys', {
    headers: authHeaders(),
  });
  return data;
}

export async function createApiKey(body: CreateApiKeyBody): Promise<ApiKeyMutationResponse> {
  const { data } = await adminClient.post<ApiKeyMutationResponse>(
    '/admin/config/api-keys',
    body,
    { headers: authHeaders() },
  );
  return data;
}

export async function activateApiKey(id: string): Promise<ApiKeyMutationResponse> {
  const { data } = await adminClient.post<ApiKeyMutationResponse>(
    `/admin/config/api-keys/${id}/activate`,
    null,
    { headers: authHeaders() },
  );
  return data;
}

// ──────────────────── Env Config API ────────────────────

export async function getEnvConfig(): Promise<EnvConfigResponse> {
  const { data } = await adminClient.get<EnvConfigResponse>('/admin/config/env', {
    headers: authHeaders(),
  });
  return data;
}

export async function updateEnvConfig(configs: Record<string, unknown>): Promise<EnvConfigUpdateResponse> {
  const { data } = await adminClient.put<EnvConfigUpdateResponse>(
    '/admin/config/env',
    { configs },
    { headers: authHeaders() },
  );
  return data;
}
