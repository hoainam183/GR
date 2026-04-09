import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

const Logo = () => (
  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
    <svg
      className="h-4 w-4 text-primary-foreground"
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
);

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
    title: "Smart Q&A",
    description:
      "Ask any question about HUST academic regulations, curriculum, and student policies. Get instant, accurate answers powered by AI.",
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
    title: "Document Search",
    description:
      "Instantly search through official university documents, circulars, and guidelines. Find what you need without digging through PDFs.",
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
    title: "24/7 Support",
    description:
      "Available around the clock — before exams, during registration, or whenever you need guidance. HUST Assistant never sleeps.",
  },
];

const LandingPage = () => {
  const navigate = useNavigate();

  const scrollToFeatures = () => {
    document.getElementById("features")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="flex min-h-screen flex-col bg-background font-sans">
      {/* Navbar */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-2.5">
            <Logo />
            <span className="text-lg font-semibold text-foreground">
              HUST Assistant
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              className="text-sm font-medium text-foreground hover:bg-secondary"
              onClick={() => navigate("/login")}
            >
              Login
            </Button>
            <Button
              className="text-sm font-medium"
              onClick={() => navigate("/register")}
            >
              Sign Up
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center md:py-36">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary"></span>
            Powered by AI · Built for HUST Students
          </div>
          <h1 className="mb-6 text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl md:text-6xl">
            Your Smart{" "}
            <span className="text-primary">Academic Assistant</span>
          </h1>
          <p className="mx-auto mb-10 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Instantly answer questions about HUST regulations, course
            programs, and student policies — all in one place, available
            any time.
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              className="w-full px-8 text-sm font-semibold sm:w-auto"
              onClick={() => navigate("/chat")}
            >
              Get Started
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="w-full px-8 text-sm font-semibold sm:w-auto"
              onClick={scrollToFeatures}
            >
              Learn More
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="border-t border-border bg-secondary/40 px-4 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <h2 className="mb-3 text-3xl font-bold tracking-tight text-foreground">
              Everything you need
            </h2>
            <p className="text-base text-muted-foreground">
              Designed to make university life simpler and smarter.
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
            © 2025 HUST Assistant. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
