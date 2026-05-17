import { useEffect, useState } from "react";
import {
  addDoc, collection, doc, limit, onSnapshot, orderBy, query, updateDoc,
} from "firebase/firestore";
import {
  Shield, Users, Clock, AlertTriangle, FolderOpen, UserCheck,
} from "lucide-react";
import { useAuth } from "@/auth";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface UserRow {
  id: string;
  email?: string;
  display_name?: string | null;
  plan_id?: string;
  plan_expires_at?: string | null;
  disabled?: boolean;
  created_at?: string;
  last_login_at?: string;
}

interface ProjectRow {
  id: string;
  name?: string;
  owner_uid?: string;
  plan_id?: string;
  created_at?: string;
}

interface AuditEntry {
  id: string;
  admin_uid?: string;
  admin_email?: string;
  action?: string;
  target_uid?: string | null;
  payload?: Record<string, unknown>;
  ts?: string | null;
}

const PLAN_OPTIONS = ["free", "pro", "enterprise"] as const;
type Plan = (typeof PLAN_OPTIONS)[number];


export function Admin() {
  const { isAdmin, user: me } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!isAdmin) return;
    const unsubU = onSnapshot(
      collection(db, "users"),
      (snap) => setUsers(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<UserRow, "id">) }))),
      (err) => setError(err.message),
    );
    const unsubP = onSnapshot(
      collection(db, "projects"),
      (snap) => setProjects(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<ProjectRow, "id">) }))),
      () => { /* swallow */ },
    );
    const unsubA = onSnapshot(
      query(collection(db, "admin_audit_log"), orderBy("ts", "desc"), limit(50)),
      (snap) => setAudit(snap.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<AuditEntry, "id">) }))),
      () => { /* swallow */ },
    );
    return () => { unsubU(); unsubP(); unsubA(); };
  }, [isAdmin]);

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-600" /> Admins only
          </CardTitle>
          <CardDescription>
            Your Firebase Auth identity doesn't carry the{" "}
            <code className="text-xs">admin: true</code> custom claim. Bootstrap
            with{" "}
            <code className="bg-muted px-1 py-0.5 text-xs">
              python scripts/grant_admin.py grant {"<your-email>"}
            </code>{" "}
            from the repo root (requires{" "}
            <code className="text-xs">GOOGLE_APPLICATION_CREDENTIALS</code> env
            var pointing at a service-account JSON), then sign out and sign
            back in to refresh your token.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const setPlan = async (uid: string, newPlan: Plan, currentPlan: string | undefined) => {
    if (newPlan === currentPlan) return;
    const now = new Date().toISOString();
    try {
      await updateDoc(doc(db, "users", uid), {
        plan_id: newPlan,
        plan_started_at: now,
      });
      await addDoc(collection(db, "admin_audit_log"), {
        admin_uid: me!.uid,
        admin_email: me!.email,
        action: "plan_change",
        target_uid: uid,
        payload: { from: currentPlan ?? "free", to: newPlan },
        ts: now,
      });
    } catch (err) {
      alert(`plan change failed: ${(err as Error).message}`);
    }
  };

  const setDisabled = async (uid: string, disabled: boolean) => {
    const now = new Date().toISOString();
    try {
      await updateDoc(doc(db, "users", uid), { disabled });
      await addDoc(collection(db, "admin_audit_log"), {
        admin_uid: me!.uid,
        admin_email: me!.email,
        action: disabled ? "user_disabled" : "user_enabled",
        target_uid: uid,
        payload: {},
        ts: now,
      });
    } catch (err) {
      alert(`status change failed: ${(err as Error).message}`);
    }
  };

  const lowerFilter = filter.toLowerCase();
  const filtered = filter
    ? users.filter((u) =>
        (u.email || "").toLowerCase().includes(lowerFilter)
        || (u.display_name || "").toLowerCase().includes(lowerFilter)
        || u.id.toLowerCase().includes(lowerFilter),
      )
    : users;

  // Counts per plan
  const planCounts = users.reduce((acc, u) => {
    const p = u.plan_id || "free";
    acc[p] = (acc[p] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <Shield className="h-6 w-6" /> Admin
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage user plans + audit log. Signed in as{" "}
          <code className="text-xs">{me?.email}</code>.
        </p>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {/* User table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" /> Users
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {users.length}
            </Badge>
          </CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-3">
            {PLAN_OPTIONS.map((p) => (
              <span key={p}>
                <code className="text-[10px]">{p}</code>: {planCounts[p] || 0}
              </span>
            ))}
          </CardDescription>
          <div className="pt-2">
            <Input
              placeholder="filter by email / display name / uid…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-2 py-2">Email</th>
                  <th className="px-2 py-2">Plan</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Last login</th>
                  <th className="px-2 py-2">Projects</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => {
                  const projCount = projects.filter((p) => p.owner_uid === u.id).length;
                  const isMe = u.id === me?.uid;
                  return (
                    <tr key={u.id} className="border-b last:border-0">
                      <td className="px-2 py-2">
                        <div className="flex items-baseline gap-2">
                          <span className="font-medium">{u.email || "—"}</span>
                          {isMe && (
                            <Badge variant="outline" className="text-[9px]">you</Badge>
                          )}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {u.display_name || u.id}
                        </div>
                      </td>
                      <td className="px-2 py-2">
                        <select
                          value={u.plan_id || "free"}
                          onChange={(e) => setPlan(u.id, e.target.value as Plan, u.plan_id)}
                          className={cn(
                            "h-7 rounded-md border bg-background px-2 text-xs",
                            u.plan_id === "pro" && "border-emerald-500",
                            u.plan_id === "enterprise" && "border-violet-500",
                          )}
                        >
                          {PLAN_OPTIONS.map((p) => (
                            <option key={p} value={p}>{p}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => setDisabled(u.id, !u.disabled)}
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-medium",
                            u.disabled
                              ? "bg-destructive text-destructive-foreground"
                              : "bg-emerald-100 text-emerald-800 hover:bg-emerald-200",
                          )}
                          title={u.disabled ? "Click to enable" : "Click to disable"}
                        >
                          {u.disabled ? "disabled" : "active"}
                        </button>
                      </td>
                      <td className="px-2 py-2 text-[10px] text-muted-foreground">
                        {u.last_login_at
                          ? new Date(u.last_login_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-2 py-2 text-[10px] text-muted-foreground">
                        <FolderOpen className="mr-1 inline h-3 w-3" />
                        {projCount}
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-4 text-center text-xs italic text-muted-foreground">
                      no users match filter
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Audit log */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-4 w-4" /> Audit log
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {audit.length}
            </Badge>
          </CardTitle>
          <CardDescription>
            Most recent 50 admin actions. Append-only — Firestore rules block updates and deletes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {audit.length === 0 ? (
            <p className="text-xs italic text-muted-foreground">No admin actions yet.</p>
          ) : (
            <div className="space-y-1.5">
              {audit.map((e) => (
                <div key={e.id} className="flex flex-wrap items-baseline gap-2 text-xs">
                  <UserCheck className="h-3 w-3 text-muted-foreground" />
                  <code className="text-[10px]" title={e.admin_uid}>
                    {e.admin_email || e.admin_uid?.slice(0, 8)}
                  </code>
                  <span className="font-medium">{e.action}</span>
                  {e.target_uid && (
                    <span className="text-muted-foreground">
                      → <code className="text-[10px]">{e.target_uid.slice(0, 8)}</code>
                    </span>
                  )}
                  {e.payload && Object.keys(e.payload).length > 0 && (
                    <code className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                      {JSON.stringify(e.payload)}
                    </code>
                  )}
                  {e.ts && (
                    <time
                      className="ml-auto text-[10px] text-muted-foreground"
                      dateTime={typeof e.ts === "string" ? e.ts : undefined}
                    >
                      {typeof e.ts === "string"
                        ? new Date(e.ts).toLocaleString()
                        : "—"}
                    </time>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
