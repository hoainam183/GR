import { test, expect, type Page, type Route } from '@playwright/test';
import { adminUser } from './mocks';

/**
 * Mocked-backend E2E for four admin-console UI/UX fixes:
 *
 *  1. Reloading any admin page must restore the last-selected tab (was: always
 *     snapped back to "Tổng quan").
 *  2. Finishing a pipeline step must auto-jump the review tabs to that step's
 *     output (was: admin had to click the tab manually).
 *  3. Deleting a chunk must NOT scroll the page back to the top.
 *  4. Chunk pagination must be able to navigate back to page 1 (was: "Trước"
 *     from page 2 did nothing).
 *
 * No real backend is required — every /admin call is intercepted below.
 */

const API = 'http://localhost:8000';

// A non-expiring dummy JWT so the client never tries a real refresh mid-test.
const dummyJwt = (() => {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ sub: 'admin', exp: 4102444800 })).toString('base64url');
  return `${header}.${payload}.sig`;
})();

interface Chunk {
  chunk_id: string;
  chunk_index: number;
  content: string;
  metadata: Record<string, unknown>;
  edited?: boolean;
}

function buildDoc(status: string, overrides: Record<string, unknown> = {}) {
  return {
    id: 'doc-1',
    filename: 'quy-che-dao-tao.pdf',
    file_size: 2_500_000,
    status,
    collection: 'quydinh',
    chunking_strategy: 'recursive',
    converter: 'pymupdf4llm',
    chunk_count: 45,
    markdown_reviewed: false,
    cleaned_reviewed: false,
    chunks_reviewed: false,
    llm_clean_requested: false,
    llm_cleaned_reviewed: false,
    llm_clean_warnings: null,
    metadata_overrides: {},
    uploaded_by: 'admin',
    uploaded_at: '2026-07-01T00:00:00Z',
    error_message: null,
    converted_at: '2026-07-01T00:05:00Z',
    cleaned_at: null,
    llm_cleaned_at: null,
    chunked_at: null,
    indexed_at: null,
    ...overrides,
  };
}

function buildChunks(count: number): Chunk[] {
  return Array.from({ length: count }, (_, i) => ({
    chunk_id: `chunk-${i}`,
    chunk_index: i,
    // Long, multi-line content so the chunk list is tall enough to scroll.
    content:
      `Điều ${i + 1}. Nội dung chunk số ${i} phục vụ kiểm thử giao diện.\n`.repeat(6) +
      `Đây là đoạn văn bản dài để bảo đảm danh sách chunk đủ cao để cuộn trang.`,
    metadata: { level: 'section' },
  }));
}

interface AdminState {
  doc: ReturnType<typeof buildDoc>;
  chunks: Chunk[];
}

