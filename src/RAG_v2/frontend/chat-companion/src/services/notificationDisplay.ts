import type { NotificationItem } from '@rag/shared';

const CRAWL_COMPLETION_PREFIX = /^Crawl\s+'[^']+'\s+hoàn tất\.\s*/i;

const SOURCE_LABELS: Record<string, string> = {
  baiviet: 'Kế hoạch',
  kehoach: 'Kế hoạch',
  kehoach_list: 'Kế hoạch',
  quydinh: 'Quy định',
};

const humanizeSourceList = (sourceText: string): string => {
  const labels: string[] = [];
  for (const rawSource of sourceText.split(',')) {
    const source = rawSource.trim();
    if (!source) continue;

    const label = SOURCE_LABELS[source.toLowerCase()] ?? source;
    if (!labels.includes(label)) labels.push(label);
  }
  return labels.join(', ');
};

const humanizeCrawlerSources = (body: string): string =>
  body.replace(/từ nguồn ([^.]+)/i, (match, sourceText: string) => {
    const sourceLabel = humanizeSourceList(sourceText);
    return sourceLabel ? `từ nguồn ${sourceLabel}` : match;
  });

export const getNotificationDisplayTitle = (item: NotificationItem): string => {
  if (item.type === 'crawler_update' && item.title.toLowerCase().includes('crawl')) {
    return 'Cập nhật dữ liệu đã hoàn tất';
  }
  return item.title;
};

export const getNotificationDisplayBody = (item: NotificationItem): string => {
  if (item.type !== 'crawler_update') return item.body;

  const body = item.body.replace(CRAWL_COMPLETION_PREFIX, '').trim() || item.body;
  return humanizeCrawlerSources(body);
};
