import { test, expect } from '@playwright/test';
import { gotoChat, studentUser, adminUser } from './mocks';

type PW = import('@playwright/test').Page;

const sendButton = (page: PW) => page.getByRole('button', { name: 'Gửi tin nhắn' });
const chatBox = (page: PW) => page.getByRole('textbox', { name: 'Nhập câu hỏi' });

// Conversation text lives inside the markdown `.prose` bubble — scoping here
// avoids matching the admin debug JSON <pre>, which echoes the same strings.
const inBubble = (page: PW, text: string | RegExp) =>
  page.locator('.prose').getByText(text).first();

const ask = async (page: PW, text: string) => {
  const box = chatBox(page);
  await box.click();
  await box.fill(text);
  await sendButton(page).click();
};

test.describe('Empty state (DESIGN §6 welcome + §5.5 disclaimer)', () => {
  test('greets the student, shows suggestion cards and the AI disclaimer', async ({ page }) => {
    await gotoChat(page);

    await expect(page.getByText('Xin chào, An!')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Quy chế đào tạo' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Chính sách học bổng/ })).toBeVisible();
    await expect(
      page.getByText(/Thông tin do AI tổng hợp từ tài liệu, quy chế/),
    ).toBeVisible();
  });

  test('send button is disabled until the user types', async ({ page }) => {
    await gotoChat(page);
    await expect(sendButton(page)).toBeDisabled();
    await chatBox(page).fill('Điều kiện tốt nghiệp?');
    await expect(sendButton(page)).toBeEnabled();
  });
});

test.describe('Send + streaming render', () => {
  test('user question echoes and the streamed answer renders', async ({ page }) => {
    await gotoChat(page);
    await ask(page, 'Điều kiện tốt nghiệp là gì?');

    await expect(inBubble(page, 'Điều kiện tốt nghiệp là gì?')).toBeVisible();
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();
  });

  test('contextual follow-up chips appear after an answer (DESIGN §5.3)', async ({ page }) => {
    await gotoChat(page);
    await ask(page, 'Điều kiện tốt nghiệp?');
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();

    await expect(page.getByRole('button', { name: 'Lịch thi cuối kỳ' })).toBeVisible();
    await page.getByRole('button', { name: 'Học bổng KKHT' }).click();
    await expect(inBubble(page, 'Học bổng KKHT')).toBeVisible();
  });
});

test.describe('Citations (DESIGN §5.2) — student view is clean', () => {
  test('shows friendly citation cards with locator + source link, no debug', async ({ page }) => {
    await gotoChat(page, { user: studentUser });
    await ask(page, 'Điều kiện tốt nghiệp?');
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();

    // No developer debug leaks to students.
    await expect(page.getByText('Debug runtime info')).toHaveCount(0);
    await expect(page.getByText('Collection Ranking')).toHaveCount(0);

    await page.getByRole('button', { name: /Xem nguồn \(2\)/ }).click();
    await expect(page.getByText('Nguồn tham khảo')).toBeVisible();
    await expect(page.getByText('QD_quy-che-dao-tao-DH_2023.pdf')).toBeVisible();
    await expect(page.getByText('Điều 14, tr. 12')).toBeVisible();
    await expect(page.getByRole('link', { name: /Xem tài liệu gốc/ }).first()).toBeVisible();
  });
});

test.describe('Admin still sees debug instrumentation', () => {
  test('admin gets the debug panel and runtime info', async ({ page }) => {
    await gotoChat(page, { user: adminUser });
    await ask(page, 'Điều kiện tốt nghiệp?');
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();

    await expect(page.getByText('Collection Ranking').first()).toBeVisible();
    await expect(page.getByText('Debug runtime info')).toBeVisible();
  });
});

test.describe('Feedback (DESIGN §5.7)', () => {
  test('thumbs up records feedback with a confirmation toast', async ({ page }) => {
    await gotoChat(page);
    await ask(page, 'Điều kiện tốt nghiệp?');
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();

    await page.getByRole('button', { name: 'Hữu ích' }).click();
    await expect(page.getByText('Cảm ơn bạn đã đánh giá!')).toBeVisible();
  });

  test('thumbs down opens the reason picker', async ({ page }) => {
    await gotoChat(page);
    await ask(page, 'Điều kiện tốt nghiệp?');
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();

    await page.getByRole('button', { name: 'Chưa tốt' }).click();
    await expect(page.getByText('Sai thông tin')).toBeVisible();
    await expect(page.getByText('Thông tin cũ')).toBeVisible();
  });
});

test.describe('Error handling + retry (DESIGN §5.6)', () => {
  test('failed send shows an error bubble and "Thử lại" recovers', async ({ page }) => {
    await gotoChat(page, { failStream: true });
    await ask(page, 'Điều kiện tốt nghiệp?');

    await expect(page.getByText(/Không gửi được tin nhắn/)).toBeVisible();
    const retry = page.getByRole('button', { name: 'Thử lại' });
    await expect(retry).toBeVisible();

    await retry.click();
    await expect(inBubble(page, /được xét tốt nghiệp/)).toBeVisible();
    await expect(page.getByText(/Không gửi được tin nhắn/)).toHaveCount(0);
  });
});

test.describe('Theme toggle (DESIGN §2 dark mode)', () => {
  test('toggling flips the dark class on <html>', async ({ page }) => {
    await gotoChat(page);
    const toggle = page.getByRole('button', { name: /Chuyển sang chế độ/ });
    const before = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    await toggle.click();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.classList.contains('dark')))
      .toBe(!before);
  });
});
