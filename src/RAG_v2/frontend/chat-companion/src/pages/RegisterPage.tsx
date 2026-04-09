import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const MicrosoftIcon = () => (
  <svg width="18" height="18" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
    <rect x="1" y="1" width="9" height="9" fill="#f25022" />
    <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
    <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
    <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
  </svg>
);

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

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
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  terms?: string;
}

const RegisterPage = () => {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const validate = (): boolean => {
    const next: FormErrors = {};
    if (!fullName.trim()) next.fullName = "Full name is required.";
    if (!email.trim()) next.email = "Email is required.";
    else if (!email.includes("@")) next.email = "Enter a valid email address.";
    if (!password) next.password = "Password is required.";
    else if (password.length < 8) next.password = "Password must be at least 8 characters.";
    if (!confirmPassword) next.confirmPassword = "Please confirm your password.";
    else if (confirmPassword !== password) next.confirmPassword = "Passwords do not match.";
    if (!agreedToTerms) next.terms = "You must agree to the Terms of Service.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    console.log("Register:", { fullName, email, password });
    navigate("/chat");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 shadow-sm">
        {/* Header */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
            <svg
              className="h-5 w-5 text-primary-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              HUST Assistant
            </p>
            <h1 className="mt-1 text-2xl font-bold text-foreground">Create an account</h1>
            <p className="mt-1 text-sm text-muted-foreground">Join HUST Assistant today</p>
          </div>
        </div>

        {/* OAuth */}
        <div className="flex flex-col gap-2.5">
          <Button
            variant="outline"
            className="w-full justify-center gap-2.5 border-border bg-card text-sm font-medium text-foreground hover:bg-secondary"
            type="button"
          >
            <MicrosoftIcon />
            Sign up with Microsoft
          </Button>
          <Button
            variant="outline"
            className="w-full justify-center gap-2.5 border-border bg-card text-sm font-medium text-foreground hover:bg-secondary"
            type="button"
          >
            <GoogleIcon />
            Sign up with Google
          </Button>
        </div>

        {/* Divider */}
        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs text-muted-foreground">or</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {/* Full Name */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fullName" className="text-sm font-medium text-foreground">
              Full Name
            </Label>
            <Input
              id="fullName"
              type="text"
              autoComplete="name"
              placeholder="Nguyen Van A"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={errors.fullName ? "border-destructive focus-visible:ring-destructive" : ""}
            />
            {errors.fullName && (
              <p className="text-xs text-destructive">{errors.fullName}</p>
            )}
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email" className="text-sm font-medium text-foreground">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="yourname@sis.hust.edu.vn"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={errors.email ? "border-destructive focus-visible:ring-destructive" : ""}
            />
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email}</p>
            )}
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password" className="text-sm font-medium text-foreground">
              Password
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Min. 8 characters"
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

          {/* Confirm Password */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="confirmPassword" className="text-sm font-medium text-foreground">
              Confirm Password
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
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                <EyeIcon show={showConfirm} />
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="text-xs text-destructive">{errors.confirmPassword}</p>
            )}
          </div>

          {/* Terms */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-start gap-2.5">
              <Checkbox
                id="terms"
                checked={agreedToTerms}
                onCheckedChange={(checked) => setAgreedToTerms(checked === true)}
                className="mt-0.5"
              />
              <Label
                htmlFor="terms"
                className="cursor-pointer text-sm leading-snug text-muted-foreground"
              >
                I agree to the{" "}
                <span className="font-medium text-primary hover:underline">
                  Terms of Service
                </span>{" "}
                and{" "}
                <span className="font-medium text-primary hover:underline">
                  Privacy Policy
                </span>
              </Label>
            </div>
            {errors.terms && (
              <p className="text-xs text-destructive">{errors.terms}</p>
            )}
          </div>

          <Button type="submit" className="mt-1 w-full font-semibold">
            Create Account
          </Button>
        </form>

        {/* Footer links */}
        <div className="mt-6 flex flex-col items-center gap-2 text-sm text-muted-foreground">
          <p>
            Already have an account?{" "}
            <button
              type="button"
              className="font-medium text-primary hover:underline"
              onClick={() => navigate("/login")}
            >
              Sign in
            </button>
          </p>
          <button
            type="button"
            className="text-xs hover:text-foreground hover:underline"
            onClick={() => navigate("/")}
          >
            Back to Home
          </button>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
