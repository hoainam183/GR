import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { uploadDocuments } from '@/services/adminApi';
import { COLLECTION_CHUNKER_MAP, CHUNKER_ALTERNATIVES } from '@/types/admin';
import type { CollectionName, DocumentDetail } from '@/types/admin';
import { toast } from 'sonner';
import { Upload, X, FileText } from 'lucide-react';

const MAX_SIZE_MB = 50;
const COLLECTIONS: CollectionName[] = ['ctdt', 'quydinh', 'kehoach', 'stsv', 'test'];

interface FileUploaderProps {
  onUploaded: (docs: DocumentDetail[]) => void;
}

export default function FileUploader({ onUploaded }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [collection, setCollection] = useState<CollectionName | ''>('');
  const [strategy, setStrategy] = useState<string>('');
  const [progress, setProgress] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const valid: File[] = [];
    for (const f of Array.from(incoming)) {
      if (f.type !== 'application/pdf') {
        toast.error(`${f.name}: chỉ hỗ trợ file PDF`);
        continue;
      }
      if (f.size > MAX_SIZE_MB * 1024 * 1024) {
        toast.error(`${f.name}: vượt quá ${MAX_SIZE_MB}MB`);
        continue;
      }
      valid.push(f);
    }
    setFiles((prev) => [...prev, ...valid].slice(0, 5));
  };

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const handleUpload = async () => {
    if (!collection) {
      toast.error('Vui lòng chọn collection');
      return;
    }
    if (files.length === 0) {
      toast.error('Vui lòng chọn ít nhất 1 file PDF');
      return;
    }
    setUploading(true);
    setProgress(0);
    try {
      const docs = await uploadDocuments(
        files,
        collection,
        strategy || undefined,
        undefined,
        setProgress,
      );
      toast.success(`Đã upload ${docs.length} file thành công`);
      setFiles([]);
      setProgress(null);
      onUploaded(docs);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Upload thất bại';
      toast.error(typeof msg === 'string' ? msg : 'Upload thất bại');
    } finally {
      setUploading(false);
    }
  };

  const alternatives = collection ? CHUNKER_ALTERNATIVES[collection] : [];

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <h3 className="text-lg font-semibold">Upload tài liệu</h3>

      {/* Drop zone */}
      <div
        className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-6 text-muted-foreground transition hover:border-primary"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
      >
        <Upload className="h-8 w-8" />
        <p className="text-sm">Kéo thả hoặc nhấn để chọn file PDF (tối đa 5 file, {MAX_SIZE_MB}MB/file)</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
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

      {/* Collection + Strategy selectors */}
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

      {/* Progress + Upload button */}
      {progress !== null && <Progress value={progress} className="h-2" />}
      <Button onClick={handleUpload} disabled={uploading || files.length === 0}>
        {uploading ? 'Đang upload...' : 'Upload'}
      </Button>
    </div>
  );
}
