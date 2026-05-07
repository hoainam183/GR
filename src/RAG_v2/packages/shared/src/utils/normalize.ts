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

/**
 * Map a raw source object from the backend into a typed RetrievedDocument.
 */
export const mapSourceToRetrieved = (
  source: Record<string, unknown>,
  rank: number,
): RetrievedDocument => ({
  rank,
  content: typeof source.text === 'string' ? source.text : '',
  score:
    typeof source.rerank_score === 'number'
      ? source.rerank_score
      : typeof source.score === 'number'
        ? source.score
        : 0,
  hybrid_score: typeof source.score === 'number' ? source.score : undefined,
  rerank_score:
    typeof source.rerank_score === 'number' ? source.rerank_score : undefined,
  vector_score:
    typeof source.vector_score === 'number' ? source.vector_score : undefined,
  keyword_score:
    typeof source.keyword_score === 'number' ? source.keyword_score : undefined,
  collection:
    typeof source.collection === 'string' ? source.collection : undefined,
  metadata:
    source.metadata && typeof source.metadata === 'object'
      ? (source.metadata as Record<string, unknown>)
      : {},
});

/**
 * Normalize a raw /chat/v3 or metadata payload into a typed ChatV3Response.
 */
export const normalizeV3Response = (
  payload: Record<string, unknown>,
  fallbackSessionId?: string,
): ChatV3Response => {
  const retrievedDocs = Array.isArray(payload.retrieved_documents)
    ? (payload.retrieved_documents as RetrievedDocument[])
    : Array.isArray(payload.sources)
      ? (payload.sources as Record<string, unknown>[]).map((source, index) =>
          mapSourceToRetrieved(source, index + 1),
        )
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
    num_documents:
      typeof payload.num_documents === 'number'
        ? payload.num_documents
        : typeof payload.num_sources === 'number'
          ? payload.num_sources
          : retrievedDocs.length,
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
