import { useEffect, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import { useAuth } from "@/auth";
import { db } from "@/firebase";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function Account() {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!user) return;
    return onSnapshot(doc(db, "users", user.uid), (snap) => setProfile(snap.data() ?? null));
  }, [user]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Account</h1>
        <p className="text-sm text-muted-foreground">
          Manage your profile, subscription, and compute servers.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Email</span>
            <span>{user.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">User ID</span>
            <span className="font-mono text-xs">{user.uid}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Display name</span>
            <span>{(profile?.display_name as string) ?? user.displayName ?? "—"}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
          <CardDescription>
            Plan changes are made by an admin — contact us to upgrade.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Plan</span>
            <span>{(profile?.plan_id as string) ?? "free"}</span>
          </div>
          {profile?.plan_expires_at != null && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Expires</span>
              <span>{String(profile.plan_expires_at)}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Compute servers</CardTitle>
          <CardDescription>
            Coming soon — manage your registered HPC nodes here. For v0 use the MCP tools
            <code className="ml-1 text-xs">add_server</code> /<code className="ml-1 text-xs">list_servers</code>.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Danger zone</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={signOut}>
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
