import { test, expect, Page } from '@playwright/test';

/**
 * Regression test for a real concurrency bug found while manually exploring
 * the sidebar UX: starting a message from a brand-new chat (no session_id
 * yet) and then navigating away WHILE it streams used to leak that answer
 * (and the busy/Stop-button UI state) into whatever chat view you landed on
 * next — because `isCurrentRequest()` short-circuited to `true` forever for
 * any request that started as capturedSessionId === undefined.
 *
 * Repro, deliberately avoiding every confound hit while developing this test
 * (Mongo-persistence timing for RAG, chitchat turns never being persisted,
 * sidebar list staleTime making row selectors unreliable): fire a slow RAG
 * question from a brand-new chat (session B, no id yet), then immediately
 * click "New chat" AGAIN to land on a second, totally blank chat (session
 * C — never sent anything). Session C's empty/greeting view must stay
 * completely untouched by B's backgrounded stream.
 */

const login = async (page: Page) => {
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');
  await page.fill('#username', 'user2');
  await page.fill('#password', '12345678');
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => url.pathname.includes('/chat'), { timeout: 30_000 });
  await expect(page.locator('[aria-label="Nhập câu hỏi"]')).toBeVisible({ timeout: 15_000 });
};

test('leaving a new-chat request mid-stream does not leak into the next blank chat', async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);

  const input = page.locator('[aria-label="Nhập câu hỏi"]');
  const newChatBtn = page.getByRole('button', { name: 'Cuộc trò chuyện mới', exact: true });

  // 1. Session B: from a brand-new chat (no session id yet), fire a SLOW RAG
  // question — the CPU reranker takes ~55s+, giving a wide window to
  // navigate away while it's still retrieving/streaming in the background.
  await newChatBtn.click();
  await page.waitForURL((url) => url.pathname === '/chat');
  await input.fill('Điều kiện xét tốt nghiệp là gì?');
  await input.press('Enter');
  await page.waitForTimeout(1500); // let the request actually start (session frame received)

  // 2. Immediately land on a second, totally blank chat (session C).
  await newChatBtn.click();
  await page.waitForURL((url) => url.pathname === '/chat');
  await expect(page.getByText('Xin chào,', { exact: false })).toBeVisible({ timeout: 10_000 });

  // 3. Poll for ~50s: session C must stay a blank greeting screen — no bubble,
  // no fake Stop-button/typing-indicator bleeding in from B's background request.
  let leaked = false;
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(2500);
    const greetingStillShown = await page.getByText('Xin chào,', { exact: false }).isVisible();
    const anyBubble = await page.locator('.prose, .whitespace-pre-wrap').count();
    const stopVisible = await page
      .locator('button[aria-label="Dừng phản hồi"], button:has-text("Dừng")')
      .count();
    const stillOnBlankChat = page.url().endsWith('/chat');
    if (!greetingStillShown || anyBubble > 0 || stopVisible > 0 || !stillOnBlankChat) {
      leaked = true;
      console.log(
        `Leak detected at t+${(i + 1) * 2.5}s: greeting=${greetingStillShown} bubbles=${anyBubble} stop=${stopVisible} url=${page.url()}`,
      );
      break;
    }
  }

  expect(leaked, 'session B leaked into the blank session C view').toBe(false);
});
