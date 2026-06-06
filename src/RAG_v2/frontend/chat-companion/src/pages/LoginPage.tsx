import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { loginUser } from "@/services/authApi";
import { applyTokenResponse, getCurrentSessionUser, ensureSession } from "@/services/authSession";
import HustLogo from "@/components/HustLogo";
import axios from "axios";

const isInternalPath = (value: string | null): value is string =>
  Boolean(value?.startsWith("/") && !value.startsWith("//"));

const isAdminPath = (value: string): boolean =>
  value === "/admin" ||
  value.startsWith("/admin/") ||
  value === "/trace" ||
  value === "/retrieval" ||
  value === "/eval";

const safeNextPath = (value: string | null): string | null =>
  isInternalPath(value) ? value : null;

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

const LoginPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ username?: string; password?: string; api?: string }>({});
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

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

  const validate = () => {
    const next: { username?: string; password?: string } = {};
    if (!username.trim()) next.username = "Tên đăng nhập là bắt buộc.";
    if (!password) next.password = "Mật khẩu là bắt buộc.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setErrors({});
    try {
      const result = applyTokenResponse(await loginUser({ username, password }));
      const next = safeNextPath(searchParams.get("next"));
      if (next && (result.user.role === "admin" || !isAdminPath(next))) {
        navigate(next);
      } else if (result.user.role === "admin") {
        navigate("/admin");
      } else {
        navigate("/chat");
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrors({ api: err.response?.data?.detail ?? "Đăng nhập thất bại." });
      } else {
        setErrors({ api: "Đăng nhập thất bại." });
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
            <h1 className="mt-1 text-2xl font-bold text-foreground">Chào mừng trở lại</h1>
            <p className="mt-1 text-sm text-muted-foreground">Đăng nhập vào tài khoản của bạn</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {errors.api && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {errors.api}
            </p>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="username" className="text-sm font-medium text-foreground">
              Tên đăng nhập
            </Label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              placeholder="Nhập tên đăng nhập"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={errors.username ? "border-destructive focus-visible:ring-destructive" : ""}
            />
            {errors.username && (
              <p className="text-xs text-destructive">{errors.username}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className="text-sm font-medium text-foreground">
              Mật khẩu
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`pr-10 ${errors.password ? "border-destructive focus-visible:ring-destructive" : ""}`}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                <EyeIcon show={showPassword} />
              </button>
            </div>
            {errors.password && (
              <p className="text-xs text-destructive">{errors.password}</p>
            )}
          </div>

          <Button type="submit" className="mt-1 w-full font-semibold" disabled={loading}>
            {loading ? "Đang đăng nhập…" : "Đăng nhập"}
          </Button>
        </form>

        {/* Footer links */}
        <div className="mt-6 flex flex-col items-center gap-2 text-sm text-muted-foreground">
          <p>
            Chưa có tài khoản?{" "}
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => navigate("/register")}
            >
              Đăng ký
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

export default LoginPage;
