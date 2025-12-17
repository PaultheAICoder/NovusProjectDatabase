/**
 * Root application component with router and providers.
 */

import { lazy, Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import { Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { queryClient } from "@/lib/api";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { Header, Sidebar, Footer } from "@/components/layout";
import { Toaster } from "@/components/ui/toaster";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// Lazy load page components for code splitting
const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const ProjectsPage = lazy(() =>
  import("@/pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage }))
);
const ProjectDetailPage = lazy(() =>
  import("@/pages/ProjectDetailPage").then((m) => ({ default: m.ProjectDetailPage }))
);
const ProjectFormPage = lazy(() =>
  import("@/pages/ProjectFormPage").then((m) => ({ default: m.ProjectFormPage }))
);
const SearchPage = lazy(() =>
  import("@/pages/SearchPage").then((m) => ({ default: m.SearchPage }))
);
const AdminPage = lazy(() =>
  import("@/pages/AdminPage").then((m) => ({ default: m.AdminPage }))
);
const ImportPage = lazy(() =>
  import("@/pages/ImportPage").then((m) => ({ default: m.ImportPage }))
);
const OrganizationsPage = lazy(() =>
  import("@/pages/OrganizationsPage").then((m) => ({ default: m.OrganizationsPage }))
);
const OrganizationDetailPage = lazy(() =>
  import("@/pages/OrganizationDetailPage").then((m) => ({
    default: m.OrganizationDetailPage,
  }))
);
const ContactsPage = lazy(() =>
  import("@/pages/ContactsPage").then((m) => ({ default: m.ContactsPage }))
);
const ContactDetailPage = lazy(() =>
  import("@/pages/ContactDetailPage").then((m) => ({
    default: m.ContactDetailPage,
  }))
);

/**
 * Protected route wrapper.
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * Loading spinner for lazy-loaded routes.
 */
function PageLoader() {
  return (
    <div className="flex min-h-[400px] items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

/**
 * Main layout with header and sidebar.
 */
function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-6 pb-12">{children}</main>
      </div>
      <Footer />
    </div>
  );
}

/**
 * Enhanced error message configuration for login errors.
 */
interface ErrorMessageConfig {
  title: string;
  description: string;
  tip?: string;
  showRetry: boolean;
  showContactSupport: boolean;
}

const errorConfigs: Record<string, ErrorMessageConfig> = {
  token_exchange_failed: {
    title: "Authentication Failed",
    description: "We couldn't complete the sign-in process with Azure AD.",
    tip: "This may be a temporary issue. Please wait a moment and try again.",
    showRetry: true,
    showContactSupport: true,
  },
  no_id_token: {
    title: "Authentication Failed",
    description: "The authentication response was incomplete.",
    tip: "Try signing in again. If the problem persists, contact support.",
    showRetry: true,
    showContactSupport: true,
  },
  invalid_token: {
    title: "Invalid Authentication",
    description: "The authentication response could not be verified.",
    tip: "Clear your browser cookies and try signing in again.",
    showRetry: true,
    showContactSupport: true,
  },
  invalid_state: {
    title: "Session Expired",
    description: "Your sign-in session has expired or was interrupted.",
    tip: "This can happen if you waited too long or opened multiple tabs.",
    showRetry: true,
    showContactSupport: false,
  },
  token_expired: {
    title: "Session Expired",
    description: "Your authentication session has expired.",
    tip: "Please sign in again to continue.",
    showRetry: true,
    showContactSupport: false,
  },
  missing_user_info: {
    title: "Missing Account Information",
    description: "We couldn't retrieve your user information from Azure AD.",
    tip: "Contact your IT administrator if your Azure AD profile is incomplete.",
    showRetry: true,
    showContactSupport: true,
  },
  domain_not_allowed: {
    title: "Access Denied",
    description: "Your email domain is not authorized to access this application.",
    tip: "Only users with approved company email addresses can sign in.",
    showRetry: false,
    showContactSupport: true,
  },
};

const defaultErrorConfig: ErrorMessageConfig = {
  title: "Sign-In Error",
  description: "An unexpected error occurred during sign-in.",
  tip: "Please try again. If the problem continues, contact support.",
  showRetry: true,
  showContactSupport: true,
};

const SUPPORT_EMAIL = "support@novus-db.com";

function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");

  const errorConfig = error ? (errorConfigs[error] || defaultErrorConfig) : null;

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Novus Project Database</h1>
          <p className="mt-2 text-muted-foreground">Sign in to continue</p>
          {errorConfig && (
            <Alert variant="destructive" className="mt-4 max-w-md mx-auto text-left">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{errorConfig.title}</AlertTitle>
              <AlertDescription>
                <p>{errorConfig.description}</p>
                {errorConfig.tip && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {errorConfig.tip}
                  </p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  {errorConfig.showRetry && (
                    <Button variant="outline" size="sm" onClick={login}>
                      <RefreshCw className="mr-2 h-3 w-3" />
                      Try Again
                    </Button>
                  )}
                  {errorConfig.showContactSupport && (
                    <Button variant="ghost" size="sm" asChild>
                      <a href={`mailto:${SUPPORT_EMAIL}`}>Contact Support</a>
                    </Button>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}
          <button
            onClick={login}
            className="mt-4 rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
          >
            Sign in with Azure AD
          </button>
        </div>
      </div>
      <Footer />
    </div>
  );
}

/**
 * Application routes.
 */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <DashboardPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ProjectsPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/new"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ProjectFormPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ProjectDetailPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id/edit"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ProjectFormPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/organizations"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <OrganizationsPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/organizations/:id"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <OrganizationDetailPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/contacts"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ContactsPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/contacts/:id"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ContactDetailPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/search"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <SearchPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/import"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <ImportPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Suspense fallback={<PageLoader />}>
                <AdminPage />
              </Suspense>
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/**
 * Root App component.
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
