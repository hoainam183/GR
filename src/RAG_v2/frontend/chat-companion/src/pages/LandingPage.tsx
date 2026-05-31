import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { getCurrentSessionUser, ensureSession } from "@/services/authSession";
import HustLogo from "@/components/HustLogo";



const features = [
  {
    icon: (
      <svg
        className="h-6 w-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
    title: "Hỏi đáp thông minh",
    description:
      "Đặt câu hỏi về quy chế đào tạo, chương trình học và chính sách sinh viên. Nhận câu trả lời chính xác ngay lập tức.",
  },
  {
    icon: (
      <svg
        className="h-6 w-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
    ),
    title: "Tra cứu văn bản",
    description:
      "Tìm kiếm nhanh qua các văn bản, quy định và hướng dẫn chính thức của trường.",
  },
  {
    icon: (
      <svg
        className="h-6 w-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
    title: "Hỗ trợ 24/7",
    description:
      "Luôn sẵn sàng — trước kỳ thi, trong đăng ký học, hay bất cứ khi nào bạn cần. Trợ lý không bao giờ nghỉ.",
  },
];

const LandingPage = () => {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);

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
        setReady(true);
      }
    }).catch(() => setReady(true));
  }, [navigate]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="animate-pulse text-muted-foreground text-sm">Đang kiểm tra phiên...</div>
      </div>
    );
  }

  const scrollToFeatures = () => {
    document.getElementById("features")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="flex min-h-screen flex-col bg-background font-sans">
      {/* Navbar */}
      <header className="sticky top-0 z-50 border-b border-border/50 hust-gradient-header backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-2.5">
            <HustLogo size="md" />
            <div>
              <span className="text-lg font-semibold text-white">
                ĐHBK Hà Nội
              </span>
              <span className="block text-xs text-white/70">Trợ Lý Học Vụ</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              className="text-sm font-medium text-white hover:bg-white/20"
              onClick={() => navigate("/login")}
            >
              Đăng nhập
            </Button>
            <Button
              className="text-sm font-medium bg-white text-foreground hover:bg-white/90"
              onClick={() => navigate("/register")}
            >
              Đăng ký
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center md:py-36">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-accent"></span>
            AI · Dành cho sinh viên Bách Khoa
          </div>
          <h1 className="mb-6 text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl md:text-6xl">
            Trợ Lý Học Vụ{" "}
            <span className="text-primary">Bách Khoa</span>
          </h1>
          <p className="mx-auto mb-10 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Giải đáp mọi thắc mắc về quy chế, chương trình đào tạo và chính sách sinh viên — mọi lúc, mọi nơi.
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              className="w-full px-8 text-sm font-semibold sm:w-auto"
              onClick={() => navigate("/chat")}
            >
              Bắt đầu ngay
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="w-full px-8 text-sm font-semibold sm:w-auto"
              onClick={scrollToFeatures}
            >
              Tìm hiểu thêm
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="border-t border-border bg-secondary/40 px-4 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <h2 className="mb-3 text-3xl font-bold tracking-tight text-foreground">
              Tính năng nổi bật
            </h2>
            <p className="text-base text-muted-foreground">
              Được thiết kế để cuộc sống đại học đơn giản và thông minh hơn.
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="flex flex-col gap-4 rounded-xl border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  {feature.icon}
                </div>
                <div>
                  <h3 className="mb-1.5 text-base font-semibold text-foreground">
                    {feature.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border bg-background px-4 py-6">
        <div className="mx-auto flex max-w-6xl items-center justify-center">
          <p className="text-sm text-muted-foreground">
            © 2025 Đại học Bách Khoa Hà Nội. Trợ Lý Học Vụ Thông Minh.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
