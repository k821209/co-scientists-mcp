import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Projects } from "./pages/Projects";
import { ProjectShell } from "./pages/ProjectShell";
import { ProjectPapers } from "./pages/ProjectPapers";
import { ProjectPresentations } from "./pages/ProjectPresentations";
import { ProjectRuns } from "./pages/ProjectRuns";
import { ProjectSetup } from "./pages/ProjectSetup";
import { Account } from "./pages/Account";
import { Admin } from "./pages/Admin";

// Paper detail uses react-markdown + KaTeX (~300 KB). Lazy-load so the initial
// dashboard bundle doesn't pay for it — only loaded when a user opens a paper.
const Paper = lazy(() => import("./pages/Paper").then((m) => ({ default: m.Paper })));
const SharedPaper = lazy(() =>
  import("./pages/SharedPaper").then((m) => ({ default: m.SharedPaper })),
);

function Lazy({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Anonymous share link — NO RequireAuth; the page authenticates
          itself via /exchange_share_token. */}
      <Route
        path="/shared/:pid/:slug/:shareId"
        element={<Lazy><SharedPaper /></Lazy>}
      />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route index element={<Navigate to="/projects" replace />} />
                <Route path="projects" element={<Projects />} />

                {/* Paper detail — lazy-loaded (react-markdown + KaTeX) */}
                <Route
                  path="projects/:pid/papers/:slug"
                  element={<Lazy><Paper /></Lazy>}
                />

                {/* Project shell with tabs */}
                <Route path="projects/:pid" element={<ProjectShell />}>
                  <Route index element={<Navigate to="papers" replace />} />
                  <Route path="papers" element={<ProjectPapers />} />
                  <Route path="presentations" element={<ProjectPresentations />} />
                  <Route path="runs" element={<ProjectRuns />} />
                  <Route path="setup" element={<ProjectSetup />} />
                </Route>

                <Route path="account" element={<Account />} />
                <Route path="admin" element={<Admin />} />
              </Routes>
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
