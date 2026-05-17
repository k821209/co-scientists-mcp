import { useAuth } from "@/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function Admin() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Admins only</CardTitle>
          <CardDescription>
            You don't have the <code>admin</code> custom claim on your Firebase user.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Manage users, grant subscriptions, view audit log.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Coming in next session</CardTitle>
          <CardDescription>
            For v0, grant subscriptions by editing <code>/users/&#123;uid&#125;.plan_id</code>{" "}
            directly in the Firebase Console.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Planned screens: Users list with inline plan editor · Plans CRUD · Audit log feed ·
          Bootstrap second admin via Firebase Admin SDK.
        </CardContent>
      </Card>
    </div>
  );
}
