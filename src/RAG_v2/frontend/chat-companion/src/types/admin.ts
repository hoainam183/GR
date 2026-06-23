/** Types matching backend schemas/document.py */

export type DocumentStatus =
  | 'uploaded'
  | 'converting'
  | 'converted'
  | 'cleaning'
  | 'cleaned'
  | 'chunking'
  | 'chunked'
  | 'embedding'
  | 'indexed'
  | 'failed';

export type CollectionName = 'ctdt' | 'quydinh' | 'kehoach' | 'stsv' | 'test';

export const COLLECTION_CHUNKER_MAP: Record<CollectionName, string> = {
  quydinh: 'recursive',
  ctdt: 'recursive',
  kehoach: 'kehoach',
  stsv: 'stsv',
  test: 'recursive',
};

export const CHUNKER_ALTERNATIVES: Record<CollectionName, string[]> = {
  quydinh: ['recursive', 'hierarchical', 'olmocr'],
  ctdt: ['recursive', 'hierarchical'],
  kehoach: ['kehoach', 'recursive'],
  stsv: ['stsv', 'recursive'],
  test: ['recursive', 'hierarchical', 'olmocr'],
};

/** Converter options for the convert step */
export type ConverterName = 'pymupdf4llm' | 'docling' | 'pdfplumber';

export interface ConverterOption {
  key: ConverterName;
  label: string;
  description: string;
}

/** Chunker option from backend */
export interface ChunkerOption {
  key: string;
  label: string;
  description: string;
  collections: string[];
}

/** Summary of a chunk set produced by a specific strategy */
export interface ChunkStrategySummary {
  strategy: string;
  chunk_count: number;
  avg_size: number;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  file_size: number;
  status: DocumentStatus;
  collection: CollectionName;
  chunking_strategy: string | null;
  converter: string | null;
  chunk_count: number | null;
  markdown_reviewed: boolean;
  cleaned_reviewed: boolean;
  chunks_reviewed: boolean;
  metadata_overrides: Record<string, unknown>;
  uploaded_by: string;
  uploaded_at: string;
  error_message: string | null;
  converted_at: string | null;
  cleaned_at: string | null;
  chunked_at: string | null;
  indexed_at: string | null;
}

export interface DocumentListResponse {
  documents: DocumentDetail[];
  total: number;
  page: number;
  limit: number;
}

export interface ChunkPreview {
  chunk_id: string;
  chunk_index: number;
  content: string;
  metadata: Record<string, unknown>;
  edited?: boolean;
  updated_at?: string | null;
}

export interface ChunksResponse {
  chunks: ChunkPreview[];
  total: number;
  page: number;
  limit: number;
  strategy: string;
  stats: Record<string, number>;
}

export interface MarkdownContent {
  content: string;
}

export interface CleanedContent {
  content: string;
}

/** Pipeline step definition for UI rendering */
export interface PipelineStep {
  key: 'convert' | 'clean' | 'chunk' | 'index';
  label: string;
  runningStatus: DocumentStatus;
  doneStatus: DocumentStatus;
}

export const PIPELINE_STEPS: PipelineStep[] = [
  { key: 'convert', label: 'Chuyển đổi PDF', runningStatus: 'converting', doneStatus: 'converted' },
  { key: 'clean', label: 'Làm sạch', runningStatus: 'cleaning', doneStatus: 'cleaned' },
  { key: 'chunk', label: 'Chia chunk', runningStatus: 'chunking', doneStatus: 'chunked' },
  { key: 'index', label: 'Nhúng & Lưu trữ', runningStatus: 'embedding', doneStatus: 'indexed' },
];

/** Upload "kind" chosen by admin. Routes the form to the right backend pipeline. */
export type UploadKind = 'document' | 'exam_schedule';

/** Exam term for a lịch thi file. Empty string = auto-detect from the file. */
export type ExamType = 'giua_ky' | 'cuoi_ky';

/** Response from POST /admin/exam-schedules (schemas/exam_schedule.py). */
export interface SkippedRow {
  row_index: number;
  reason: string;
}

export interface ParseReport {
  total_rows: number;
  valid_rows: number;
  skipped_rows: SkippedRow[];
}

export interface ExamScheduleUploadResponse {
  source_file: string;
  parsed: number;
  skipped: number;
  invalid: number;
  replaced_existing: boolean;
  records_indexed: number;
  exam_type: ExamType | null;
  report: ParseReport;
}

/** Per-source statistics shown in the DB-status panel. */
export interface ExamScheduleSourceSummary {
  source_file: string;
  row_count: number;
  latest_uploaded_at: string | null;
}

/** Snapshot of the exam_schedules collection. */
export interface ExamScheduleSummary {
  total_rows: number;
  distinct_subjects: number;
  distinct_exam_dates: number;
  sources: ExamScheduleSourceSummary[];
}
