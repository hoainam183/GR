/**
 * UI/UX AUDIT spec (screenshot-only). Reuses e2e/mocks.ts.
 * Runs on both `desktop` and `mobile` projects. Captures full-page screenshots
 * of every screen/state into the scratchpad so they can be reviewed for
 * layout/contrast/clipping/state bugs. Assertions are intentionally light —
 * the screenshots are the evidence; we don't want false test failures.
 */
import { test, expect, type Page, type TestInfo } from '@playwright/test';
import { mockBackend, gotoChat, studentUser, adminUser, API } from './mocks';

const OUT = 'C:/Users/LENOVO/AppData/Local/Temp/claude/D--GR/168e9a5c-a808-4888-8a1b-d4ecbbc8bee8/scratchpad/shots/web';

async function shot(page: Page, info: TestInfo, name: string) {
  const proj = info.project.name;
  await page.waitForTimeout(450); // let animations/streaming settle
  await page.screenshot({ path: `${OUT}/${proj}__${name}.png`, fullPage: true });
}

/** Force /auth/refresh to 401 so public auth screens actually render (not redirect to /chat). */
async function loggedOut(page: Page) {
  await mockBackend(page);
  await page.route(`${API}/auth/refresh`, (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'no session' }) }),
  );
}

const chatBox = (p: Page) => p.getByRole('textbox', { name: 'Nhập câu hỏi' });
const sendBtn = (p: Page) => p.getByRole('button', { name: 'Gửi tin nhắn' });
const ask = async (p: Page, t: string) => {
  await chatBox(p).click();
  await chatBox(p).fill(t);
  await sendBtn(p).click();
};

// ---------------- Public / auth screens ----------------
test('landing page', async ({ page }, info) => {
  await loggedOut(page);
  await page.goto('/');
  await shot(page, info, '01-landing');
});

test('login page', async ({ page }, info) => {
  await loggedOut(page);
  await page.goto('/login');
  await shot(page, info, '02-login');
});

test('register page', async ({ page }, info) => {
  await loggedOut(page);
  await page.goto('/register');
  await shot(page, info, '03-register');
});

test('complete-profile page', async ({ page }, info) => {
  await mockBackend(page, { user: { ...studentUser, is_profile_complete: false } });
  await page.goto('/complete-profile');
  await shot(page, info, '04-complete-profile');
});

// ---------------- Chat ----------------
test('chat empty state', async ({ page }, info) => {
  await gotoChat(page);
  await expect(page.getByText(/Xin chào/)).toBeVisible();
  await shot(page, info, '10-chat-empty');
});

test('chat answer + sources', async ({ page }, info) => {
  await gotoChat(page, { user: studentUser });
  await ask(page, 'Điều kiện tốt nghiệp là gì?');
  await expect(page.locator('.prose').getByText(/được xét tốt nghiệp/).first()).toBeVisible();
  await shot(page, info, '11-chat-answer');
  // expand source cards
  const src = page.getByRole('button', { name: /Xem nguồn/ });
  if (await src.count()) {
    await src.first().click();
    await shot(page, info, '12-chat-sources-open');
  }
});

test('chat thumbs-down reason picker', async ({ page }, info) => {
  await gotoChat(page);
  await ask(page, 'Điều kiện tốt nghiệp?');
  await expect(page.locator('.prose').getByText(/được xét tốt nghiệp/).first()).toBeVisible();
  await page.getByRole('button', { name: 'Chưa tốt' }).click();
  await shot(page, info, '13-chat-feedback-down');
});

test('chat error + retry', async ({ page }, info) => {
  await gotoChat(page, { failStream: true });
  await ask(page, 'Điều kiện tốt nghiệp?');
  await expect(page.getByText(/Không gửi được tin nhắn/)).toBeVisible();
  await shot(page, info, '14-chat-error');
});

test('chat admin debug view', async ({ page }, info) => {
  await gotoChat(page, { user: adminUser });
  await ask(page, 'Điều kiện tốt nghiệp?');
  await expect(page.locator('.prose').getByText(/được xét tốt nghiệp/).first()).toBeVisible();
  await shot(page, info, '15-chat-admin-debug');
});

test('chat dark mode', async ({ page }, info) => {
  await gotoChat(page);
  await ask(page, 'Điều kiện tốt nghiệp?');
  await expect(page.locator('.prose').getByText(/được xét tốt nghiệp/).first()).toBeVisible();
  const toggle = page.getByRole('button', { name: /Chuyển sang chế độ/ });
  if (await toggle.count()) await toggle.first().click();
  await shot(page, info, '16-chat-dark');
});

// ---------------- Sidebar / history ----------------
test('sidebar with sessions', async ({ page }, info) => {
  await gotoChat(page, {
    sessions: [
      { session_id: 's1', title: 'Điều kiện tốt nghiệp và xét học bổng khuyến khích học tập kỳ này', turn_count: 4 },
      { session_id: 's2', title: 'Lịch thi cuối kỳ 20242', turn_count: 2 },
      { session_id: 's3', title: null, turn_count: 1 },
    ],
  });
  // On mobile the sidebar is behind a button; try to open it.
  const open = page.getByRole('button', { name: /Mở sidebar|sidebar/i });
  if (info.project.name === 'mobile' && (await open.count())) await open.first().click();
  await shot(page, info, '20-sidebar-sessions');
});

// ---------------- Bookmarks / notifications ----------------
test('bookmarks page', async ({ page }, info) => {
  await mockBackend(page);
  await page.goto('/bookmarks');
  await shot(page, info, '30-bookmarks');
});

test('notifications page', async ({ page }, info) => {
  await mockBackend(page);
  await page.goto('/notifications');
  await shot(page, info, '31-notifications');
});

// ---------------- Admin ----------------
test('admin dashboard', async ({ page }, info) => {
  await mockBackend(page, { user: adminUser });
  await page.goto('/admin');
  await shot(page, info, '40-admin');
});
