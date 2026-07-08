import axios from 'axios';
import type {
  ChatRequest,
  ChatResponse,
  ChatV3Response,
  RetrievedDocument,
  UserContext,
} from '@/types/chat';
import { getStoredToken, getStoredUser } from '@/services/authStorage';
import { authFetch, installAuthInterceptors } from '@/services/authSession';

type StoredUserShape = UserContext & {
  email?: string | null;
  username?: string | null;
};

export interface ResolvedChatIdentity {
  userContext?: UserContext;
  userId?: string;
  source: 'explicit' | 'localStorage' | 'mixed' | 'none';
}

export interface ChatStreamHandlers {
  onSessionId?: (sessionId: string) => void;
  onToken?: (delta: string) => void;
  onStatus?: (status: { stage?: string; message: string }) => void;
  onMetadata?: (meta: Partial<ChatV3Response>) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
  signal?: AbortSignal;
}

export interface RetrievalSearchResponse {
  query: string;
  results: RetrievedDocument[];
  total_found: number;
  applied_filters: Array<{
    collection: string;
    applied: boolean;
    matched_ids: number;
    filter_desc?: string;
  }>;
  collection_results: Array<{
    collection: string;
    vector_count: number;
    keyword_count: number;
  }>;
  fusion_weights: Record<string, unknown>;
  latency_ms: number;
}

export interface EvalRunSummary {
  run_id: string;
  eval_suite: 'historical_email' | 'current_policy';
  status: string;
  started_at?: string;
  finished_at?: string;
  trigger?: string;
  summary: Record<string, unknown>;
  artifacts?: Record<string, string>;
  errors?: string[];
}

export interface EvalCaseFailure {
  case_id: string;
  eval_suite: string;
  question: string;
  fail_reasons?: string[];
  metrics?: Record<string, number>;
  judge_scores?: Record<string, number>;
  error?: string;
}

export interface EvalBreakdownRow {
  key: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  pass_rate: number;
}

export interface EvalDashboardResponse {
  status: string;
  source: 'mongodb' | 'artifacts';
  latest?: EvalRunSummary | null;
  runs: EvalRunSummary[];
  trends: Array<{
    run_id: string;
    eval_suite: string;
    finished_at?: string;
    status: string;
    summary: Record<string, unknown>;
  }>;
  failing_cases: EvalCaseFailure[];
  breakdown?: {
    by_query_class?: EvalBreakdownRow[];
    by_collection?: EvalBreakdownRow[];
  };
  stale_source_violations?: EvalCaseFailure[];
}

export interface ChatStreamResult {
  answer: string;
  sessionId?: string;
  metadata?: Partial<ChatV3Response>;
}

// Backend API endpoint
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Configure axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000 * 2, // 60*2 seconds timeout for RAG processing
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

installAuthInterceptors(apiClient);

const authHeaders = (): Record<string, string> => {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const cleanText = (value: unknown): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const cleaned = value.trim();
  return cleaned.length > 0 ? cleaned : undefined;
};

const asRecord = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;

const sanitizeUserContext = (
  context?: UserContext,
): UserContext | undefined => {
  if (!context) {
    return undefined;
  }

  const cleaned: UserContext = {};
  const studentId = cleanText(context.student_id);
  const cohort = cleanText(context.cohort);
  const major = cleanText(context.major);
  const majorCode = cleanText(context.major_code);
  const fullName = cleanText(context.full_name);

  if (studentId) cleaned.student_id = studentId;
  if (cohort) cleaned.cohort = cohort;
  if (major) cleaned.major = major;
  if (majorCode) cleaned.major_code = majorCode;
  if (fullName) cleaned.full_name = fullName;

  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
};

const readStoredUser = (): StoredUserShape | undefined => {
  const parsed = getStoredUser<StoredUserShape>();
  if (!parsed || typeof parsed !== 'object') {
    return undefined;
  }
  return parsed;
};

const storedUserToContext = (
  stored?: StoredUserShape,
): UserContext | undefined => {
  if (!stored) {
    return undefined;
  }
  return sanitizeUserContext({
    student_id: stored.student_id,
    cohort: stored.cohort,
    major: stored.major,
    major_code: stored.major_code,
    full_name: stored.full_name,
  });
};

