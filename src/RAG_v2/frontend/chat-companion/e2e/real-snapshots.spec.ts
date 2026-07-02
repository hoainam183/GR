import { test, expect } from '@playwright/test';

test.describe('Real API UI/UX Snapshots', () => {
  test.use({ viewport: { width: 1280, height: 800 } });
  test.setTimeout(180000); // 3 minutes

  test('Public Pages Snapshots', async ({ page }) => {
    // 1. Snapshot Public Pages
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'ui-snapshots-real/landing-page.png', fullPage: true });

    await page.goto('/404-not-found');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'ui-snapshots-real/not-found-page.png', fullPage: true });

    await page.goto('/register');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'ui-snapshots-real/register-page.png', fullPage: true });
  });

  test('Student (user2) Snapshots', async ({ page }) => {
    // 2. Login
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'ui-snapshots-real/login-page-before.png', fullPage: true });

    await page.fill('#username', 'user2');
    await page.fill('#password', '12345678');
    await page.screenshot({ path: 'ui-snapshots-real/login-page-filled.png', fullPage: true });

    await page.click('button[type="submit"]');
    
    // Wait for navigation after login
    await page.waitForURL(url => url.pathname.includes('/chat') || url.pathname.includes('/admin'));
    await page.waitForLoadState('domcontentloaded');
    // Important: Wait long enough for actual backend data to load into UI
    await page.waitForTimeout(6000); 

    // 3. Snapshot Student Pages
    const studentRoutes = [
      { path: '/chat', name: 'student-chat' },
      { path: '/complete-profile', name: 'student-complete-profile' },
      { path: '/bookmarks', name: 'student-bookmarks' },
      { path: '/notifications', name: 'student-notifications' },
    ];

    for (const route of studentRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      // Wait for React Query to fetch and render
      await page.waitForTimeout(5000);

      // If we are on chat page, send a message to ensure there is "đầy đủ data"
      if (route.path === '/chat') {
        const chatInput = page.getByLabel('Nhập câu hỏi');
        if (await chatInput.isVisible()) {
          await chatInput.fill('Học bổng KKHT là gì?');
          await page.getByRole('button', { name: 'Gửi tin nhắn' }).click();
          // Wait for AI to finish responding
          await page.waitForTimeout(15000); 
        }
      }

      await page.screenshot({ path: `ui-snapshots-real/${route.name}.png`, fullPage: true });
    }
  });

  test('Admin Snapshots', async ({ page }) => {
    // 2. Login
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    await page.fill('#username', 'admin');
    await page.fill('#password', '12345678');
    await page.click('button[type="submit"]');
    
    // Wait for navigation
    await page.waitForURL(url => url.pathname.includes('/chat') || url.pathname.includes('/admin'));
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(6000); // give it time to load data from real backend

    // 4. Snapshot Admin Pages
    const adminRoutes = [
      { path: '/admin', name: 'admin-dashboard' },
      { path: '/eval', name: 'admin-eval' },
      { path: '/admin/documents/1', name: 'admin-document-review' },
    ];

    for (const route of adminRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      // Wait for React Query / backend to fetch data
      await page.waitForTimeout(5000);
      await page.screenshot({ path: `ui-snapshots-real/${route.name}.png`, fullPage: true });
    }
  });
});
