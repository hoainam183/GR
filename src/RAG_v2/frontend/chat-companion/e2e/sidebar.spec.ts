import { test, expect } from '@playwright/test';
import { gotoChat } from './mocks';

test.describe('Conversation sidebar (DESIGN §4 layout)', () => {
  test('desktop shows the sidebar inline; mobile opens it as a sheet', async ({ page }, testInfo) => {
    await gotoChat(page);

    const newChat = page.getByRole('button', { name: 'Cuộc trò chuyện mới' });

    if (testInfo.project.name === 'mobile') {
      // Hidden behind the menu button until opened (mobile-first, DESIGN §4.1).
      await expect(newChat).toHaveCount(0);
      await page.getByRole('button', { name: 'Mở sidebar' }).click();
      await expect(newChat).toBeVisible();
    } else {
      // Always-visible resizable panel on desktop (DESIGN §4.2).
      await expect(newChat).toBeVisible();
    }
  });
});
