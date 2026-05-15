import type { AxiosInstance } from 'axios';
import type { LookupDocument, SuggestedQuestion } from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const lookupCTDT = async (
  client: AxiosInstance,
  majorCode: string,
  cohort?: string,
): Promise<{
  major_code: string;
  cohort?: string | null;
  program_name: string;
  documents: LookupDocument[];
}> => {
  const response = await client.get(`${API_PATHS.LOOKUP_CTDT}/${majorCode}`, {
    params: cohort ? { cohort } : undefined,
  });
  return response.data;
};

export const lookupRegulations = async (
  client: AxiosInstance,
  params: { category?: string; cohort?: string } = {},
): Promise<{ regulations: LookupDocument[] }> => {
  const response = await client.get(API_PATHS.LOOKUP_REGULATIONS, { params });
  return response.data;
};

export const lookupCalendar = async (
  client: AxiosInstance,
  semester?: string,
): Promise<{ events: LookupDocument[] }> => {
  const response = await client.get(API_PATHS.LOOKUP_CALENDAR, {
    params: semester ? { semester } : undefined,
  });
  return response.data;
};

export const lookupCompare = async (
  client: AxiosInstance,
  params: { topic: string; cohort1: string; cohort2: string },
): Promise<{
  comparison: {
    topic: string;
    cohort1: string;
    cohort2: string;
    answer: string;
    sources: unknown[];
  };
}> => {
  const response = await client.get(API_PATHS.LOOKUP_COMPARE, { params });
  return response.data;
};

export const getSuggestedQuestions = async (
  client: AxiosInstance,
): Promise<SuggestedQuestion[]> => {
  const response = await client.get<{ suggestions: SuggestedQuestion[] }>(
    API_PATHS.CHAT_SUGGEST,
  );
  return response.data.suggestions;
};
