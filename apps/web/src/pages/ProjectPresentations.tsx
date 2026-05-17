import { Presentation } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ProjectPresentations() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Presentation className="h-5 w-5" /> Presentations
        </CardTitle>
        <CardDescription>
          Build slide decks from your papers using the{" "}
          <code className="bg-muted px-1 py-0.5 text-xs">/paper-deck</code> skill
          in Claude Code.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <p>
          Coming soon: per-paper deck list with PNG thumbnails, theme picker,
          and a Download <code className="text-xs">.pptx</code> button — fed by
          the deck-pipeline tools in the local MCP (port pending — see the open
          item list in the repo).
        </p>
        <p>
          For now the deck tools aren't wired in this build. Once the{" "}
          <code className="text-xs">paper-deck</code> skill is ported to the
          cloud schema, decks created in Claude Code will appear here
          automatically — same pattern as Papers.
        </p>
      </CardContent>
    </Card>
  );
}
