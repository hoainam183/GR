import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Save, Check } from 'lucide-react';

function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

interface MarkdownEditorProps {
  content: string;
  onSave: (content: string) => Promise<void>;
  approved?: boolean;
  title?: string;
}

export default function MarkdownEditor({ content, onSave, approved, title = 'Markdown' }: MarkdownEditorProps) {
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const dirty = value !== content;

  useEffect(() => {
    setValue(content);
  }, [content]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(value);
      toast.success(`${title} đã được lưu`);
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, `Lưu ${title} thất bại`));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">
          {title}
          {approved && (
            <span className="ml-2 inline-flex items-center gap-1 text-xs text-green-600">
              <Check className="h-3 w-3" /> Đã duyệt
            </span>
          )}
        </h4>
        <Button size="sm" onClick={handleSave} disabled={saving || !dirty}>
          <Save className="mr-1 h-3 w-3" />
          {saving ? 'Đang lưu…' : 'Lưu & Duyệt'}
        </Button>
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="min-h-[400px] font-mono text-sm"
      />
    </div>
  );
}
