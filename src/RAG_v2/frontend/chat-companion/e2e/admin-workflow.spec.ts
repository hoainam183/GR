import fs from 'node:fs';
import { test, expect, type Page } from '@playwright/test';

/**
 * Real E2E — admin upload / crawl / index workflow.
 *
 * Unlike the other specs in this folder, this one does NOT mock the backend.
 * It drives the actual FastAPI backend on :8000 (real Mongo/Qdrant/ES/Redis),
 * logging in as the seeded `admin` account, to evaluate the admin console's
 * UI/UX for document upload, exam-schedule upload, and the crawler
 * review/index workflow end to end.
 *
 * Requires: backend running on :8000 with the `admin` / `12345678` account.
 *
 * All interactive actions pass an explicit bounded `timeout` — Playwright
 * actions otherwise inherit the *test* timeout (10 min here) as their
 * ceiling, so a bad selector hangs for the full 10 minutes instead of
 * failing fast.
 */

/** Build a minimal valid one-page PDF in-memory — avoids committing a binary
 * fixture that the repo's blanket `*.pdf` .gitignore rule would drop. */
function buildMinimalPdf(text: string): Buffer {
  const objects: (string | null)[] = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    null, // stream object, built below
  ];
  const stream = Buffer.from(`BT /F1 12 Tf 50 700 Td (${text}) Tj ET`, 'latin1');

  const chunks: Buffer[] = [Buffer.from('%PDF-1.4\n', 'latin1')];
  let offset = chunks[0].length;
  const offsets: number[] = [];
  objects.forEach((obj, i) => {
    offsets.push(offset);
    const n = i + 1;
    let buf: Buffer;
    if (obj === null) {
      buf = Buffer.concat([
        Buffer.from(`${n} 0 obj\n<< /Length ${stream.length} >>\nstream\n`, 'latin1'),
        stream,
        Buffer.from('\nendstream\nendobj\n', 'latin1'),
      ]);
    } else {
      buf = Buffer.from(`${n} 0 obj\n${obj}\nendobj\n`, 'latin1');
    }
    chunks.push(buf);
    offset += buf.length;
  });

  const xrefOffset = offset;
  const n = objects.length + 1;
  let xref = `xref\n0 ${n}\n0000000000 65535 f \n`;
  for (const off of offsets) xref += `${off.toString().padStart(10, '0')} 00000 n \n`;
  chunks.push(Buffer.from(xref, 'latin1'));
  chunks.push(Buffer.from(`trailer\n<< /Size ${n} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`, 'latin1'));

  return Buffer.concat(chunks);
}

const SAMPLE_PDF_BYTES = buildMinimalPdf(
  'E2E admin upload test document. Dieu 1. Day la noi dung thu nghiem cho kiem thu upload tai lieu admin.',
);
// Unique per run so reruns never collide with a leftover doc from a prior
// failed attempt (the DocumentList row locator matches on filename).
const SAMPLE_PDF_NAME = `admin-sample-${Date.now()}.pdf`;
const SNAP_DIR = 'ui-snapshots-real/admin-workflow';
const ACT_TIMEOUT = 5_000;

// NOTE: Radix Select triggers render role="combobox" but the visible <Label>
// is never wired to them via htmlFor/id, and ARIA forbids deriving a
// combobox's accessible name from its content — so getByRole('combobox',
// {name}) cannot find them (a real a11y bug, tracked separately). Match on
// the trigger's visible text via a plain DOM selector instead.
async function selectRadixOption(page: Page, triggerText: string, optionName: RegExp | string) {
  await page.locator('[role="combobox"]', { hasText: triggerText }).first().click({ timeout: ACT_TIMEOUT });
  await page.getByRole('option', { name: optionName }).click({ timeout: ACT_TIMEOUT });
}

async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');
  await page.fill('#username', 'admin', { timeout: ACT_TIMEOUT });
  await page.fill('#password', '12345678', { timeout: ACT_TIMEOUT });
  await page.click('button[type="submit"]', { timeout: ACT_TIMEOUT });
  await page.waitForURL((url) => url.pathname.includes('/admin') || url.pathname.includes('/chat'), {
    timeout: 15_000,
  });
  if (!page.url().includes('/admin')) {
    await page.goto('/admin');
  }
  await page.waitForLoadState('domcontentloaded');
}

