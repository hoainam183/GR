import { useEffect, useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  uploadDocuments,
  uploadExamSchedule,
  getExamScheduleSummary,
  deleteExamScheduleSource,
} from '@/services/adminApi';
import { COLLECTION_CHUNKER_MAP, CHUNKER_ALTERNATIVES } from '@/types/admin';
import type {
  CollectionName,
  DocumentDetail,
  UploadKind,
  ExamType,
  ExamScheduleUploadResponse,
  ExamScheduleSummary,
} from '@/types/admin';
import { toast } from 'sonner';
import {
  Upload,
  X,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Database,
  RefreshCw,
  Trash2,
} from 'lucide-react';

const MAX_SIZE_MB = 50;
const COLLECTIONS: CollectionName[] = ['ctdt', 'quydinh', 'kehoach', 'stsv', 'test'];
const EXAM_ACCEPTED_MIMES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
  'application/vnd.ms-excel.sheet.macroEnabled.12', // .xlsm
]);
const EXAM_ACCEPTED_EXTS = ['.pdf', '.xlsx', '.xlsm'];
const DOC_ACCEPTED_MIMES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
]);
const DOC_ACCEPTED_EXTS = ['.pdf', '.docx'];

function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

interface FileUploaderProps {
  onUploaded: (docs: DocumentDetail[]) => void;
}

