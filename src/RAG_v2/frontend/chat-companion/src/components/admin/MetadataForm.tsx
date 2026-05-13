import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Save } from 'lucide-react';

interface MetadataFormProps {
  initial: Record<string, unknown>;
  onSave: (meta: Record<string, string>) => Promise<void>;
}

export default function MetadataForm({ initial, onSave }: MetadataFormProps) {
  const [cohort, setCohort] = useState((initial.cohort as string) || '');
  const [majorCode, setMajorCode] = useState((initial.major_code as string) || '');
  const [dateStr, setDateStr] = useState((initial.date_str as string) || '');
  const [saving, setSaving] = useState(false);

  const validate = (): string | null => {
    if (cohort && !/^K\d+$/i.test(cohort)) return 'Khóa phải có dạng K + số (vd: K68)';
    return null;
  };

  const handleSave = async () => {
    const err = validate();
    if (err) { toast.error(err); return; }
    setSaving(true);
    try {
      const meta: Record<string, string> = {};
      if (cohort) meta.cohort = cohort;
      if (majorCode) meta.major_code = majorCode;
      if (dateStr) meta.date_str = dateStr;
      await onSave(meta);
      toast.success('Metadata đã lưu');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Lưu metadata thất bại');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <h4 className="text-sm font-semibold">Metadata (tuỳ chọn)</h4>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label>Khóa (cohort)</Label>
          <Input placeholder="K68" value={cohort} onChange={(e) => setCohort(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Mã ngành (major_code)</Label>
          <Input placeholder="IT1" value={majorCode} onChange={(e) => setMajorCode(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Ngày ban hành</Label>
          <Input placeholder="01/01/2024" value={dateStr} onChange={(e) => setDateStr(e.target.value)} />
        </div>
      </div>
      <Button size="sm" onClick={handleSave} disabled={saving}>
        <Save className="mr-1 h-3 w-3" />
        {saving ? 'Đang lưu…' : 'Lưu metadata'}
      </Button>
    </div>
  );
}
