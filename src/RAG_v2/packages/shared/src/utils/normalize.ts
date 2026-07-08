/**
 * Response normalization utilities.
 * Extracted from frontend/chat-companion/src/services/chatApi.ts
 */

import type {
  ChatResponse,
  ChatV3Response,
  RetrievedDocument,
} from '../types/chat';
import { cleanText } from './sanitize';

const asRecord = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const asNonEmptyString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim() ? value.trim() : undefined;

const hasUsefulMetadata = (metadata: Record<string, unknown>): boolean =>
  [
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
  ].some((key) => asNonEmptyString(metadata[key]));

export const isDisplayableRetrievedDocument = (
  doc: RetrievedDocument,
): boolean =>
  Boolean(doc.content.trim()) || hasUsefulMetadata(doc.metadata);

/**
 * Map a raw source object from the backend into a typed RetrievedDocument.
 */
export const mapSourceToRetrieved = (
  source: Record<string, unknown>,
  rank: number,
): RetrievedDocument => ({
  rank: asNumber(source.rank) ?? rank,
  content:
    typeof source.content === 'string'
      ? source.content
      : typeof source.text === 'string'
        ? source.text
        : typeof source.chunk_text === 'string'
          ? source.chunk_text
          : '',
  score: asNumber(source.rerank_score) ?? asNumber(source.score) ?? 0,
  hybrid_score: asNumber(source.score),
  rerank_score: asNumber(source.rerank_score),
  vector_score: asNumber(source.vector_score),
  keyword_score: asNumber(source.keyword_score),
  collection:
    typeof source.collection === 'string' ? source.collection : undefined,
  metadata:
    source.metadata && typeof source.metadata === 'object'
      ? (source.metadata as Record<string, unknown>)
      : {},
});

export const normalizeRetrievedDocuments = (
  sources: unknown,
): RetrievedDocument[] =>
  Array.isArray(sources)
    ? sources
        .map((source, index) =>
          mapSourceToRetrieved(asRecord(source) ?? {}, index + 1),
        )
        .filter(isDisplayableRetrievedDocument)
    : [];

/**
 * Normalize a raw /chat/v3 or metadata payload into a typed ChatV3Response.
 */
export const normalizeV3Response = (
  payload: Record<string, unknown>,
  fallbackSessionId?: string,
): ChatV3Response => {
  const retrievedDocs = Array.isArray(payload.retrieved_documents)
    ? normalizeRetrievedDocuments(payload.retrieved_documents)
    : Array.isArray(payload.sources)
      ? normalizeRetrievedDocuments(payload.sources)
      : [];

  const toolsFromTrace =
    payload.agent_trace &&
    typeof payload.agent_trace === 'object' &&
    Array.isArray(
      (payload.agent_trace as Record<string, unknown>).tool_calls,
    )
      ? ((payload.agent_trace as Record<string, unknown>)
          .tool_calls as ChatV3Response['tool_calls'])
      : [];

  const toolsUsedFromTrace =
    payload.agent_trace &&
    typeof payload.agent_trace === 'object' &&
    Array.isArray(
      (payload.agent_trace as Record<string, unknown>).tool_names_sequence,
    )
      ? ((payload.agent_trace as Record<string, unknown>)
          .tool_names_sequence as string[])
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
    session_id: cleanText(payload.session_id) || fallbackSessionId || '',
    turn_id:
      typeof payload.turn_id === 'number'
        ? payload.turn_id
        : typeof payload.turn_id === 'string'
          ? Number(payload.turn_id)
          : undefined,
    routing_probabilities:
      payload.routing_probabilities &&
      typeof payload.routing_probabilities === 'object'
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
