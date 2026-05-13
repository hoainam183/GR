import axios from 'axios';
import type {
  DocumentDetail,
  DocumentListResponse,
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
});

function authHeaders() {
  const token = localStorage.getItem('token');
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
