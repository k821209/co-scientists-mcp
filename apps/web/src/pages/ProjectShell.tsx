import { useEffect, useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { doc, onSnapshot } from "firebase/firestore";
import { ArrowLeft, FileText, Presentation, Settings, Activity } from "lucide-react";
import { db } from "@/firebase";
import { TabBar } from "@/components/Tabs";

export interface Project {
  name: string;
  description?: string;
  plan_id?: string;
  owner_uid?: string;
  api_key?: string;
  api_key_created_at?: string;
}

export interface ProjectContext {
  pid: string;
  project: Project | null;
}

export function ProjectShell() {
  const { pid } = useParams<{ pid: string }>();
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    if (!pid) return;
    return onSnapshot(doc(db, "projects", pid), (snap) => {
      setProject((snap.data() as Project) ?? null);
    });
  }, [pid]);

  if (!pid) return null;

  const tabs = [
    { to: `/projects/${pid}/papers`,        label: "Paper",         icon: FileText },
    { to: `/projects/${pid}/presentations`, label: "Presentation",  icon: Presentation },
    { to: `/projects/${pid}/runs`,          label: "Runs",          icon: Activity },
    { to: `/projects/${pid}/setup`,         label: "Setup guide",   icon: Settings },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/projects"
          className="-ml-3 inline-flex h-9 items-center rounded-md px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> All projects
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">
          {project?.name || pid}
        </h1>
        {project?.description && (
          <p className="text-sm text-muted-foreground">{project.description}</p>
        )}
      </div>

      <TabBar tabs={tabs} />

      <Outlet context={{ pid, project } satisfies ProjectContext} />
    </div>
  );
}