export const resolveChatIdentity = (
  userContext?: UserContext,
  userId?: string,
): ResolvedChatIdentity => {
  const explicitContext = sanitizeUserContext(userContext);
  const explicitUserId = cleanText(userId);

  const storedUser = readStoredUser();
  const fallbackContext = storedUserToContext(storedUser);
  const fallbackUserId =
    cleanText(storedUser?.email) ||
    cleanText(storedUser?.username) ||
    cleanText(storedUser?.student_id);

  const resolvedContext = explicitContext || fallbackContext;
  const resolvedUserId = explicitUserId || fallbackUserId;

  const hasExplicit = Boolean(explicitContext || explicitUserId);
  const hasFallback = Boolean(fallbackContext || fallbackUserId);

  let source: ResolvedChatIdentity['source'] = 'none';
  if (hasExplicit && hasFallback && (!explicitContext || !explicitUserId)) {
    source = 'mixed';
  } else if (hasExplicit) {
    source = 'explicit';
  } else if (hasFallback) {
    source = 'localStorage';
  }

  return {
    userContext: resolvedContext,
    userId: resolvedUserId,
    source,
  };
};

const mapSourceToRetrieved = (
  source: Record<string, unknown>,
  rank: number,
): RetrievedDocument => {
  const metadata =
    source.metadata && typeof source.metadata === 'object'
      ? (source.metadata as Record<string, unknown>)
      : {};
  const content =
    typeof source.content === 'string'
      ? source.content
      : typeof source.text === 'string'
      ? source.text
      : typeof source.chunk_text === 'string'
      ? source.chunk_text
      : '';
  const rerankScore =
    typeof source.rerank_score === 'number' ? source.rerank_score : undefined;
  const score =
    rerankScore ??
    (typeof source.score === 'number'
      ? source.score
      : typeof source.hybrid_score === 'number'
      ? source.hybrid_score
      : 0);

  return {
    rank: typeof source.rank === 'number' ? source.rank : rank,
    content,
    score,
    hybrid_score:
      typeof source.hybrid_score === 'number'
        ? source.hybrid_score
        : typeof source.score === 'number'
        ? source.score
        : undefined,
    rerank_score: rerankScore,
    vector_score:
      typeof source.vector_score === 'number' ? source.vector_score : undefined,
    keyword_score:
      typeof source.keyword_score === 'number' ? source.keyword_score : undefined,
    collection:
      typeof source.collection === 'string'
        ? source.collection
        : typeof metadata.collection === 'string'
        ? metadata.collection
        : undefined,
    metadata,
  };
};

const usefulSourceMetadataKeys = [
  'title',
  'heading',
  'doc_title',
  'document_title',
  'article_title',
  'source',
  'file_name',
  'filename',
  'url',
  'source_url',
  'link',
  'href',
  'file_url',
  'pdf_url',
  'page',
  'page_number',
  'pages',
];

const isDisplayableRetrievedDocument = (doc: RetrievedDocument): boolean =>
  Boolean(doc.content.trim()) ||
  usefulSourceMetadataKeys.some((key) => {
    const value = doc.metadata[key];
    return typeof value === 'string' && value.trim();
  });