export default function FileUploader({ onUploaded }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<UploadKind>('document');
  const [files, setFiles] = useState<File[]>([]);
  const [collection, setCollection] = useState<CollectionName | ''>('');
  const [strategy, setStrategy] = useState<string>('');
  // '' = auto-detect the exam term from the file banner/filename.
  const [examType, setExamType] = useState<ExamType | ''>('');
  const [progress, setProgress] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [examResult, setExamResult] = useState<ExamScheduleUploadResponse | null>(null);
  const [dbSummary, setDbSummary] = useState<ExamScheduleSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const isExam = kind === 'exam_schedule';
  const maxFiles = isExam ? 1 : 5;

  const refreshDbSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const summary = await getExamScheduleSummary();
      setDbSummary(summary);
    } catch (error: unknown) {
      setSummaryError(apiErrorMessage(error, 'Không tải được trạng thái database'));
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const handleDeleteSource = useCallback(
    async (sourceFile: string) => {
      const ok = window.confirm(
        `Xoá toàn bộ lịch thi từ "${sourceFile}"?\nHành động này không thể hoàn tác.`,
      );
      if (!ok) return;
      try {
        const result = await deleteExamScheduleSource(sourceFile);
        toast.success(
          `Đã xoá ${result.mongo_deleted} dòng (ES: ${result.es_deleted}, file: ${result.files_deleted})`,
        );
        await refreshDbSummary();
      } catch (error: unknown) {
        toast.error(apiErrorMessage(error, 'Xoá lịch thi thất bại'));
      }
    },
    [refreshDbSummary],
  );

  // Fetch DB snapshot the first time admin switches to exam-schedule mode.
  useEffect(() => {
    if (isExam && dbSummary === null && !summaryLoading && summaryError === null) {
      void refreshDbSummary();
    }
  }, [isExam, dbSummary, summaryLoading, summaryError, refreshDbSummary]);

  const isAcceptedFile = (f: File): boolean => {
    const mimes = isExam ? EXAM_ACCEPTED_MIMES : DOC_ACCEPTED_MIMES;
    const exts = isExam ? EXAM_ACCEPTED_EXTS : DOC_ACCEPTED_EXTS;
    // MIME first, then extension fallback — browsers sometimes report an empty
    // or generic MIME for .docx/.xlsx.
    if (mimes.has(f.type)) return true;
    const lower = f.name.toLowerCase();
    return exts.some((ext) => lower.endsWith(ext));
  };

  const rejectionMessage = (name: string): string =>
    `${name}: chỉ hỗ trợ ${(isExam ? EXAM_ACCEPTED_EXTS : DOC_ACCEPTED_EXTS).join('/')}`;

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const valid: File[] = [];
    for (const f of Array.from(incoming)) {
      if (!isAcceptedFile(f)) {
        toast.error(rejectionMessage(f.name));
        continue;
      }
      if (f.size > MAX_SIZE_MB * 1024 * 1024) {
        toast.error(`${f.name}: vượt quá ${MAX_SIZE_MB}MB`);
        continue;
      }
      valid.push(f);
    }
    setFiles((prev) => [...prev, ...valid].slice(0, maxFiles));
  };

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const handleKindChange = (next: UploadKind) => {
    setKind(next);
    setFiles([]);
    setProgress(null);
    setExamResult(null);
    if (next === 'exam_schedule') {
      setCollection('');
      setStrategy('');
    } else {
      setExamType('');
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error(isExam ? 'Vui lòng chọn 1 file lịch thi' : 'Vui lòng chọn ít nhất 1 file PDF/DOCX');
      return;
    }
    if (!isExam && !collection) {
      toast.error('Vui lòng chọn collection');
      return;
    }
    setUploading(true);
    setProgress(0);
    try {
      if (isExam) {
        setExamResult(null);
        const report = await uploadExamSchedule(files[0], examType, setProgress);
        setExamResult(report);
        toast.success(
          `Lịch thi: ${report.parsed} dòng đã import` +
            (report.skipped ? `, bỏ qua ${report.skipped}` : '') +
            (report.replaced_existing ? ' (đã thay thế dữ liệu cũ)' : ''),
        );
        setFiles([]);
        setProgress(null);
        onUploaded([]);
        // Verify by re-reading the DB snapshot.
        void refreshDbSummary();
      } else {
        const docs = await uploadDocuments(
          files,
          collection as CollectionName,
          strategy || undefined,
          undefined,
          setProgress,
        );
        toast.success(`Đã upload ${docs.length} file thành công`);
        setFiles([]);
        setProgress(null);
        onUploaded(docs);
      }
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Upload thất bại'));
    } finally {
      setUploading(false);
    }
  };

  const alternatives = collection ? CHUNKER_ALTERNATIVES[collection] : [];

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <h3 className="text-lg font-semibold">Upload tài liệu</h3>

      {/* Document kind selector */}
      <div className="space-y-1.5">
        <Label>Loại tài liệu *</Label>
        <Select value={kind} onValueChange={(v) => handleKindChange(v as UploadKind)}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="document">Tài liệu thường (CTĐT / Quy định / Kế hoạch / Hỗ trợ SV)</SelectItem>
            <SelectItem value="exam_schedule">Lịch thi</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {isExam
            ? 'File sẽ được parse thành các dòng lịch thi (mã HP, phòng, kíp, ngày...) và lưu vào MongoDB + Elasticsearch. Up lại cùng tên sẽ thay thế dữ liệu cũ.'
            : 'File sẽ đi qua pipeline convert → clean → chunk → embed và lưu vào Qdrant + Elasticsearch.'}
        </p>
      </div>

      {/* Drop zone */}
      <div
        className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-6 text-muted-foreground transition hover:border-primary"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
      >
        <Upload className="h-8 w-8" />
        <p className="text-sm">
          {isExam
            ? `Kéo thả hoặc nhấn để chọn 1 file ${EXAM_ACCEPTED_EXTS.join('/')} (${MAX_SIZE_MB}MB)`
            : `Kéo thả hoặc nhấn để chọn file ${DOC_ACCEPTED_EXTS.join('/')} (tối đa ${maxFiles} file, ${MAX_SIZE_MB}MB/file)`}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={isExam ? EXAM_ACCEPTED_EXTS.join(',') : DOC_ACCEPTED_EXTS.join(',')}
          multiple={!isExam}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between rounded bg-muted px-3 py-1.5 text-sm">
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                {f.name} <span className="text-xs text-muted-foreground">({(f.size / 1024 / 1024).toFixed(1)} MB)</span>
              </span>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => removeFile(i)}>
                <X className="h-3 w-3" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {/* Collection + Strategy selectors — only for the document pipeline */}
      {!isExam && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Collection *</Label>
            <Select value={collection} onValueChange={(v) => {
              setCollection(v as CollectionName);
              setStrategy(COLLECTION_CHUNKER_MAP[v as CollectionName] || '');
            }}>
              <SelectTrigger><SelectValue placeholder="Chọn collection" /></SelectTrigger>
              <SelectContent>
                {COLLECTIONS.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Chunking strategy</Label>
            <Select value={strategy} onValueChange={setStrategy}>
              <SelectTrigger><SelectValue placeholder="Mặc định" /></SelectTrigger>
              <SelectContent>
                {alternatives.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      {/* Exam term selector — only for lịch thi. '' = auto-detect from file. */}
      {isExam && (
        <div className="space-y-1.5">
          <Label>Kỳ thi</Label>
          <Select
            value={examType || 'auto'}
            onValueChange={(v) => setExamType(v === 'auto' ? '' : (v as ExamType))}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Tự động (từ file)</SelectItem>
              <SelectItem value="giua_ky">Giữa kỳ</SelectItem>
              <SelectItem value="cuoi_ky">Cuối kỳ</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Để "Tự động" sẽ nhận diện giữa/cuối kỳ từ banner trong file. Chọn thủ
            công nếu file không ghi rõ hoặc nhận diện sai.
          </p>
        </div>
      )}

      {/* Progress + Upload button */}
      {progress !== null && <Progress value={progress} className="h-2" />}
      <Button onClick={handleUpload} disabled={uploading || files.length === 0}>
        {uploading ? 'Đang upload...' : 'Upload'}
      </Button>

      {/* Result card — only for exam schedule, persists until next upload / kind switch */}
      {isExam && examResult && <ExamResultCard result={examResult} />}

      {/* DB status panel — only for exam schedule */}
      {isExam && (
        <ExamDbStatusPanel
          summary={dbSummary}
          loading={summaryLoading}
          error={summaryError}
          onRefresh={refreshDbSummary}
          onDelete={handleDeleteSource}
        />
      )}
    </div>
  );
}

// ─────────────────────────── Result card ───────────────────────────

const EXAM_TYPE_LABEL: Record<ExamType, string> = {
  giua_ky: 'Giữa kỳ',
  cuoi_ky: 'Cuối kỳ',
};

function ExamResultCard({ result }: { result: ExamScheduleUploadResponse }) {
  const hasSkipped = result.skipped > 0;
  const success = result.parsed > 0;
  const termLabel = result.exam_type ? EXAM_TYPE_LABEL[result.exam_type] : 'Không xác định';
  return (
    <div
      className={`rounded-md border p-3 text-sm ${
        success
          ? 'border-emerald-500/40 bg-emerald-500/5'
          : 'border-amber-500/40 bg-amber-500/5'
      }`}
    >
      <div className="flex items-center gap-2 font-medium">
        {success ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-amber-600" />
        )}
        <span>
          {success
            ? `Đã import ${result.parsed} dòng từ "${result.source_file}"`
            : `Không có dòng hợp lệ nào trong "${result.source_file}" — dữ liệu cũ được giữ nguyên`}
        </span>
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-4">
        <li>Parsed: <span className="font-medium text-foreground">{result.parsed}</span></li>
        <li>Skipped: <span className="font-medium text-foreground">{result.skipped}</span></li>
        <li>ES indexed: <span className="font-medium text-foreground">{result.records_indexed}</span></li>
        <li>
          Replaced:{' '}
          <span className="font-medium text-foreground">
            {result.replaced_existing ? 'Có' : 'Không'}
          </span>
        </li>
        <li>Kỳ thi: <span className="font-medium text-foreground">{termLabel}</span></li>
      </ul>
      {hasSkipped && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            Xem {result.report.skipped_rows.length} dòng bị bỏ qua
          </summary>
          <ul className="mt-1 max-h-40 overflow-y-auto rounded bg-background/60 p-2 font-mono">
            {result.report.skipped_rows.slice(0, 50).map((row) => (
              <li key={row.row_index}>
                row #{row.row_index}: {row.reason}
              </li>
            ))}
            {result.report.skipped_rows.length > 50 && (
              <li className="italic text-muted-foreground">
                ... còn {result.report.skipped_rows.length - 50} dòng nữa
              </li>
            )}
          </ul>
        </details>
      )}
    </div>
  );
}

