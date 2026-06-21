import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { setStoredUser } from "@/services/authStorage";
import { authFetch, ensureSession, throwIfNotOk } from "@/services/authSession";
import HustLogo from "@/components/HustLogo";
import { COHORT_OPTIONS, MAJOR_OPTIONS, findMajorOptionByCode } from "@rag/shared";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface ProfileForm {
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
}

const CompleteProfile = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>({
    full_name: "",
    student_id: "",
    cohort: "",
    major: "",
    major_code: "",
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const selectedMajor = findMajorOptionByCode(form.major_code);

  useEffect(() => {
    ensureSession()
      .then((user) => {
        if (!user) {
          navigate("/login");
          return;
        }
        const majorOption = findMajorOptionByCode(user.major_code);
        setForm({
          full_name: user.full_name ?? "",
          student_id: user.student_id ?? "",
          cohort: user.cohort ?? "",
          major: majorOption?.name ?? "",
          major_code: majorOption?.code ?? "",
        });
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Không thể tải hồ sơ.";
        toast.error(message);
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim()) {
      toast.error("Họ và tên là bắt buộc.");
      return;
    }
    if (!form.student_id.trim()) {
      toast.error("Mã số sinh viên là bắt buộc.");
      return;
    }
    if (!form.cohort) {
      toast.error("Vui lòng chọn khoá học.");
      return;
    }
    if (!selectedMajor) {
      toast.error("Vui lòng chọn ngành học.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/auth/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          full_name: form.full_name,
          student_id: form.student_id,
          cohort: form.cohort,
          major: selectedMajor.name,
          major_code: selectedMajor.code,
        }),
      });

      await throwIfNotOk(res, "Lưu hồ sơ thất bại.");

      const updatedUser = await res.json().catch(() => null);
      if (updatedUser) {
        setStoredUser(updatedUser);
      }

      navigate("/chat");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Lưu hồ sơ thất bại.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-[420px] overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="h-1 w-full bg-accent"></div>
        <div className="p-8">
        {/* Header */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <HustLogo size="lg" />
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              ĐẠI HỌC BÁCH KHOA HÀ NỘI
            </p>
            <h1 className="mt-1 text-2xl font-bold text-foreground">Hoàn thiện hồ sơ</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Xác nhận thông tin của bạn trước khi tiếp tục
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            {/* Full Name */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="full_name" className="text-sm font-medium text-foreground">
              Họ và tên
              </Label>
              <Input
                id="full_name"
                type="text"
                autoComplete="name"
                placeholder="Nguyễn Văn A"
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              />
            </div>

            {/* Student ID */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="student_id" className="text-sm font-medium text-foreground">
              Mã số sinh viên
              </Label>
              <Input
                id="student_id"
                type="text"
                autoComplete="off"
                placeholder="20XXXXXX"
                value={form.student_id}
                onChange={(e) => setForm((f) => ({ ...f, student_id: e.target.value }))}
              />
            </div>

            {/* Cohort */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cohort" className="text-sm font-medium text-foreground">
              Khoá học
              </Label>
              <Select
                value={form.cohort}
                onValueChange={(val) => setForm((f) => ({ ...f, cohort: val }))}
              >
                <SelectTrigger id="cohort" className="w-full">
                  <SelectValue placeholder="Chọn khoá học" />
                </SelectTrigger>
                <SelectContent>
                  {COHORT_OPTIONS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Major */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="major" className="text-sm font-medium text-foreground">
              Ngành học
              </Label>
              <Select
                value={form.major_code}
                onValueChange={(code) => {
                  const option = findMajorOptionByCode(code);
                  setForm((f) => ({
                    ...f,
                    major: option?.name ?? "",
                    major_code: option?.code ?? "",
                  }));
                }}
              >
                <SelectTrigger id="major" className="w-full">
                  <SelectValue placeholder="Chọn ngành học" />
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {MAJOR_OPTIONS.map((option) => (
                    <SelectItem key={option.code} value={option.code}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedMajor && (
                <p className="text-xs text-muted-foreground">
                  Mã ngành: <span className="font-semibold text-foreground">{selectedMajor.code}</span>
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="mt-2 w-full"
              disabled={submitting}
            >
              {submitting ? "Đang lưu…" : "Lưu và tiếp tục"}
            </Button>
          </form>
        )}
        </div>
      </div>
    </div>
  );
};

export default CompleteProfile;
