# Mobile Architecture Plan — RAG Student Assistant

> Tài liệu kiến trúc mở rộng hệ thống RAG_v2 sang React Native (Expo).

---

## 1. Kiến trúc Monorepo (Code Sharing)

### 1.1 Công cụ: Yarn Workspaces + Turborepo

```
RAG_v2/
├── package.json              # Root workspace config
├── turbo.json                # Turborepo pipeline
├── packages/
│   └── shared/               # Shared code (TS only, no JSX)
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── types/
│           │   ├── chat.ts          # Message, ChatRequest, ChatResponse, RetrievedDocument...
│           │   ├── auth.ts          # UserContext, Session, LoginRequest...
│           │   └── index.ts
│           ├── api/
│           │   ├── client.ts        # createApiClient(baseURL, getToken) factory
│           │   ├── chatApi.ts       # sendMessage, sendMessageV3 (platform-agnostic)
│           │   ├── sessionApi.ts    # listSessions, getSession
│           │   ├── authApi.ts       # login, register, refresh
│           │   └── index.ts
│           ├── utils/
│           │   ├── sanitize.ts      # cleanText, sanitizeUserContext
│           │   ├── normalize.ts     # normalizeV3Response, mapSourceToRetrieved
│           │   └── constants.ts     # API paths, CLARIFY_SENTINEL
│           ├── stores/
│           │   ├── chatStore.ts     # Zustand chat state (platform-agnostic)
│           │   └── authStore.ts     # Zustand auth state (storage adapter injected)
│           └── index.ts
├── frontend/
│   └── chat-companion/       # Existing web app (Vite + React)
│       ├── package.json      # depends on @rag/shared
│       └── src/
├── mobile/                   # New Expo app
│   ├── package.json          # depends on @rag/shared
│   └── src/
└── backend/                  # Python backend (unchanged)
```

### 1.2 Root `package.json`

```json
{
  "name": "rag-student-assistant",
  "private": true,
  "workspaces": ["packages/*", "frontend/chat-companion", "mobile"],
  "devDependencies": {
    "turbo": "^2.5.0",
    "typescript": "^5.8.3"
  },
  "scripts": {
    "dev:web": "turbo run dev --filter=chat-companion",
    "dev:mobile": "turbo run dev --filter=mobile",
    "build": "turbo run build",
    "lint": "turbo run lint",
    "typecheck": "turbo run typecheck"
  }
}
```

