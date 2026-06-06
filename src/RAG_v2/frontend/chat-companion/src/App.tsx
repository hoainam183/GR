import { useEffect, useState, useRef } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import CompleteProfile from "./pages/CompleteProfile";
import TracePage from "./pages/TracePage";
import RetrievalPage from "./pages/RetrievalPage";
import EvalPage from "./pages/EvalPage";
import AdminPage from "./pages/AdminPage";
import DocumentReview from "./pages/DocumentReview";
import BookmarksPage from "./pages/BookmarksPage";
import NotificationsPage from "./pages/NotificationsPage";
import { ensureSession, getCurrentSessionUser } from "@/services/authSession";
import type { UserPublic } from "@/services/authApi";

const queryClient = new QueryClient();

const loginRedirect = (pathname: string, search: string) =>
  `/login?next=${encodeURIComponent(`${pathname}${search}`)}`;

/**
 * Renders children if the user has an active session.
 *
 * Strategy:
 * - If a user is already cached in localStorage, render children immediately
 *   (optimistic) while the session is being verified in the background.
 * - If no cached user, render a blank screen until the first check resolves.
 * - Only redirect to /login once we know for certain there is no valid session.
 * - The session check runs once on mount; subsequent navigations within a
 *   protected subtree do NOT trigger a new network round-trip.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [user, setUser] = useState<UserPublic | null>(() => getCurrentSessionUser());
  // Start in "checking" only when there is no cached user to show immediately.
  const [checking, setChecking] = useState(() => getCurrentSessionUser() === null);
  const verified = useRef(false);

  useEffect(() => {
    // Already verified in this component lifetime — skip on subsequent renders.
    if (verified.current) return;
    verified.current = true;

    ensureSession()
      .then((sessionUser) => {
        setUser(sessionUser);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => {
        setChecking(false);
      });
  }, []);

  // Show nothing only while the very first check is in flight AND there is
  // no cached user to render behind it.
  if (checking) return null;
  if (!user) return <Navigate to={loginRedirect(location.pathname, location.search)} replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [user, setUser] = useState<UserPublic | null>(() => getCurrentSessionUser());
  const [checking, setChecking] = useState(() => getCurrentSessionUser() === null);
  const verified = useRef(false);

  useEffect(() => {
    if (verified.current) return;
    verified.current = true;

    ensureSession()
      .then((sessionUser) => {
        setUser(sessionUser);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => {
        setChecking(false);
      });
  }, []);

  if (checking) return null;
  if (!user) return <Navigate to={loginRedirect(location.pathname, location.search)} replace />;
  if (user.role !== "admin") return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/chat" element={<RequireAuth><Index /></RequireAuth>} />
          <Route path="/chat/:sessionId" element={<RequireAuth><Index /></RequireAuth>} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/complete-profile" element={<RequireAuth><CompleteProfile /></RequireAuth>} />
          <Route path="/trace" element={<RequireAdmin><TracePage /></RequireAdmin>} />
          <Route path="/retrieval" element={<RequireAdmin><RetrievalPage /></RequireAdmin>} />
          <Route path="/eval" element={<RequireAdmin><EvalPage /></RequireAdmin>} />
          <Route path="/admin" element={<RequireAdmin><AdminPage /></RequireAdmin>} />
          <Route path="/admin/documents/:id" element={<RequireAdmin><DocumentReview /></RequireAdmin>} />
          <Route path="/bookmarks" element={<RequireAuth><BookmarksPage /></RequireAuth>} />
          <Route path="/notifications" element={<RequireAuth><NotificationsPage /></RequireAuth>} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