/** Intercept every backend call the admin console makes and serve from `state`. */
async function mockAdmin(page: Page, state: AdminState): Promise<void> {
  await page.route(`${API}/**`, async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    // --- Auth ---
    if (path === '/auth/refresh' && method === 'POST') {
      return json({ access_token: dummyJwt, token_type: 'bearer', expires_in: 3600, user: adminUser });
    }
    if (path === '/auth/me') return json(adminUser);
    if (path === '/auth/logout') return json({ status: 'ok' });

    // --- Overview tab data (rendered on first visit) ---
    if (path === '/admin/stats/overview') {
      return json({
        total_users: 1280,
        total_sessions: 3400,
        total_queries: 9800,
        active_users_7d: 420,
        total_feedback: 210,
        satisfaction_rate: 87,
      });
    }
    if (path === '/admin/stats/users/breakdown') return json({ registrations: [] });

    // --- Converter / chunker option lists ---
    if (path === '/admin/converters') {
      return json({ converters: [{ key: 'pymupdf4llm', label: 'PyMuPDF4LLM', description: 'Nhanh' }] });
    }
    if (path === '/admin/chunkers') {
      return json({ chunkers: [{ key: 'recursive', label: 'Recursive', description: '', collections: [] }] });
    }

    // --- Document list ---
    if (path === '/admin/documents' && method === 'GET') {
      return json({ documents: [state.doc], total: 1, page: 1, limit: 20 });
    }

    // --- Chunk sub-resources (check specific paths before the list path) ---
    const chunkItem = path.match(/^\/admin\/documents\/[^/]+\/chunks\/([^/]+)$/);
    if (chunkItem && method === 'DELETE') {
      const chunkId = chunkItem[1];
      state.chunks = state.chunks.filter((c) => c.chunk_id !== chunkId);
      return json({ deleted_chunk_id: chunkId, remaining_chunks: state.chunks.length });
    }
    if (path.endsWith('/chunks/select') && method === 'POST') {
      return json({ kept_chunks: state.chunks.length, deleted_chunks: 0 });
    }
    if (path.endsWith('/chunk-strategies')) return json({ strategies: [] });
    if (path.endsWith('/chunks') && method === 'GET') {
      const pageNum = Number(url.searchParams.get('page') ?? '1');
      const limit = Number(url.searchParams.get('limit') ?? '20');
      const start = (pageNum - 1) * limit;
      const slice = state.chunks.slice(start, start + limit);
      const sizes = state.chunks.map((c) => c.content.length);
      return json({
        chunks: slice,
        total: state.chunks.length,
        page: pageNum,
        limit,
        strategy: 'recursive',
        stats: {
          avg_size: sizes.reduce((a, b) => a + b, 0) / (sizes.length || 1),
          min_size: Math.min(...sizes),
          max_size: Math.max(...sizes),
        },
      });
    }
    if (path.endsWith('/chunks') && method === 'PUT') {
      state.doc.chunks_reviewed = true;
      return json({ status: 'ok' });
    }

    // --- Review content ---
    if (path.endsWith('/markdown') && method === 'GET') return json({ content: '# Markdown\n\nNội dung markdown.' });
    if (path.endsWith('/cleaned') && method === 'GET') return json({ content: '# Cleaned\n\nNội dung đã làm sạch.' });
    if (path.endsWith('/llm-cleaned') && method === 'GET') return json({ content: 'LLM', warnings: [] });

    // --- Pipeline step triggers: advance status so polling picks up the result ---
    if (path.endsWith('/clean') && method === 'POST') {
      state.doc = buildDoc('cleaned', { cleaned_at: '2026-07-01T00:10:00Z' });
      return json({ status: 'ok' });
    }
    if (path.endsWith('/convert') && method === 'POST') {
      state.doc = buildDoc('converted');
      return json({ status: 'ok' });
    }
    if (path.endsWith('/chunk') && method === 'POST') {
      state.doc = buildDoc('chunked', { chunked_at: '2026-07-01T00:15:00Z' });
      return json({ status: 'ok' });
    }
    if (path.endsWith('/index') && method === 'POST') {
      state.doc = buildDoc('indexed', { chunks_reviewed: true, indexed_at: '2026-07-01T00:20:00Z' });
      return json({ status: 'ok' });
    }

    // --- Document detail (generic, after the sub-resource checks above) ---
    if (/^\/admin\/documents\/[^/]+$/.test(path)) {
      if (method === 'DELETE') return json({ status: 'ok' });
      return json(state.doc);
    }

    // Benign default so nothing hangs.
    return json({});
  });
}

