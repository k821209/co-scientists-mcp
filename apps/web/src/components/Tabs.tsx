import { Link, useLocation } from "react-router-dom";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface TabDef {
  to: string;
  label: string;
  icon: LucideIcon;
}

export function TabBar({ tabs }: { tabs: TabDef[] }) {
  const location = useLocation();
  return (
    <nav className="-mx-1 flex flex-wrap items-end gap-1 border-b">
      {tabs.map((t) => {
        const Icon = t.icon;
        const active = location.pathname.startsWith(t.to);
        return (
          <Link
            key={t.to}
            to={t.to}
            className={cn(
              "inline-flex items-center gap-2 rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
