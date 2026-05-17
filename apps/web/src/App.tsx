import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Projects } from "./pages/Projects";
import { ProjectShell } from "./pages/ProjectShell";
import { ProjectPapers } from "./pages/ProjectPapers";
import { ProjectPresentations } from "./pages/ProjectPresentations";
import { ProjectSetup } from "./pages/ProjectSetup";
import { Paper } from "./pages/Paper";
import { Account } from "./pages/Account";
import { Admin } from "./pages/Admin";

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
      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route index element={<Navigate to="/projects" replace />} />
                <Route path="projects" element={<Projects />} />

                {/* Paper detail — outside the tab shell, has its own layout */}
                <Route path="projects/:pid/papers/:slug" element={<Paper />} />

                {/* Project shell with tabs */}
                <Route path="projects/:pid" element={<ProjectShell />}>
                  <Route index element={<Navigate to="papers" replace />} />
                  <Route path="papers" element={<ProjectPapers />} />
                  <Route path="presentations" element={<ProjectPresentations />} />
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