### 1.3 `turbo.json`

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": { "dependsOn": ["^build"], "outputs": ["dist/**"] },
    "dev": { "cache": false, "persistent": true },
    "lint": {},
    "typecheck": { "dependsOn": ["^build"] }
  }
}
```

### 1.4 Shared Package `packages/shared/package.json`

```json
{
  "name": "@rag/shared",
  "version": "1.0.0",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "dependencies": {
    "axios": "^1.13.2",
    "zustand": "^5.0.0",
    "zod": "^3.25.0"
  }
}
```

### 1.5 Những gì CHIA SẺ vs KHÔNG chia sẻ

| Layer | Shared (`@rag/shared`) | Platform-specific |
|-------|----------------------|-------------------|
| **Types** | ✅ `Message`, `ChatRequest`, `ChatResponse`, `UserContext`, `Session`, `Turn`, `RetrievedDocument` | — |
| **API Client** | ✅ Factory `createApiClient()` + tất cả endpoint functions | ❌ SSE streaming (khác nhau giữa web/mobile) |
| **State** | ✅ Zustand stores (inject storage adapter) | ❌ Storage implementation |
| **Utils** | ✅ `sanitizeUserContext`, `normalizeV3Response`, `cleanText` | — |
| **UI** | ❌ | ✅ Web: React DOM / Mobile: React Native |
| **Storage** | ❌ | ✅ Web: `localStorage` / Mobile: `expo-secure-store` |
| **SSE** | ❌ | ✅ Web: `ReadableStream` / Mobile: `react-native-sse` |

### 1.6 API Client Factory Pattern

```typescript
// packages/shared/src/api/client.ts
import axios, { type AxiosInstance } from 'axios';

export interface ApiClientConfig {
  baseURL: string;
  getToken?: () => Promise<string | null>;
  timeout?: number;
}

export const createApiClient = (config: ApiClientConfig): AxiosInstance => {
  const client = axios.create({
    baseURL: config.baseURL,
    timeout: config.timeout ?? 120_000,
    headers: { 'Content-Type': 'application/json' },
  });

  client.interceptors.request.use(async (req) => {
    if (config.getToken) {
      const token = await config.getToken();
      if (token) req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
  });

  return client;
};
```

---

## 2. Giải pháp Streaming (SSE) trên Mobile

### 2.1 Vấn đề

React Native `fetch()` **không hỗ trợ** `ReadableStream` (`response.body` = `null`). Web frontend hiện tại dùng `response.body.getReader()` — cách này sẽ **CRASH** trên mobile.

### 2.2 Giải pháp: `react-native-sse`

**Thư viện chọn:** [`react-native-sse`](https://github.com/binaryminds/react-native-sse) — native EventSource cho RN.

**Lý do:**
- Dùng native `NSURLSession` (iOS) / `OkHttp` (Android) — ổn định, không bị timeout
- Hỗ trợ POST request với custom headers (cần cho JWT auth)
- Tự động reconnect khi mất kết nối
- Bundle size nhỏ (~15KB)

**Cài đặt:**
```bash
npx expo install react-native-sse
```

### 2.3 Implementation: `useStreamChat` Hook

```typescript
// mobile/src/hooks/useStreamChat.ts
import EventSource from 'react-native-sse';
import { useCallback, useRef, useState } from 'react';
import { getToken } from '../services/secureStorage';
import type { ChatRequest } from '@rag/shared';

interface StreamState {
  answer: string;
  isStreaming: boolean;
  sessionId: string | null;
  error: string | null;
}

export const useStreamChat = (apiBaseUrl: string) => {
  const [state, setState] = useState<StreamState>({
    answer: '', isStreaming: false, sessionId: null, error: null,
  });
  const esRef = useRef<EventSource | null>(null);

  const startStream = useCallback(async (request: ChatRequest) => {
    // Cleanup previous stream
    esRef.current?.close();
    setState({ answer: '', isStreaming: true, sessionId: null, error: null });

    const token = await getToken();
    const url = `${apiBaseUrl}/chat/stream`;

    const es = new EventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });
    esRef.current = es;

    // Buffer to accumulate answer
    let buffer = '';

    es.addEventListener('message', (event: any) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'session') {
          setState(prev => ({ ...prev, sessionId: data.session_id }));
        } else if (data.type === 'token') {
          buffer += data.delta || '';
          setState(prev => ({ ...prev, answer: buffer }));
        } else if (data.type === 'metadata') {
          // Store metadata for later use (sources, timings, etc.)
          setState(prev => ({ ...prev, metadata: data.data }));
        } else if (data.type === 'done') {
          setState(prev => ({ ...prev, isStreaming: false }));
          es.close();
        } else if (data.type === 'error') {
          setState(prev => ({
            ...prev, isStreaming: false, error: data.error,
          }));
          es.close();
        }
      } catch {
        // Plain text token fallback
        buffer += event.data;
        setState(prev => ({ ...prev, answer: buffer }));
      }
    });

    es.addEventListener('error', (event: any) => {
      setState(prev => ({
        ...prev, isStreaming: false,
        error: event.message || 'Connection lost',
      }));
      es.close();
    });
  }, [apiBaseUrl]);

  const stopStream = useCallback(() => {
    esRef.current?.close();
    setState(prev => ({ ...prev, isStreaming: false }));
  }, []);

  return { ...state, startStream, stopStream };
};
```

### 2.4 Fallback Strategy

```
Ưu tiên 1: react-native-sse (EventSource native)
    │ fail?
    ▼
Ưu tiên 2: Custom fetch + TextDecoder polyfill (react-native-polyfill-globals)
    │ fail?
    ▼
Ưu tiên 3: POST /chat (non-streaming) — blocking nhưng luôn hoạt động
```

### 2.5 So sánh SSE Libraries

| Thư viện | POST support | Auth header | Auto-reconnect | Bundle | Recommend |
|----------|-------------|-------------|----------------|--------|-----------|
| `react-native-sse` | ✅ | ✅ | ✅ | 15KB | ✅ **Chọn** |
| `@microsoft/fetch-event-source` | ✅ | ✅ | ✅ | 8KB | ⚠️ Cần polyfill TextDecoder |
| `rn-fetch-blob` + manual parse | ✅ | ✅ | ❌ | 200KB | ❌ Quá nặng |
| Native `EventSource` (web API) | ❌ GET only | ❌ | ✅ | 0 | ❌ Không hỗ trợ POST |

---

## 3. Chuyển đổi UI Components

### 3.1 Bảng Mapping thư viện UI

| Chức năng | Web (hiện tại) | Mobile (đề xuất) | Ghi chú |
|-----------|---------------|-----------------|---------|
| **Styling** | TailwindCSS 3.x | NativeWind 4.x | Reuse Tailwind classes, `className` → `className` |
| **CSS Variables** | HSL CSS vars | NativeWind themes | Map `--primary` → NativeWind theme tokens |
| **UI Kit** | shadcn/ui + Radix | React Native Paper hoặc Tamagui | Paper dễ setup hơn, Tamagui nếu cần perf |
| **Markdown** | `react-markdown` + `remark-gfm` | `react-native-markdown-display` | Hỗ trợ tables, code blocks, links |
| **Icons** | `lucide-react` | `@expo/vector-icons` (Ionicons) | Expo built-in, no native linking |
| **Navigation** | `react-router-dom` | `@react-navigation/native` | Stack + Bottom Tabs |
| **Toast/Snackbar** | `sonner` | `react-native-toast-message` | — |
| **Bottom Sheet** | `vaul` (Drawer) | `@gorhom/bottom-sheet` | Cho Source Viewer |
| **Scroll Area** | `@radix-ui/react-scroll-area` | `FlatList` / `ScrollView` | Native components |
| **Animation** | CSS `keyframes` | `react-native-reanimated` | Layout animations, typing indicator |
| **Form** | `react-hook-form` + `zod` | `react-hook-form` + `zod` | ✅ **Dùng chung** qua `@rag/shared` |
| **HTTP** | `axios` | `axios` | ✅ **Dùng chung** qua `@rag/shared` |
| **Server State** | `@tanstack/react-query` | `@tanstack/react-query` | ✅ **Dùng chung** |

### 3.2 Mapping HTML Elements → React Native

| Web (HTML/React DOM) | Mobile (React Native) | Lưu ý |
|---------------------|----------------------|-------|
| `<div>` | `<View>` | Default `flexDirection: 'column'` |
| `<span>`, `<p>` | `<Text>` | Mọi text PHẢI trong `<Text>` |
| `<img>` | `<Image>` | Cần `width`/`height` explicit |
| `<button>` | `<Pressable>` / `<TouchableOpacity>` | Dùng `Pressable` (newer API) |
| `<input>` | `<TextInput>` | — |
| `<a href>` | `<Pressable>` + `Linking.openURL()` | — |
| `<ul>/<ol>` | `<FlatList>` / `<View>` loop | `FlatList` cho list dài |
| `<svg>` | `react-native-svg` hoặc Icon component | — |
| `className="..."` | `className="..."` (NativeWind) | NativeWind bridge |
| `onClick` | `onPress` | — |
| `hover:` pseudo | Không có | Dùng `Pressable` style function |

### 3.3 Component Migration Map

| Web Component | Mobile Component | Shared Logic |
|--------------|-----------------|-------------|
| `ChatContainer.tsx` | `ChatScreen.tsx` | Chat state (Zustand) |
| `ChatMessage.tsx` | `MessageBubble.tsx` | Message type from `@rag/shared` |
| `ChatInput.tsx` | `ChatInput.tsx` | Validation logic |
| `TypingIndicator.tsx` | `TypingIndicator.tsx` | Animation khác (Reanimated) |
| Source panel (inline) | `SourceBottomSheet.tsx` | Source data types |
| ReactMarkdown render | `MarkdownDisplay.tsx` | — |

### 3.4 NativeWind Setup

```typescript
// mobile/tailwind.config.ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      // Reuse tokens from web tailwind.config.ts
      colors: {
        primary: { DEFAULT: '#6366f1', foreground: '#ffffff' },
        secondary: { DEFAULT: '#f1f5f9', foreground: '#334155' },
        muted: { DEFAULT: '#f1f5f9', foreground: '#64748b' },
        chat: {
          user: '#ede9fe',
          assistant: '#ffffff',
        },
      },
      fontFamily: { sans: ['Inter'] },
    },
  },
} satisfies Config;
```

---

## 4. Bảo mật & Local Storage

### 4.1 So sánh Web vs Mobile Storage

| Mục đích | Web (hiện tại) | Mobile (đề xuất) | Lý do |
|----------|---------------|-----------------|-------|
| **JWT Access Token** | `localStorage` | `expo-secure-store` | Encrypted keychain (iOS) / Keystore (Android) |
| **Refresh Token** | `localStorage` | `expo-secure-store` | Không bao giờ lưu token nhạy cảm trong AsyncStorage |
| **User Profile cache** | `localStorage` | `expo-secure-store` | Chứa MSSV, thông tin cá nhân |
| **Chat history cache** | Không cache | `MMKV` (`react-native-mmkv`) | Nhanh 30x hơn AsyncStorage, cho offline |
| **App Settings** | `localStorage` | `MMKV` | Theme, language, non-sensitive |
| **FAQ Cache** | Không | `MMKV` | Offline mode |

### 4.2 Secure Storage Implementation

```typescript
// mobile/src/services/secureStorage.ts
import * as SecureStore from 'expo-secure-store';

const KEYS = {
  ACCESS_TOKEN: 'auth_access_token',
  REFRESH_TOKEN: 'auth_refresh_token',
  USER_PROFILE: 'user_profile',
  SESSION_ID: 'current_session_id',
} as const;

export const setToken = async (access: string, refresh: string) => {
  await SecureStore.setItemAsync(KEYS.ACCESS_TOKEN, access);
  await SecureStore.setItemAsync(KEYS.REFRESH_TOKEN, refresh);
};

export const getToken = async (): Promise<string | null> =>
  SecureStore.getItemAsync(KEYS.ACCESS_TOKEN);

export const getRefreshToken = async (): Promise<string | null> =>
  SecureStore.getItemAsync(KEYS.REFRESH_TOKEN);

export const clearTokens = async () => {
  await SecureStore.deleteItemAsync(KEYS.ACCESS_TOKEN);
  await SecureStore.deleteItemAsync(KEYS.REFRESH_TOKEN);
};

export const setUserProfile = async (profile: object) =>
  SecureStore.setItemAsync(KEYS.USER_PROFILE, JSON.stringify(profile));

export const getUserProfile = async () => {
  const raw = await SecureStore.getItemAsync(KEYS.USER_PROFILE);
  return raw ? JSON.parse(raw) : null;
};
```

### 4.3 Zustand Store + Secure Storage Adapter

```typescript
// packages/shared/src/stores/authStore.ts
import { createStore } from 'zustand';

export interface AuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
  user: { student_id: string; cohort: string; major: string } | null;
  setAuth: (token: string, user: AuthState['user']) => void;
  clearAuth: () => void;
}

// Platform-agnostic store — storage persistence injected per platform
export const createAuthStore = () =>
  createStore<AuthState>((set) => ({
    isAuthenticated: false,
    accessToken: null,
    user: null,
    setAuth: (token, user) =>
      set({ isAuthenticated: true, accessToken: token, user }),
    clearAuth: () =>
      set({ isAuthenticated: false, accessToken: null, user: null }),
  }));
```

```typescript
// mobile/src/stores/authStore.ts — mobile wiring
import { createAuthStore } from '@rag/shared';
import { setToken, clearTokens, getToken } from '../services/secureStorage';

export const authStore = createAuthStore();

// Sync to SecureStore on state change
authStore.subscribe(async (state, prev) => {
  if (state.accessToken !== prev.accessToken) {
    if (state.accessToken) {
      await setToken(state.accessToken, ''); // refresh handled separately
    } else {
      await clearTokens();
    }
  }
});
```

### 4.4 Axios Interceptor với Auto-Refresh

```typescript
// mobile/src/services/api.ts
import { createApiClient } from '@rag/shared';
import { getToken, getRefreshToken, setToken, clearTokens } from './secureStorage';
import { API_BASE_URL } from '../utils/constants';

export const apiClient = createApiClient({
  baseURL: API_BASE_URL,
  getToken,
});

// 401 interceptor — auto refresh
apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status !== 401) throw error;
    const refresh = await getRefreshToken();
    if (!refresh) { clearTokens(); throw error; }

    try {
      const { data } = await apiClient.post('/auth/refresh', { refresh_token: refresh });
      await setToken(data.access_token, data.refresh_token || refresh);
      error.config.headers.Authorization = `Bearer ${data.access_token}`;
      return apiClient.request(error.config);
    } catch {
      await clearTokens();
      throw error;
    }
  }
);
```

---

## 5. Lệnh Khởi tạo Dự án

### 5.1 Khởi tạo Expo App

```bash
# Từ thư mục RAG_v2/
cd /Users/nam.nguyen/Documents/personal/GR/src/RAG_v2

# 1. Tạo Expo app với TypeScript template
npx -y create-expo-app@latest mobile --template blank-typescript

# 2. Cài dependencies chính
cd mobile
npx expo install expo-secure-store expo-constants expo-linking expo-status-bar

# 3. Navigation
npm install @react-navigation/native @react-navigation/bottom-tabs @react-navigation/native-stack
npx expo install react-native-screens react-native-safe-area-context

# 4. NativeWind (TailwindCSS cho RN)
npm install nativewind tailwindcss
npx tailwindcss init

# 5. SSE Streaming
npm install react-native-sse

# 6. UI & UX
npm install react-native-markdown-display @gorhom/bottom-sheet react-native-reanimated react-native-gesture-handler
npx expo install react-native-reanimated react-native-gesture-handler

# 7. State & Data
npm install zustand @tanstack/react-query axios react-hook-form zod @hookform/resolvers

# 8. Storage
npm install react-native-mmkv

# 9. Dev tools
npm install -D typescript @types/react
```

### 5.2 Khởi tạo Monorepo Root

```bash
# Từ thư mục RAG_v2/
cd /Users/nam.nguyen/Documents/personal/GR/src/RAG_v2

# 1. Init root package.json (nếu chưa có)
npm init -y

# 2. Cài Turborepo
npm install -D turbo

# 3. Tạo shared package
mkdir -p packages/shared/src/{types,api,utils,stores}

# 4. Init shared package.json
cd packages/shared && npm init -y && cd ../..

# 5. Cập nhật root package.json workspaces
# (xem Section 1.2 ở trên)

# 6. Di chuyển shared types từ frontend
cp frontend/chat-companion/src/types/chat.ts packages/shared/src/types/chat.ts
```

### 5.3 Cấu trúc thư mục Mobile App

```
mobile/
├── app.json
├── babel.config.js
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── App.tsx
├── src/
│   ├── navigation/
│   │   ├── RootNavigator.tsx
│   │   ├── AuthStack.tsx
│   │   ├── MainTabNavigator.tsx
│   │   └── ChatStack.tsx
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── LoginScreen.tsx
│   │   │   └── RegisterScreen.tsx
│   │   ├── chat/
│   │   │   ├── ChatScreen.tsx
│   │   │   └── SessionListScreen.tsx
│   │   └── profile/
│   │       └── ProfileScreen.tsx
│   ├── components/
│   │   ├── chat/
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── StreamingText.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   ├── SourceBottomSheet.tsx
│   │   │   └── MarkdownDisplay.tsx
│   │   └── common/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   ├── hooks/
│   │   ├── useStreamChat.ts
│   │   ├── useAuth.ts
│   │   └── useProfile.ts
│   ├── services/
│   │   ├── api.ts
│   │   └── secureStorage.ts
│   ├── stores/
│   │   ├── authStore.ts
│   │   └── chatStore.ts
│   └── utils/
│       └── constants.ts
└── assets/
```

---

## 6. Tổng kết Architecture Decisions

| Quyết định | Lựa chọn | Lý do |
|-----------|----------|-------|
| Monorepo tool | Yarn Workspaces + Turborepo | Caching, parallel builds, workspace linking |
| Shared code scope | Types + API client + Zustand stores + Utils | Tối đa reuse, tối thiểu platform coupling |
| SSE library | `react-native-sse` | Native impl, POST support, auto-reconnect |
| Styling | NativeWind 4.x | Reuse Tailwind classes từ web |
| Secure storage | `expo-secure-store` (tokens) + `MMKV` (cache) | Keychain encryption cho sensitive data |
| Navigation | React Navigation v6 | De-facto standard cho Expo |
| State management | Zustand (shared) + React Query | Lightweight, đã dùng trên web |

### Rủi ro & Mitigation

| Rủi ro | Mitigation |
|--------|-----------|
| NativeWind không hỗ trợ 100% Tailwind classes | Dùng `StyleSheet` fallback cho edge cases |
| `react-native-sse` timeout trên kết nối yếu | Implement heartbeat check + fallback sang `/chat` non-streaming |
| Monorepo Metro bundler resolution | Cấu hình `metro.config.js` với `watchFolders` trỏ tới `packages/shared` |
| `expo-secure-store` giới hạn 2KB/value | Chỉ lưu token + profile nhỏ, cache lớn dùng MMKV |
