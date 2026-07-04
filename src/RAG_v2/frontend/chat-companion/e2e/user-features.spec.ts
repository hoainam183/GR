import { test, expect, Page } from '@playwright/test';

/**
 * REAL-backend E2E covering the remaining user-facing UX surface: sidebar
 * rename/switch-session, bookmarks, notifications, theme toggle, and the
 * feedback thumbs toggle-off fix. Requires the RAG backend (:8000) + Vite dev
 * server (:8080) with a seeded student user (user2 / 12345678).
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

test.describe.serial('User-facing UX (real backend)', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test('Sidebar: new chat, rename, switch session, delete', async ({ page }) => {
    test.setTimeout(240_000);
    await login(page);

    // New chat
    await page.getByRole('button', { name: 'Cuộc trò chuyện mới', exact: true }).click();
    await page.waitForURL((url) => url.pathname === '/chat');

    // Use RAG-routed questions (not chitchat) — chitchat turns are never
    // persisted to Mongo by design, and separately, the app currently loses
    // a chitchat-only session's displayed content once you navigate away and
    // back (its only client-side record is eagerly cleared on completion).
    // That's a real, independently-reported gap — avoid it here so this test
    // verifies rename/switch itself, not that unrelated gap.
    const uniqueTagA = `sidebar-A-${Date.now()}`;
    const input = page.locator('[aria-label="Nhập câu hỏi"]');
    await input.fill(`Học bổng KKHT là gì? (${uniqueTagA})`);
    await input.press('Enter');
    await page.waitForURL((url) => /\/chat\/.+/.test(url.pathname), { timeout: 20_000 });
    await expect(page.locator('.prose').last()).toBeVisible({ timeout: 150_000 });

    // Reload so the sidebar's sessions query (30s staleTime) is guaranteed to
    // refetch fresh and include + highlight the session we just created —
    // relying on invalidateQueries' background refetch alone was flaky here.
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    const optionsBtn = page.locator('.conversation-item.bg-sidebar-accent [aria-label="Tuỳ chọn cuộc trò chuyện"]');
    await expect(optionsBtn).toBeVisible({ timeout: 20_000 });

    // ── Rename ──────────────────────────────────────────────────────────
    await optionsBtn.click();
    await page.getByText('Đổi tên', { exact: true }).click();
    const renameInput = page.locator('input[placeholder="Cuộc trò chuyện mới"]');
    await expect(renameInput).toBeVisible();
    const newTitle = `E2E test ${Date.now()}`;
    await renameInput.fill(newTitle);
    await renameInput.press('Enter');
    await expect(page.getByText(newTitle, { exact: true }).first()).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: 'ui-snapshots-real/sidebar-renamed.png' });

    // ── Switch session ──────────────────────────────────────────────────
    // Start a second chat, then switch back to the renamed one via the sidebar.
    const firstUrl = page.url();
    await page.getByRole('button', { name: 'Cuộc trò chuyện mới', exact: true }).click();
    await page.waitForURL((url) => url.pathname === '/chat');
    await expect(input).toBeVisible();
    await input.fill('Lịch thi giữa kỳ khi nào?');
    await input.press('Enter');
    await page.waitForURL((url) => /\/chat\/.+/.test(url.pathname) && page.url() !== firstUrl, {
      timeout: 20_000,
    });
    const secondUrl = page.url();
    expect(secondUrl).not.toBe(firstUrl);

    await page.locator('.conversation-item').getByText(newTitle, { exact: true }).click();
    await page.waitForURL(firstUrl, { timeout: 10_000 });
    await expect(page.getByText(uniqueTagA, { exact: false }).first()).toBeVisible({ timeout: 10_000 });

    // ── Delete the second session (cleanup) ─────────────────────────────
    await page.goto(secondUrl);
    await page.waitForLoadState('domcontentloaded');
    // Find the row belonging to the second session (the currently active one).
    await expect(
      page.locator('.conversation-item.bg-sidebar-accent [aria-label="Tuỳ chọn cuộc trò chuyện"]'),
    ).toBeVisible({ timeout: 20_000 });
    await page.locator('.conversation-item.bg-sidebar-accent [aria-label="Tuỳ chọn cuộc trò chuyện"]').click();
    await page.getByText('Xoá', { exact: true }).click();
    await page.getByRole('button', { name: 'Xoá cuộc trò chuyện?' }).isVisible().catch(() => {});
    await page.getByRole('alertdialog').getByRole('button', { name: 'Xoá' }).click();
    await page.waitForURL((url) => url.pathname === '/chat', { timeout: 10_000 });
  });

  test('Feedback thumbs: toggle up, toggle off persists after reload (bug fix)', async ({ page }) => {
    test.setTimeout(180_000);
    await login(page);

    // Must be a RAG-routed question — the feedback row only renders once the
    // turn has a turn_id, and chitchat turns are never persisted to Mongo
    // (by design), so they never get one.
    const input = page.locator('[aria-label="Nhập câu hỏi"]');
    await input.fill('Điều kiện tốt nghiệp là gì?');
    await input.press('Enter');

    const thumbsUp = page.locator('button[title="Hữu ích"]').last();
    await expect(thumbsUp).toBeVisible({ timeout: 150_000 });

    await thumbsUp.click();
    await expect(page.locator('.text-emerald-600').last()).toBeVisible({ timeout: 5_000 });
    await page.screenshot({ path: 'ui-snapshots-real/feedback-up.png' });

    // Toggle off.
    await thumbsUp.click();
    await page.waitForTimeout(500); // allow the DELETE /feedback call to land

    // Reload — with the bug, GET /feedback would resurrect "up".
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('[aria-label="Nhập câu hỏi"]')).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(1500); // let the mount-time getFeedback() resolve

    const thumbsUpAfterReload = page.locator('button[title="Hữu ích"]').last();
    await expect(thumbsUpAfterReload).toBeVisible();
    const cls = await thumbsUpAfterReload.getAttribute('class');
    expect(cls, 'thumbs-up should NOT be selected after toggle-off + reload').not.toContain('emerald');
  });

  test('Bookmark: save from chat, appears on /bookmarks, jump back, remove', async ({ page }) => {
    test.setTimeout(180_000);
    await login(page);

    // Same turn_id requirement as feedback — must be RAG-routed, not chitchat.
    const input = page.locator('[aria-label="Nhập câu hỏi"]');
    await input.fill('Học phí kỳ này là bao nhiêu?');
    await input.press('Enter');

    const bookmarkBtn = page.locator('button[title="Lưu"]').last();
    await expect(bookmarkBtn).toBeVisible({ timeout: 150_000 });
    await bookmarkBtn.click();
    await expect(page.locator('button[title="Bỏ lưu"]').last()).toBeVisible({ timeout: 5_000 });

    const chatUrl = page.url();

    // Navigate to Bookmarks page via the header shortcut.
    await page.locator('[aria-label="Câu trả lời đã lưu"]').click();
    await page.waitForURL((url) => url.pathname === '/bookmarks');
    await expect(page.getByText('Đã lưu', { exact: false }).first()).toBeVisible();
    await page.screenshot({ path: 'ui-snapshots-real/bookmarks-page.png', fullPage: true });

    // Jump back to the source chat.
    await page.locator('button[title="Xem cuộc trò chuyện gốc"]').first().click();
    await page.waitForURL(chatUrl, { timeout: 10_000 });

    // Remove the bookmark from the chat bubble to leave things clean.
    await page.locator('button[title="Bỏ lưu"]').last().click();
    await expect(page.locator('button[title="Lưu"]').last()).toBeVisible({ timeout: 5_000 });
  });

  test('Notifications: bell dropdown opens, navigates to /notifications', async ({ page }) => {
    test.setTimeout(30_000);
    await login(page);

    const bell = page.locator('[aria-label="Thông báo"]');
    await expect(bell).toBeVisible();
    await bell.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'ui-snapshots-real/notifications-dropdown.png' });

    await page.getByRole('button', { name: 'Xem tất cả thông báo' }).click();
    await page.waitForURL((url) => url.pathname === '/notifications');
    await expect(page.getByRole('button', { name: 'Quay lại' })).toBeVisible();
    await page.screenshot({ path: 'ui-snapshots-real/notifications-page.png', fullPage: true });
  });

  test('Theme toggle: dark mode persists across navigation and reload', async ({ page }) => {
    test.setTimeout(30_000);
    await login(page);

    const themeBtn = page.locator('button[title="Chế độ tối"], button[title="Chế độ sáng"]');
    await expect(themeBtn).toBeVisible();
    const wasDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));

    await themeBtn.click();
    await page.waitForTimeout(200);
    const isDarkNow = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    expect(isDarkNow).toBe(!wasDark);

    // Persists across client-side navigation to another page.
    await page.locator('[aria-label="Câu trả lời đã lưu"]').click();
    await page.waitForURL((url) => url.pathname === '/bookmarks');
    expect(await page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(isDarkNow);

    // Persists across a hard reload.
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    expect(await page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(isDarkNow);

    // Restore original theme so repeated runs are idempotent.
    await page.goto('/chat');
    await page.locator('button[title="Chế độ tối"], button[title="Chế độ sáng"]').click();
  });
});
