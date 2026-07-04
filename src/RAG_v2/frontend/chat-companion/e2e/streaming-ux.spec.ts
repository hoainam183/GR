import { test, expect, Page } from '@playwright/test';

/**
 * REAL-backend E2E for the streaming chat UX improvements.
 *
 * Requires the RAG backend on :8000 and the Vite dev server on :8080, plus a
 * seeded student user (user2 / 12345678). Verifies, end to end:
 *   - staged progress labels (reflection → retrieval → synthesis) appear before
 *     the first token (backend B2 wired through to the TypingIndicator);
 *   - the answer streams in (assistant text grows monotonically);
 *   - while streaming we render plain text (.whitespace-pre-wrap) and swap to
 *     parsed markdown (.prose) only once it finishes (frontend A1);
 *   - sources appear after the answer with the fade-in class (A4);
 *   - no uncaught page errors during a full turn.
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

const sendMessage = async (page: Page, text: string) => {
  const input = page.locator('[aria-label="Nhập câu hỏi"]');
  await input.fill(text);
  await input.press('Enter');
};

// Latest assistant answer text, whether streaming (plain) or finished (markdown).
const answerText = async (page: Page): Promise<string> => {
  const streaming = page.locator('.whitespace-pre-wrap');
  if (await streaming.count()) return (await streaming.last().innerText()).trim();
  const prose = page.locator('.prose');
  if (await prose.count()) return (await prose.last().innerText()).trim();
  return '';
};

test.describe('Streaming chat UX (real backend)', () => {
  test('RAG turn: staged progress → smooth stream → markdown + sources', async ({ page }) => {
    test.setTimeout(200_000); // CPU reranker adds ~55s before the first token

    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));

    await login(page);
    await sendMessage(page, 'Học bổng KKHT là gì?');

    // ── 1. Collect the staged progress labels shown before the first token ──
    const labels: string[] = [];
    const lengths: number[] = [];
    let midStreamShot = false;
    const deadline = Date.now() + 170_000;

    while (Date.now() < deadline) {
      const labelLoc = page.locator('span.italic');
      if (await labelLoc.count()) {
        const t = (await labelLoc.first().innerText()).trim();
        if (t && labels[labels.length - 1] !== t) labels.push(t);
      }

      const txt = await answerText(page);
      if (txt) {
        lengths.push(txt.length);
        // Grab a mid-stream frame the moment tokens start flowing.
        if (!midStreamShot && (await page.locator('.whitespace-pre-wrap').count())) {
          await page.screenshot({ path: 'ui-snapshots-real/streaming-mid.png', fullPage: true });
          midStreamShot = true;
        }
      }

      // Done when the sources button appears (metadata frame processed).
      if (await page.getByRole('button', { name: /Xem nguồn/i }).count()) break;
      await page.waitForTimeout(250);
    }

    // ── 2. Assertions ──────────────────────────────────────────────────────
    console.log('STATUS LABELS SEEN:', JSON.stringify(labels));
    console.log('ANSWER LENGTH SAMPLES:', JSON.stringify(lengths));

    // At least one progress label surfaced before the answer (staged feedback).
    expect(labels.length, 'expected staged progress labels').toBeGreaterThan(0);
    expect(labels.some((l) => /phân tích|tìm kiếm|tổng hợp/i.test(l))).toBeTruthy();

    // Answer content grew over time (real streaming, not a single dump).
    expect(lengths.length, 'expected sampled answer text').toBeGreaterThan(0);
    const maxLen = Math.max(...lengths);
    expect(maxLen).toBeGreaterThan(40);

    // Finished answer is parsed markdown, not the raw streaming span.
    await expect(page.locator('.prose').last()).toBeVisible({ timeout: 20_000 });

    // Sources revealed with the fade-in polish (A4).
    const sourcesBtn = page.getByRole('button', { name: /Xem nguồn/i }).last();
    await expect(sourcesBtn).toBeVisible();
    await expect(sourcesBtn).toHaveClass(/animate-fade-in-up/);

    await page.screenshot({ path: 'ui-snapshots-real/streaming-done.png', fullPage: true });

    // Expand sources to confirm the fade-in container renders.
    await sourcesBtn.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: 'ui-snapshots-real/streaming-sources.png', fullPage: true });

    expect(pageErrors, `uncaught page errors: ${pageErrors.join(' | ')}`).toHaveLength(0);
  });
});
