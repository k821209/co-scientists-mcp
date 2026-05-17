import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Folder, User, Shield, LogOut } from "lucide-react";
import { useAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
const NAV = [
    { to: "/projects", label: "Projects", icon: Folder },
    { to: "/account", label: "Account", icon: User },
];
export function Layout({ children }) {
    const [open, setOpen] = useState(false);
    const { user, isAdmin, signOut } = useAuth();
    const location = useLocation();
    const items = [...NAV, ...(isAdmin ? [{ to: "/admin", label: "Admin", icon: Shield }] : [])];
    return (_jsxs("div", { className: "flex min-h-screen bg-background", children: [_jsxs("div", { className: "md:hidden fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-4", children: [_jsx(Button, { variant: "ghost", size: "icon", onClick: () => setOpen(!open), "aria-label": "menu", children: open ? _jsx(X, { className: "h-5 w-5" }) : _jsx(Menu, { className: "h-5 w-5" }) }), _jsx("span", { className: "font-semibold", children: "co-scientist" }), _jsx("div", { className: "w-10" })] }), _jsxs("aside", { className: cn("fixed inset-y-0 left-0 z-20 w-64 transform border-r bg-background transition-transform", "md:translate-x-0 md:static md:shrink-0", open ? "translate-x-0" : "-translate-x-full"), children: [_jsx("div", { className: "hidden md:flex h-14 items-center border-b px-6", children: _jsx("span", { className: "font-semibold", children: "co-scientist" }) }), _jsxs("nav", { className: "flex flex-col gap-1 p-4 pt-20 md:pt-4", children: [items.map((item) => {
                                const Icon = item.icon;
                                const active = location.pathname.startsWith(item.to);
                                return (_jsxs(Link, { to: item.to, onClick: () => setOpen(false), className: cn("flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors", active
                                        ? "bg-accent text-accent-foreground"
                                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"), children: [_jsx(Icon, { className: "h-4 w-4" }), item.label] }, item.to));
                            }), _jsx("div", { className: "mt-auto pt-4", children: user && (_jsxs("div", { className: "space-y-2 px-3 py-2 text-xs text-muted-foreground", children: [_jsx("div", { className: "truncate", children: user.email || user.displayName }), _jsxs(Button, { variant: "outline", size: "sm", className: "w-full", onClick: signOut, children: [_jsx(LogOut, { className: "mr-2 h-4 w-4" }), " Sign out"] })] })) })] })] }), _jsx("main", { className: "flex-1 pt-14 md:pt-0", children: _jsx("div", { className: "container mx-auto p-4 md:p-8", children: children }) })] }));
}
