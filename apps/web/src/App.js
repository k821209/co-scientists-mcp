import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Projects } from "./pages/Projects";
import { ProjectPapers } from "./pages/ProjectPapers";
import { Paper } from "./pages/Paper";
import { Account } from "./pages/Account";
import { Admin } from "./pages/Admin";
function RequireAuth({ children }) {
    const { user, loading } = useAuth();
    if (loading) {
        return (_jsx("div", { className: "flex min-h-screen items-center justify-center text-sm text-muted-foreground", children: "Loading\u2026" }));
    }
    if (!user)
        return _jsx(Navigate, { to: "/login", replace: true });
    return _jsx(_Fragment, { children: children });
}
export default function App() {
    return (_jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(Login, {}) }), _jsx(Route, { path: "/*", element: _jsx(RequireAuth, { children: _jsx(Layout, { children: _jsxs(Routes, { children: [_jsx(Route, { index: true, element: _jsx(Navigate, { to: "/projects", replace: true }) }), _jsx(Route, { path: "projects", element: _jsx(Projects, {}) }), _jsx(Route, { path: "projects/:pid/papers", element: _jsx(ProjectPapers, {}) }), _jsx(Route, { path: "projects/:pid/papers/:slug", element: _jsx(Paper, {}) }), _jsx(Route, { path: "account", element: _jsx(Account, {}) }), _jsx(Route, { path: "admin", element: _jsx(Admin, {}) })] }) }) }) })] }));
}