const normalizeV3Response = (
  payload: Record<string, unknown>,
  fallbackSessionId?: string,
): ChatV3Response => {
  const retrievedDocs = Array.isArray(payload.retrieved_documents)
    ? (payload.retrieved_documents as Record<string, unknown>[]).map((source, index) =>
        mapSourceToRetrieved(source, index + 1),
      ).filter(isDisplayableRetrievedDocument)
    : Array.isArray(payload.sources)
    ? (payload.sources as Record<string, unknown>[]).map((source, index) =>
        mapSourceToRetrieved(source, index + 1),
      ).filter(isDisplayableRetrievedDocument)
    : [];

  const toolsFromTrace =
    payload.agent_trace &&
    typeof payload.agent_trace === 'object' &&
    Array.isArray((payload.agent_trace as Record<string, unknown>).tool_calls)
      ? ((payload.agent_trace as Record<string, unknown>).tool_calls as ChatV3Response['tool_calls'])
      : [];

  const toolsUsedFromTrace =
    payload.agent_trace &&
    typeof payload.agent_trace === 'object' &&
    Array.isArray((payload.agent_trace as Record<string, unknown>).tool_names_sequence)
      ? ((payload.agent_trace as Record<string, unknown>).tool_names_sequence as string[])
      : [];

  return {
    question: typeof payload.question === 'string' ? payload.question : '',
    answer: typeof payload.answer === 'string' ? payload.answer : '',
    retrieved_documents: retrievedDocs,
    num_documents: retrievedDocs.length,
    model_name:
      typeof payload.model_name === 'string'
        ? payload.model_name
        : typeof payload.mode === 'string'
        ? payload.mode
        : 'unknown',
    intent:
      typeof payload.intent === 'string'
        ? payload.intent
        : typeof payload.route === 'string'
        ? payload.route
        : 'rag',
    target_collections: Array.isArray(payload.target_collections)
      ? (payload.target_collections as string[])
      : undefined,
    collection_scores: Array.isArray(payload.collection_scores)
      ? (payload.collection_scores as ChatResponse['collection_scores'])
      : undefined,
    reflected_question:
      typeof payload.reflected_question === 'string'
        ? payload.reflected_question
        : undefined,
    timings_ms:
      payload.timings_ms && typeof payload.timings_ms === 'object'
        ? (payload.timings_ms as Record<string, number>)
        : undefined,
    session_id:
      cleanText(payload.session_id) || fallbackSessionId || '',
    turn_id:
      typeof payload.turn_id === 'number' ? payload.turn_id : undefined,
    routing_probabilities:
      payload.routing_probabilities && typeof payload.routing_probabilities === 'object'
        ? (payload.routing_probabilities as Record<string, number>)
        : undefined,
    reflection_prompt:
      typeof payload.reflection_prompt === 'string'
        ? payload.reflection_prompt
        : undefined,
    llm_prompt:
      typeof payload.llm_prompt === 'string' ? payload.llm_prompt : undefined,
    applied_filters: Array.isArray(payload.applied_filters)
      ? (payload.applied_filters as ChatResponse['applied_filters'])
      : undefined,
    collection_results: Array.isArray(payload.collection_results)
      ? (payload.collection_results as ChatResponse['collection_results'])
      : undefined,
    context_trace: asRecord(payload.context_trace),
    rerank_trace: asRecord(payload.rerank_trace),
    answer_quality_gate: asRecord(payload.answer_quality_gate),
    fusion_weights: asRecord(payload.fusion_weights),
    answer_status:
      typeof payload.answer_status === 'string'
        ? payload.answer_status
        : undefined,
    mode: typeof payload.mode === 'string' ? payload.mode : undefined,
    route: typeof payload.route === 'string' ? payload.route : undefined,
    tools_used: Array.isArray(payload.tools_used)
      ? (payload.tools_used as string[])
      : toolsUsedFromTrace,
    tool_calls: Array.isArray(payload.tool_calls)
      ? (payload.tool_calls as ChatV3Response['tool_calls'])
      : toolsFromTrace,
    iterations:
      typeof payload.iterations === 'number' ? payload.iterations : undefined,
    error: typeof payload.error === 'string' ? payload.error : undefined,
    agent_error:
      typeof payload.agent_error === 'string'
        ? payload.agent_error
        : undefined,
    agent_trace:
      payload.agent_trace && typeof payload.agent_trace === 'object'
        ? (payload.agent_trace as ChatV3Response['agent_trace'])
        : undefined,
  };
};

export const sendMessage = async (
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 7,
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
): Promise<ChatResponse> => {
  // Delegate to v3 endpoint with 'auto' mode to use complexity routing
  const v3Response = await sendMessageV3(
    question,
    history,
    topK,
    'auto',
    sessionId,
    userContext,
    userId
  );
  return v3Response as unknown as ChatResponse;
};

const parseSseDataLines = (rawEvent: string): string => {
  const dataLines = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) =>
      line.startsWith('data: ') ? line.slice(6) : line.slice(5),
    );
  return dataLines.join('\n');
};