test.describe('Admin console UI/UX fixes', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test('1. reload restores the previously selected tab (Tài liệu)', async ({ page }) => {
    await mockAdmin(page, { doc: buildDoc('uploaded'), chunks: [] });
    await page.goto('/admin');

    // Land on the default overview tab.
    await expect(page.getByRole('heading', { name: 'Dashboard quản trị' })).toBeVisible();

    // Switch to the Documents tab.
    await page.getByRole('tab', { name: 'Tài liệu' }).click();
    await expect(page.getByRole('button', { name: 'Làm mới' })).toBeVisible();

    // Reload — the Documents tab must still be the active one.
    await page.reload();
    await expect(page.getByRole('button', { name: 'Làm mới' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Tài liệu' }).first()).toHaveAttribute(
      'aria-selected',
      'true',
    );
    // And Overview must NOT be shown.
    await expect(page.getByRole('heading', { name: 'Dashboard quản trị' })).toHaveCount(0);
  });

  test('2. finishing a step auto-jumps to that step\'s review tab', async ({ page }) => {
    const state: AdminState = { doc: buildDoc('converted'), chunks: [] };
    await mockAdmin(page, state);
    await page.goto('/admin/documents/doc-1');

    // A freshly-converted doc opens on the Markdown tab.
    await expect(page.getByRole('tab', { name: 'Markdown' })).toHaveAttribute('aria-selected', 'true');

    // Run the next step ("Làm sạch"). When it finishes the UI should move to Cleaned.
    await page.getByRole('button', { name: /Bước tiếp/ }).click();
    await expect(page.getByRole('tab', { name: 'Cleaned' })).toHaveAttribute(
      'aria-selected',
      'true',
      { timeout: 10_000 },
    );
    await expect(page.getByRole('heading', { name: 'Nội dung đã làm sạch' })).toBeVisible();
  });

  test('3. deleting a chunk does not scroll the page to the top', async ({ page }) => {
    const state: AdminState = { doc: buildDoc('chunked'), chunks: buildChunks(20) };
    await mockAdmin(page, state);
    await page.goto('/admin/documents/doc-1');

    await page.getByRole('tab', { name: 'Chunks' }).click();
    await expect(page.getByText('Tổng: 20 chunks')).toBeVisible();

    // Scroll down into the list.
    await page.evaluate(() => window.scrollTo(0, 1500));
    const before = await page.evaluate(() => window.scrollY);
    expect(before).toBeGreaterThan(500);

    // Delete a chunk that is currently in view.
    const deleteButtons = page.getByRole('button', { name: 'Xóa', exact: true });
    await deleteButtons.nth(6).click();
    await page.getByRole('button', { name: 'Xóa chunk' }).click();
    await expect(page.getByText('Đã xóa chunk')).toBeVisible();
    await expect(page.getByText('Tổng: 19 chunks')).toBeVisible();

    // Scroll position must be preserved (not yanked back to the top).
    const after = await page.evaluate(() => window.scrollY);
    expect(after).toBeGreaterThan(400);
  });

  test('4. chunk pagination can navigate back to page 1', async ({ page }) => {
    const state: AdminState = { doc: buildDoc('chunked'), chunks: buildChunks(45) };
    await mockAdmin(page, state);
    await page.goto('/admin/documents/doc-1');

    await page.getByRole('tab', { name: 'Chunks' }).click();
    await expect(page.getByText('Trang 1/3')).toBeVisible();
    await expect(page.getByText('#0', { exact: true })).toBeVisible();

    // Forward to page 2, then page 3.
    await page.getByRole('button', { name: 'Sau' }).click();
    await expect(page.getByText('Trang 2/3')).toBeVisible();
    await expect(page.getByText('#20', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Sau' }).click();
    await expect(page.getByText('Trang 3/3')).toBeVisible();

    // Back to page 2, then page 1 — the regression was that page 1 never reloaded.
    await page.getByRole('button', { name: 'Trước' }).click();
    await expect(page.getByText('Trang 2/3')).toBeVisible();

    await page.getByRole('button', { name: 'Trước' }).click();
    await expect(page.getByText('Trang 1/3')).toBeVisible();
    await expect(page.getByText('#0', { exact: true })).toBeVisible();
    // Page-2's first chunk must no longer be on screen.
    await expect(page.getByText('#20', { exact: true })).toHaveCount(0);
  });
});
