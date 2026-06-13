import type { Page, Route } from '@playwright/test';

export const API = 'http://localhost:8000';

export interface MockUser {
  _id: string;
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
  email: string;
  role?: string;
  is_profile_complete: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string;
}

export const studentUser: MockUser = {
  _id: 'user-student-1',
  full_name: 'Nguyễn Văn An',
  student_id: '20210001',
  cohort: 'K66',
  major: 'Khoa học Máy tính',
  major_code: 'IT1',
  email: 'an.nv210001@sis.hust.edu.vn',
  role: 'student',
  is_profile_complete: true,
  is_active: true,
  created_at: '2024-09-01T00:00:00Z',
  updated_at: '2024-09-01T00:00:00Z',
  last_login_at: '2025-06-13T00:00:00Z',
};

export const adminUser: MockUser = {
  ...studentUser,
  _id: 'user-admin-1',
  full_name: 'Trần Quản Trị',
  email: 'admin@hust.edu.vn',
  role: 'admin',
};

// A non-expiring dummy JWT (header.payload.signature) — payload carries a far-future exp
// so the client never tries to refresh during a test run.
const dummyJwt = (() => {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ sub: 'test', exp: 4102444800 })).toString('base64url');
  return `${header}.${payload}.sig`;
})();

/** A realistic streaming answer with two RAG sources (PDF + CTT article). */
export const sampleSources = [
  {
    rank: 1,
    content:
      'Điều 14. Sinh viên được xét tốt nghiệp khi tích lũy đủ số tín chỉ theo chương trình đào tạo và đạt điểm trung bình tích lũy từ 2.0 trở lên.',
    score: 0.91,
    rerank_score: 0.91,
    collection: 'quydinh',
    metadata: {
      title: 'QD_quy-che-dao-tao-DH_2023.pdf',
      collection: 'quydinh',
      dieu: '14',
      page: '12',
      url: 'https://ctt.hust.edu.vn/quy-che-dao-tao',
    },
  },
  {
    rank: 2,
    content:
      'Kế hoạch nộp học phí kỳ 20252 đợt 2, hạn cuối 01/06/2026 qua cổng thanh toán trực tuyến.',
    score: 0.84,
    rerank_score: 0.84,
    collection: 'kehoach',
    metadata: {
      title: 'Kế hoạch nộp học phí kỳ 20252',
      collection: 'kehoach',
      page: '1',
      url: 'https://ctt.hust.edu.vn/ke-hoach-hoc-phi',
    },
  },
];

const ANSWER =
  'Theo **Quy chế đào tạo đại học 2023**, bạn được xét tốt nghiệp khi tích lũy đủ tín chỉ và đạt CPA từ 2.0 trở lên.';

/** Build a Server-Sent-Events body matching the /chat/stream protocol. */
export function buildSseBody(options: { sessionId?: string; turnId?: number } = {}): string {
  const sessionId = options.sessionId ?? 'sess-test-1';
  const turnId = options.turnId ?? 1;
  const events: string[] = [];
  const push = (obj: unknown) => events.push(`data: ${JSON.stringify(obj)}\n\n`);

  push({ type: 'session', session_id: sessionId });
  push({ type: 'status', stage: 'retrieving', message: 'Đang tìm tài liệu liên quan…' });
  // Token stream — concatenated client-side into the full answer.
  for (const token of ['Theo ', '**Quy chế đào tạo đại học 2023**', ', bạn được xét tốt nghiệp ', 'khi tích lũy đủ tín chỉ và đạt CPA từ 2.0 trở lên.']) {
    push({ type: 'token', delta: token });
  }
  push({
    type: 'metadata',
    answer: ANSWER,
    question: 'Điều kiện tốt nghiệp?',
    session_id: sessionId,
    turn_id: turnId,
    mode: 'rag',
    route: 'quydinh',
    model_name: 'gpt-test',
    num_documents: sampleSources.length,
    retrieved_documents: sampleSources,
    target_collections: ['quydinh', 'kehoach'],
    collection_scores: [
      { collection: 'quydinh', score: 0.91 },
      { collection: 'kehoach', score: 0.62 },
    ],
    routing_probabilities: { quydinh: 0.8, kehoach: 0.2 },
    timings_ms: { retrieval: 320, generation: 1400 },
  });
  push({ type: 'done' });
  events.push('data: [DONE]\n\n');
  return events.join('');
}

export interface MockOptions {
  user?: MockUser;
  /** Force the /chat/stream endpoint to fail so the error+retry UI is exercised. */
  failStream?: boolean;
  /** Pre-seeded sessions returned from /sessions/me. */
  sessions?: Array<{ session_id: string; title: string | null; turn_count: number }>;
}

/**
 * Intercept every backend call so the app runs fully offline and deterministically.
 * Registers a single broad handler against the API origin.
 */
export async function mockBackend(page: Page, options: MockOptions = {}): Promise<void> {
  const user = options.user ?? studentUser;
  const sessions = options.sessions ?? [];
  let streamCalls = 0;

  await page.route(`${API}/**`, async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    // --- Auth ---
    if (path === '/auth/refresh' && method === 'POST') {
      return json({ access_token: dummyJwt, token_type: 'bearer', expires_in: 3600, user });
    }
    if (path === '/auth/logout') return json({ status: 'ok' });
    if (path === '/auth/me') return json(user);

    // --- Sessions ---
    if (path === '/sessions/me') return json({ sessions, count: sessions.length });
    if (path === '/session' && method === 'POST')
      return json({ session_id: 'sess-test-1', created_at: '2025-06-13T00:00:00Z' });
    if (path.startsWith('/session/')) {
      if (method === 'GET') {
        return json({ session_id: path.split('/').pop(), title: null, turns: [] });
      }
      return json({ updated: true });
    }

    // --- Chat streaming (the core flow) ---
    if (path === '/chat/stream' && method === 'POST') {
      streamCalls += 1;
      // Fail only the first attempt when failStream is set, so "Thử lại" can succeed.
      if (options.failStream && streamCalls === 1) {
        return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'backend down' }) });
      }
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' },
        body: buildSseBody(),
      });
    }

    // --- Feedback / bookmarks / notifications (header + message actions) ---
    if (path === '/feedback' && method === 'GET') return json({ feedback: null });
    if (path === '/feedback' && method === 'POST') return json({ status: 'ok' });
    if (path.startsWith('/bookmarks')) {
      if (method === 'POST') return json({ bookmark: { id: 'bm-1' } });
      if (method === 'DELETE') return json({ status: 'ok' });
      return json({ bookmark: null, bookmarks: [], folders: [] });
    }
    if (path.startsWith('/notifications')) {
      if (path.endsWith('/unread-count')) return json({ count: 0, unread_count: 0 });
      return json({ notifications: [], items: [], count: 0, total: 0 });
    }

    // --- Fallback: benign empty success so nothing hangs ---
    return json({});
  });
}

/**
 * Open the chat as a logged-in user. Auth is bootstrapped via the mocked
 * /auth/refresh call that RequireAuth triggers on mount.
 */
export async function gotoChat(page: Page, options: MockOptions = {}): Promise<void> {
  await mockBackend(page, options);
  await page.goto('/chat');
}