test.describe.serial('Admin real-backend workflow', () => {
  test.setTimeout(10 * 60 * 1000);
  test.use({ viewport: { width: 1440, height: 900 } });

  test('Document upload — invalid file rejected, valid PDF uploaded, pipeline tracked, then deleted', async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByRole('tab', { name: 'Tài liệu' }).click({ timeout: ACT_TIMEOUT });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SNAP_DIR}/01-documents-tab-empty-state.png`, fullPage: true });

    // --- Reject an unsupported file type ---
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: 'not-a-doc.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('plain text, should be rejected'),
    });
    await expect(page.getByText(/chỉ hỗ trợ/i)).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: `${SNAP_DIR}/02-invalid-file-rejected.png`, fullPage: true });

    // --- Upload a valid PDF without selecting a collection first ---
    await fileInput.setInputFiles({
      name: SAMPLE_PDF_NAME,
      mimeType: 'application/pdf',
      buffer: SAMPLE_PDF_BYTES,
    });
    await page.screenshot({ path: `${SNAP_DIR}/03-file-selected.png`, fullPage: true });
    const uploadButton = page.getByRole('button', { name: /^Upload$/ });
    await uploadButton.click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Vui lòng chọn collection/i)).toBeVisible({ timeout: 5000 });

    // --- Now pick a collection and upload for real ---
    await selectRadixOption(page, 'Chọn collection', /^test$/);
    await page.screenshot({ path: `${SNAP_DIR}/04-collection-selected.png`, fullPage: true });

    await uploadButton.click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Đã upload 1 file thành công/i)).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: `${SNAP_DIR}/05-upload-success-toast.png`, fullPage: true });

    // --- Document should now appear in the list ---
    const row = page.locator('tr', { hasText: SAMPLE_PDF_NAME });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SNAP_DIR}/06-document-in-list.png`, fullPage: true });

    // FINDING: uploading only ever creates a record in the "uploaded" status —
    // no background task is launched (api/routes/upload.py's upload_documents
    // handler just writes the Mongo doc). "uploaded" is also NOT in
    // PROCESSING_STATUSES (lib/pipelineNotify.ts), so the list's 5s auto-poll
    // never engages either. The uploader's own copy ("File sẽ đi qua pipeline
    // convert → clean → chunk → embed...") implies this happens automatically;
    // it does not. Confirm that stays true after a real wait, then drive the
    // pipeline the way an admin actually has to: open the detail page.
    await page.waitForTimeout(8_000);
    await expect(row.getByText('Đã upload')).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: `${SNAP_DIR}/07-still-stuck-at-uploaded.png`, fullPage: true });

    // --- Open the detail/review page and run the pipeline manually ---
    await row.getByTitle('Xem chi tiết').click({ timeout: ACT_TIMEOUT });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SNAP_DIR}/08-document-detail-uploaded.png`, fullPage: true });

    await page.getByRole('button', { name: /Tự động/ }).click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Pipeline tự động đã bắt đầu/i)).toBeVisible({ timeout: 10_000 });
    // "Tự động" deliberately stops at "chunked" — indexing needs an explicit
    // human chunk-approval gate (pipeline/document_pipeline.py run_full_pipeline).
    // The header badge shows the raw status string (see DocumentReview.tsx).
    await expect(page.getByText('chunked', { exact: true })).toBeVisible({ timeout: 3 * 60 * 1000 });
    await page.screenshot({ path: `${SNAP_DIR}/09-auto-pipeline-reached-chunked.png`, fullPage: true });

    // --- Review + approve chunks, then index ---
    await page.getByRole('tab', { name: 'Chunks' }).click({ timeout: ACT_TIMEOUT });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SNAP_DIR}/10-chunks-tab.png`, fullPage: true });

    await page.getByRole('button', { name: /Duyệt chunks/ }).click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Đã duyệt chunks/i)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SNAP_DIR}/11-chunks-approved.png`, fullPage: true });

    await page.getByRole('button', { name: /Bước tiếp/ }).click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Đã index xong|Index thất bại/i).first()).toBeVisible({ timeout: 3 * 60 * 1000 });
    await page.screenshot({ path: `${SNAP_DIR}/12-indexed.png`, fullPage: true });

    // --- Back to list, delete the test document ---
    await page.goto('/admin');
    await page.getByRole('tab', { name: 'Tài liệu' }).click({ timeout: ACT_TIMEOUT });
    await page.waitForTimeout(500);
    page.once('dialog', (dialog) => dialog.accept());
    await row.getByTitle('Xóa').click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Đã xóa tài liệu/i)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SNAP_DIR}/13-after-delete.png`, fullPage: true });
  });

  test('Exam schedule upload — parse report, DB status panel', async ({ page }) => {
    // Needs a real lịch-thi PDF with actual exam rows to parse — the repo's
    // blanket `*.pdf` .gitignore rule means this local data file isn't
    // guaranteed to exist on every checkout, so skip gracefully rather than
    // hard-failing for anyone without it.
    const examPdf = 'D:/GR/src/RAG_v2/data/lichthi/LTGK-CK 20252A-AB-28042026.pdf';
    test.skip(!fs.existsSync(examPdf), `Fixture not present locally: ${examPdf}`);

    await loginAsAdmin(page);
    await page.getByRole('tab', { name: 'Tài liệu' }).click({ timeout: ACT_TIMEOUT });
    await page.waitForTimeout(500);

    // Switch to "Lịch thi" kind
    await selectRadixOption(page, 'Tài liệu thường', /^Lịch thi$/);
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SNAP_DIR}/10-exam-schedule-kind.png`, fullPage: true });

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(examPdf);
    await page.screenshot({ path: `${SNAP_DIR}/11-exam-file-selected.png`, fullPage: true });

    await page.getByRole('button', { name: /^Upload$/ }).click({ timeout: ACT_TIMEOUT });
    await expect(page.locator('text=/Lịch thi:.*dòng đã import/')).toBeVisible({ timeout: 60_000 });
    await page.screenshot({ path: `${SNAP_DIR}/12-exam-upload-result.png`, fullPage: true });

    // DB status panel should reflect the new source
    await expect(page.getByText('Trạng thái database lịch thi')).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: `${SNAP_DIR}/13-exam-db-status-panel.png`, fullPage: true });
  });

  test('Crawler — trigger, observe status, review staged output', async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByRole('tab', { name: 'Hệ thống' }).click({ timeout: ACT_TIMEOUT });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SNAP_DIR}/14-system-tab-initial.png`, fullPage: true });

    await selectRadixOption(page, 'Tất cả', /^Kế hoạch$/);

    await page.getByRole('button', { name: /Chạy Crawl/ }).click({ timeout: ACT_TIMEOUT });
    await expect(page.getByText(/Đã khởi động crawl|Crawl đang chạy/i)).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SNAP_DIR}/15-crawl-triggered.png`, fullPage: true });

    // Poll until the crawl finishes (real network crawl — can take a while)
    await expect(page.getByText('Crawler đang chạy...')).toHaveCount(0, { timeout: 9 * 60 * 1000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SNAP_DIR}/16-crawl-finished.png`, fullPage: true });
  });
});
