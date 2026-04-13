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

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const COHORTS = ["K65", "K66", "K67", "K68", "K69"] as const;

interface ProfileForm {
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
}

const CompleteProfile = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>({
    full_name: "",
    student_id: "",
    cohort: "",
    major: "CNTT Việt Nhật",
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [token, setToken] = useState<string>("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (!urlToken) {
      toast.error("Missing authentication token. Please log in again.");
      navigate("/login");
      return;
    }

    localStorage.setItem("token", urlToken);
    setToken(urlToken);

    fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${urlToken}` },
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data?.detail || `Error ${res.status}`);
        }
        return res.json();
      })
      .then((user) => {
        setForm({
          full_name: user.full_name ?? "",
          student_id: user.student_id ?? "",
          cohort: user.cohort ?? "",
          major: user.major ?? "CNTT Việt Nhật",
        });
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load profile.";
        toast.error(message);
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim()) {
      toast.error("Full name is required.");
      return;
    }
    if (!form.student_id.trim()) {
      toast.error("Student ID is required.");
      return;
    }
    if (!form.cohort) {
      toast.error("Please select your cohort.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          full_name: form.full_name,
          student_id: form.student_id,
          cohort: form.cohort,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Error ${res.status}`);
      }

      const updatedUser = await res.json().catch(() => null);
      if (updatedUser) {
        localStorage.setItem("user", JSON.stringify(updatedUser));
      }

      navigate("/chat");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to save profile.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-[420px] rounded-2xl border border-border bg-card p-8 shadow-sm">
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
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              HUST Assistant
            </p>
            <h1 className="mt-1 text-2xl font-bold text-foreground">Complete your profile</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Confirm your information before continuing
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
                Full Name
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
                Student ID
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
                Cohort
              </Label>
              <Select
                value={form.cohort}
                onValueChange={(val) => setForm((f) => ({ ...f, cohort: val }))}
              >
                <SelectTrigger id="cohort" className="w-full">
                  <SelectValue placeholder="Select your cohort" />
                </SelectTrigger>
                <SelectContent>
                  {COHORTS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Major (disabled) */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="major" className="text-sm font-medium text-foreground">
                Major
              </Label>
              <Input
                id="major"
                type="text"
                value={form.major}
                disabled
                className="cursor-not-allowed opacity-60"
              />
            </div>

            <Button
              type="submit"
              className="mt-2 w-full"
              disabled={submitting}
            >
              {submitting ? "Saving…" : "Save & Continue"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};

export default CompleteProfile;
