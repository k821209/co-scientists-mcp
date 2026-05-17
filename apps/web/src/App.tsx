import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Projects } from "./pages/Projects";
import { ProjectPapers } from "./pages/ProjectPapers";
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
                <Route path="projects/:pid/papers" element={<ProjectPapers />} />
                <Route path="projects/:pid/papers/:slug" element={<Paper />} />
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