export const sendMessageStream = async (
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 7,
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
  handlers: ChatStreamHandlers = {},
): Promise<ChatStreamResult> => {
  const identity = resolveChatIdentity(userContext, userId);
  const streamUrl = `${API_BASE_URL.replace(/\/+$/, '')}/chat/stream`;

  const response = await authFetch(streamUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      top_k: topK,
      history,
      session_id: sessionId,
      user_context: identity.userContext,
      user_id: identity.userId,
    } as ChatRequest),
    signal: handlers.signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Failed to start streaming response.');
  }

  if (!response.body) {
    throw new Error('Streaming is not supported by this browser response.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');

  let buffer = '';
  let answer = '';
  let resolvedSessionId = sessionId;
  let resolvedMetadata: Partial<ChatV3Response> | undefined;
  let done = false;

  while (!done) {
    const { value, done: streamEnded } = await reader.read();
    if (streamEnded) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    let sepIndex = buffer.indexOf('\n\n');
    while (sepIndex !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      const payload = parseSseDataLines(rawEvent);
      if (!payload) {
        sepIndex = buffer.indexOf('\n\n');
        continue;
      }

      if (payload === '[DONE]') {
        done = true;
        break;
      }

      let streamErrorMessage: string | null = null;
      try {
        const parsed = JSON.parse(payload) as Record<string, unknown>;
        const type = typeof parsed.type === 'string' ? parsed.type : '';

        if (type === 'session') {
          const sid = cleanText(parsed.session_id);
          if (sid) {
            resolvedSessionId = sid;
            handlers.onSessionId?.(sid);
          }
        } else if (type === 'token') {
          const delta = typeof parsed.delta === 'string' ? parsed.delta : '';
          if (delta) {
            answer += delta;
            handlers.onToken?.(delta);
          }
        } else if (type === 'status') {
          const message =
            typeof parsed.message === 'string' ? parsed.message : '';
          if (message) {
            handlers.onStatus?.({
              stage: typeof parsed.stage === 'string' ? parsed.stage : undefined,
              message,
            });
          }
        } else if (type === 'metadata') {
          // Parse the metadata payload using the same normalizer as V3 responses
          const meta = normalizeV3Response(parsed, resolvedSessionId);
          resolvedMetadata = meta;
          handlers.onMetadata?.(meta);
        } else if (type === 'error') {
          const message =
            typeof parsed.error === 'string'
              ? parsed.error
              : 'Streaming response failed.';
          handlers.onError?.(message);
          streamErrorMessage = message;
        } else if (type === 'done') {
          handlers.onDone?.();
          done = true;
          break;
        } else if (typeof parsed.session_id === 'string') {
          const sid = cleanText(parsed.session_id);
          if (sid) {
            resolvedSessionId = sid;
            handlers.onSessionId?.(sid);
          }
        }
      } catch {
        // Payload is not valid JSON — skip it silently.
        // Do NOT append raw payload (could be a stray URL, error text, etc.).
        console.warn('[stream] non-JSON SSE payload skipped:', payload);
      }

      if (streamErrorMessage) {
        throw new Error(streamErrorMessage);
      }

      sepIndex = buffer.indexOf('\n\n');
    }
  }

  return {
    answer,
    sessionId: resolvedSessionId,
    metadata: resolvedMetadata,
  };
};

export const sendMessageV3 = async (
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 7,
  mode: 'auto' | 'rag' | 'agent' = 'auto',
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
): Promise<ChatV3Response> => {
  try {
    const identity = resolveChatIdentity(userContext, userId);

    const response = await apiClient.post(
      '/chat/v3',
      {
        question,
        mode,
        top_k: topK,
        history,
        session_id: sessionId,
        user_context: identity.userContext,
        user_id: identity.userId,
      } as ChatRequest,
      { headers: authHeaders() },
    );

    return normalizeV3Response(
      response.data as Record<string, unknown>,
      sessionId,
    );
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('API Error:', error.response?.data || error.message);
      throw new Error(
        error.response?.data?.detail ||
          'Failed to get response from the server. Please make sure the backend is running.',
      );
    }
    throw error;
  }
};

// Health check endpoint
export const checkHealth = async (): Promise<boolean> => {
  try {
    const response = await apiClient.get('/health');
    return response.data.status === 'healthy';
  } catch (error) {
    console.error('Health check failed:', error);
    return false;
  }
};

export const retrievalSearch = async (
  query: string,
  collections: string[] = ['ctdt'],
  resolvedMajor?: string,
  resolvedCohort?: string,
  topK: number = 7,
  rerank: boolean = true,
): Promise<RetrievalSearchResponse> => {
  try {
    const response = await apiClient.post('/retrieval/search', {
      query,
      collections,
      resolved_major: resolvedMajor,
      resolved_cohort: resolvedCohort,
      top_k: topK,
      rerank,
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('Retrieval API Error:', error.response?.data || error.message);
      throw new Error(
        error.response?.data?.detail || 'Failed to get retrieval results.',
      );
    }
    throw error;
  }
};

export const getEvalDashboard = async (
  suite?: 'historical_email' | 'current_policy',
  limit: number = 10,
): Promise<EvalDashboardResponse> => {
  try {
    const response = await apiClient.get('/metrics/eval', {
      params: { suite, limit },
    });
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('Eval metrics API Error:', error.response?.data || error.message);
      throw new Error(
        error.response?.data?.detail || 'Failed to load evaluation metrics.',
      );
    }
    throw error;
  }
};
