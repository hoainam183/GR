import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import { getStoredUser } from "@/services/authStorage";

const queryClient = new QueryClient();

/** Guard: only render children if JWT user has role === "admin" */
function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = getStoredUser<{ role?: string }>();
  if (user?.role === "admin") return <>{children}</>;
  return <Navigate to="/chat" replace />;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/chat" element={<Index />} />
          <Route path="/chat/:sessionId" element={<Index />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/complete-profile" element={<CompleteProfile />} />
          <Route path="/trace" element={<AdminGuard><TracePage /></AdminGuard>} />
          <Route path="/retrieval" element={<AdminGuard><RetrievalPage /></AdminGuard>} />
          <Route path="/eval" element={<AdminGuard><EvalPage /></AdminGuard>} />
          <Route path="/admin" element={<AdminGuard><AdminPage /></AdminGuard>} />
          <Route path="/admin/documents/:id" element={<AdminGuard><DocumentReview /></AdminGuard>} />
          <Route path="/bookmarks" element={<BookmarksPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
