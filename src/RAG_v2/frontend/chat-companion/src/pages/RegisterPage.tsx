import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
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
import { registerUser } from "@/services/authApi";
import { getCurrentSessionUser, ensureSession } from "@/services/authSession";
import HustLogo from "@/components/HustLogo";
import { COHORT_OPTIONS, MAJOR_OPTIONS, findMajorOptionByCode } from "@rag/shared";
import axios from "axios";

const EyeIcon = ({ show }: { show: boolean }) =>
  show ? (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  ) : (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );

interface FormErrors {
  username?: string;
  password?: string;
  confirmPassword?: string;
  fullName?: string;
  cohort?: string;
  major?: string;
  majorCode?: string;
  api?: string;
}

const RegisterPage = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [fullName, setFullName] = useState("");
  const [cohort, setCohort] = useState("");
  const [major, setMajor] = useState("");
  const [majorCode, setMajorCode] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const selectedMajor = findMajorOptionByCode(majorCode);

  useEffect(() => {
    const cached = getCurrentSessionUser();
    if (cached) {
      navigate(cached.role === "admin" ? "/admin" : "/chat", { replace: true });
      return;
    }
    ensureSession().then((user) => {
      if (user) {
        navigate(user.role === "admin" ? "/admin" : "/chat", { replace: true });
      } else {
        setChecking(false);
      }
    }).catch(() => setChecking(false));
  }, [navigate]);

  const validate = (): boolean => {
    const next: FormErrors = {};
    if (!username.trim()) next.username = "Tên đăng nhập là bắt buộc.";
    else if (username.trim().length < 3) next.username = "Tối thiểu 3 ký tự.";
    if (!password) next.password = "Mật khẩu là bắt buộc.";
    else if (password.length < 8) next.password = "Mật khẩu tối thiểu 8 ký tự.";
    if (!confirmPassword) next.confirmPassword = "Vui lòng xác nhận mật khẩu.";
    else if (confirmPassword !== password) next.confirmPassword = "Mật khẩu không khớp.";
    if (!fullName.trim()) next.fullName = "Họ và tên là bắt buộc.";
    if (!cohort.trim()) next.cohort = "Khoá học là bắt buộc.";
    if (!selectedMajor || !major.trim() || major !== selectedMajor.name) {
      next.major = "Ngành học là bắt buộc.";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleMajorChange = (code: string) => {
    const option = findMajorOptionByCode(code);
    setMajorCode(option?.code ?? "");
    setMajor(option?.name ?? "");
    if (errors.major || errors.majorCode) {
      setErrors((prev) => ({ ...prev, major: undefined, majorCode: undefined }));
    }
  };

  const handleCohortChange = (value: string) => {
    setCohort(value);
    if (errors.cohort) {
      setErrors((prev) => ({ ...prev, cohort: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setErrors({});
    try {
      await registerUser({
        username,
        password,
        full_name: fullName,
        cohort,
        major,
        major_code: majorCode,
      });
      navigate("/login");
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrors({ api: err.response?.data?.detail ?? "Đăng ký thất bại." });
      } else {
        setErrors({ api: "Đăng ký thất bại." });
      }
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="animate-pulse text-muted-foreground text-sm">Đang kiểm tra phiên...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="h-1 w-full bg-accent"></div>
        <div className="p-8">
        {/* Header */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <HustLogo size="lg" />
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              ĐẠI HỌC BÁCH KHOA HÀ NỘI
            </p>
            <h1 className="mt-1 text-2xl font-bold text-foreground">Tạo tài khoản</h1>
            <p className="mt-1 text-sm text-muted-foreground">Đăng ký để sử dụng Trợ Lý Học Vụ</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {errors.api && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {errors.api}
            </p>
          )}

          {/* Username */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="username" className="text-sm font-medium text-foreground">
              Tên đăng nhập
            </Label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              placeholder="vd: nguyen_van_a"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={errors.username ? "border-destructive focus-visible:ring-destructive" : ""}
            />
            {errors.username && <p className="text-xs text-destructive">{errors.username}</p>}
          </div>

          {/* Full Name */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fullName" className="text-sm font-medium text-foreground">
              Họ và tên
            </Label>
            <Input
              id="fullName"
              type="text"
              autoComplete="name"
              placeholder="Nguyễn Văn A"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={errors.fullName ? "border-destructive focus-visible:ring-destructive" : ""}
            />
            {errors.fullName && <p className="text-xs text-destructive">{errors.fullName}</p>}
          </div>

          {/* Major */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="major" className="text-sm font-medium text-foreground">
              Ngành học
            </Label>
            <Select value={majorCode} onValueChange={handleMajorChange}>
              <SelectTrigger
                id="major"
                className={errors.major ? "border-destructive focus:ring-destructive" : ""}
              >
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
            {errors.major && <p className="text-xs text-destructive">{errors.major}</p>}
          </div>

          {selectedMajor && (
            <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Mã ngành: <span className="font-semibold text-foreground">{selectedMajor.code}</span>
            </div>
          )}

          {/* Cohort */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cohort" className="text-sm font-medium text-foreground">
              Khoá học
            </Label>
            <Select value={cohort} onValueChange={handleCohortChange}>
              <SelectTrigger
                id="cohort"
                className={errors.cohort ? "border-destructive focus:ring-destructive" : ""}
              >
                <SelectValue placeholder="Chọn khoá học" />
              </SelectTrigger>
              <SelectContent>
                {COHORT_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.cohort && <p className="text-xs text-destructive">{errors.cohort}</p>}
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className="text-sm font-medium text-foreground">
              Mật khẩu
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Tối thiểu 8 ký tự"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`pr-10 ${errors.password ? "border-destructive focus-visible:ring-destructive" : ""}`}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
              >
                <EyeIcon show={showPassword} />
              </button>
            </div>
            {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
          </div>

          {/* Confirm Password */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirmPassword" className="text-sm font-medium text-foreground">
              Xác nhận mật khẩu
            </Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirm ? "text" : "password"}
                autoComplete="new-password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`pr-10 ${errors.confirmPassword ? "border-destructive focus-visible:ring-destructive" : ""}`}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowConfirm((v) => !v)}
                tabIndex={-1}
              >
                <EyeIcon show={showConfirm} />
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="text-xs text-destructive">{errors.confirmPassword}</p>
            )}
          </div>

          <Button type="submit" className="mt-1 w-full font-semibold" disabled={loading}>
            {loading ? "Đang đăng ký…" : "Đăng ký"}
          </Button>
        </form>

        {/* Footer links */}
        <div className="mt-6 flex flex-col items-center gap-2 text-sm text-muted-foreground">
          <p>
            Đã có tài khoản?{" "}
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => navigate("/login")}
            >
              Đăng nhập
            </button>
          </p>
          <button
            type="button"
            className="text-xs hover:text-foreground hover:underline"
            onClick={() => navigate("/")}
          >
            Trở về trang chủ
          </button>
        </div>
      </div>
      </div>
    </div>
  );
};

export default RegisterPage;
