/**
 * Helpers to turn raw retrieved chunks (markdown) into something a student can
 * actually read inside the app. The retriever stores chunks as markdown — with
 * `####` headings, `**bold**`, horizontal rules and pipe tables — which is noise
 * when shown verbatim in a citation card. We strip the syntax to plain text and
 * map internal collection ids to friendly Vietnamese labels.
 */

const COLLECTION_LABELS: Record<string, string> = {
  ctdt: 'Chương trình đào tạo',
  quydinh: 'Quy định',
  quyche: 'Quy chế',
  kehoach: 'Kế hoạch học tập',
  hocphi: 'Học phí',
  bieumau: 'Biểu mẫu',
  thongbao: 'Thông báo',
  web: 'Nguồn web',
  tavily: 'Nguồn web',
};

/** Map an internal collection id (e.g. "ctdt") to a label a student understands. */
export const friendlyCollection = (collection?: string | null): string | null => {
  if (!collection) return null;
  const key = collection.trim().toLowerCase();
  return COLLECTION_LABELS[key] ?? collection;
};

const isTableSeparator = (line: string): boolean =>
  /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(line);

const isHorizontalRule = (line: string): boolean =>
  /^(-{3,}|\*{3,}|_{3,})$/.test(line);

const looksLikeTableRow = (line: string): boolean =>
  line.includes('|') && line.split('|').filter((c) => c.trim().length > 0).length >= 2;

/**
 * Convert a markdown chunk into readable plain text:
 * drop heading/bold/list markers, flatten pipe tables to dot-separated rows,
 * remove rule and table-separator lines, and collapse blank runs.
 * Note: avoids regex lookbehind (Hermes compatibility).
 */
export const stripMarkdown = (raw: string): string => {
  if (!raw) return '';

  let text = raw;
  // Fenced code blocks → keep inner text, drop the ``` fences.
  text = text.replace(/```[\s\S]*?```/g, (block) => block.replace(/```/g, ''));
  // Inline code, links/images, emphasis markers.
  text = text.replace(/`([^`]+)`/g, '$1');
  text = text.replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1');
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
  text = text.replace(/\*([^*]+)\*/g, '$1');
  text = text.replace(/__([^_]+)__/g, '$1');
  text = text.replace(/_([^_\n]+)_/g, '$1');

  const out: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    let line = rawLine.trim();
    if (!line) {
      out.push('');
      continue;
    }
    if (isTableSeparator(line) || isHorizontalRule(line)) continue;

    line = line.replace(/^#{1,6}\s*/, ''); // headings
    line = line.replace(/^>\s?/, ''); // blockquote
    line = line.replace(/^[-*+]\s+/, '• '); // unordered list marker

    if (looksLikeTableRow(line)) {
      const cells = line
        .split('|')
        .map((cell) => cell.trim())
        .filter((cell) => cell.length > 0);
      if (cells.length) {
        out.push(cells.join('  ·  '));
        continue;
      }
    }
    out.push(line);
  }

  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
};

/** One-line preview (markdown stripped, newlines flattened) for compact cards. */
export const toPlainPreview = (raw: string): string =>
  stripMarkdown(raw).replace(/\s*\n+\s*/g, ' ').trim();