// ─────────────────────────── DB status panel ───────────────────────────

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('vi-VN');
}

function ExamDbStatusPanel({
  summary,
  loading,
  error,
  onRefresh,
  onDelete,
}: {
  summary: ExamScheduleSummary | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void | Promise<void>;
  onDelete: (sourceFile: string) => void | Promise<void>;
}) {
  return (
    <div className="rounded-md border p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 font-medium">
          <Database className="h-4 w-4" />
          <span>Trạng thái database lịch thi</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void onRefresh()}
          disabled={loading}
          className="h-7 gap-1"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span className="text-xs">Làm mới</span>
        </Button>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {!error && loading && !summary && (
        <p className="text-xs text-muted-foreground">Đang tải...</p>
      )}

      {summary && (
        <>
          <ul className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
            <li className="rounded bg-muted/40 p-2">
              <div className="text-base font-semibold text-foreground">
                {summary.total_rows.toLocaleString('vi-VN')}
              </div>
              <div>Tổng số dòng</div>
            </li>
            <li className="rounded bg-muted/40 p-2">
              <div className="text-base font-semibold text-foreground">
                {summary.distinct_subjects.toLocaleString('vi-VN')}
              </div>
              <div>Mã học phần</div>
            </li>
            <li className="rounded bg-muted/40 p-2">
              <div className="text-base font-semibold text-foreground">
                {summary.distinct_exam_dates.toLocaleString('vi-VN')}
              </div>
              <div>Ngày thi</div>
            </li>
          </ul>

          {summary.sources.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Chưa có file lịch thi nào trong database.
            </p>
          ) : (
            <div className="mt-2 overflow-hidden rounded border">
              <table className="w-full text-xs">
                <thead className="bg-muted/40 text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1 text-left font-medium">File nguồn</th>
                    <th className="px-2 py-1 text-right font-medium">Số dòng</th>
                    <th className="px-2 py-1 text-left font-medium">Cập nhật lần cuối</th>
                    <th className="px-2 py-1 text-right font-medium w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {summary.sources.map((src) => (
                    <tr key={src.source_file} className="border-t">
                      <td className="truncate px-2 py-1" title={src.source_file}>
                        {src.source_file}
                      </td>
                      <td className="px-2 py-1 text-right font-mono">
                        {src.row_count.toLocaleString('vi-VN')}
                      </td>
                      <td className="px-2 py-1">{formatDateTime(src.latest_uploaded_at)}</td>
                      <td className="px-2 py-1 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:bg-destructive/10"
                          title="Xoá lịch thi này"
                          onClick={() => void onDelete(src.source_file)}
                          disabled={loading}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
