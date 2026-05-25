import { useEffect, useState } from "react";
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

function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [user, setUser] = useState<UserPublic | null>(() => getCurrentSessionUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    ensureSession()
      .then((sessionUser) => {
        if (!cancelled) setUser(sessionUser);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search]);

  if (loading) return null;
  if (!user) return <Navigate to={loginRedirect(location.pathname, location.search)} replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [user, setUser] = useState<UserPublic | null>(() => getCurrentSessionUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    ensureSession()
      .then((sessionUser) => {
        if (!cancelled) setUser(sessionUser);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search]);

  if (loading) return null;
  if (!user) return <Navigate to={loginRedirect(location.pathname, location.search)} replace />;
  if (user.role !== "admin") return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
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
