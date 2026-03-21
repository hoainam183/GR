import axios from 'axios';
import type { ChatRequest, ChatResponse } from '@/types/chat';

// Backend API endpoint
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Configure axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000 * 2, // 60*2 seconds timeout for RAG processing
  headers: {
    'Content-Type': 'application/json',
  },
});

export const sendMessage = async (
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 5,
): Promise<ChatResponse> => {
  try {
    const response = await apiClient.post<ChatResponse>('/chat', {
      question,
      top_k: topK,
      history,
    } as ChatRequest);
    
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('API Error:', error.response?.data || error.message);
      throw new Error(
        error.response?.data?.detail || 
        'Failed to get response from the server. Please make sure the backend is running.'
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
