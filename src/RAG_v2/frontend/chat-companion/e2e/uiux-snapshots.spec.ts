import { test } from '@playwright/test';
import { mockBackend, studentUser, adminUser } from './mocks';

test.describe('UI/UX Snapshots', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  const publicRoutes = [
    { path: '/', name: 'landing-page' },
    { path: '/login', name: 'login-page' },
    { path: '/register', name: 'register-page' },
    { path: '/404-not-found', name: 'not-found-page' },
  ];

  const studentRoutes = [
    { path: '/chat', name: 'student-chat' },
    { path: '/complete-profile', name: 'student-complete-profile' },
    { path: '/bookmarks', name: 'student-bookmarks' },
    { path: '/notifications', name: 'student-notifications' },
  ];

  const adminRoutes = [
    { path: '/admin', name: 'admin-dashboard' },
    { path: '/eval', name: 'admin-eval' },
    { path: '/admin/documents/1', name: 'admin-document-review' },
  ];

  for (const route of publicRoutes) {
    test(`Public Snapshot: ${route.name}`, async ({ page }) => {
      await mockBackend(page, { user: studentUser }); // Mock backend just in case
      await page.goto(route.path);
      // Wait for network idle or some element to ensure page is loaded
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: `ui-snapshots/${route.name}.png`, fullPage: true });
    });
  }

  for (const route of studentRoutes) {
    test(`Student Snapshot: ${route.name}`, async ({ page }) => {
      // For student, we must be logged in. RequireAuth hits /auth/refresh
      await mockBackend(page, { user: studentUser });
      await page.goto(route.path);
      await page.waitForLoadState('networkidle');
      // A small wait to allow animations to settle
      await page.waitForTimeout(500); 
      await page.screenshot({ path: `ui-snapshots/${route.name}.png`, fullPage: true });
    });
  }

  for (const route of adminRoutes) {
    test(`Admin Snapshot: ${route.name}`, async ({ page }) => {
      await mockBackend(page, { user: adminUser });
      await page.goto(route.path);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);
      await page.screenshot({ path: `ui-snapshots/${route.name}.png`, fullPage: true });
    });
  }
});
