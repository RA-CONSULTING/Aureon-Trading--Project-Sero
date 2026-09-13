/**
 * SupportProjectPrompt — the non-intrusive "support the project" card.
 *
 * A small dismissible corner card (never a modal; the console is never
 * blocked). Shown only when useSupportProject says a prompt is due. Opens the
 * SumUp support link in a new tab. Account credit is deliberately absent here:
 * only a provider-verified server receipt may change a user's balance.
 */

import { useState } from "react";
import { Heart, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useSupportProject } from "@/hooks/useSupportProject";

export function SupportProjectPrompt() {
  const { due, runtimeHours, snooze, thank, links } = useSupportProject();
  const [opened, setOpened] = useState(false);

  if (!due || links.length === 0) return null;

  const supportUrl = links[0];

  const openLink = () => {
    window.open(supportUrl, "_blank", "noopener,noreferrer");
    setOpened(true);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-sm">
      <Card className="border-border/60 shadow-lg">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Heart className="h-4 w-4 text-primary shrink-0" />
              <p className="text-sm font-medium">Enjoying Aureon?</p>
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={snooze}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            Aureon is free to run — you&apos;ve clocked ~{Math.floor(runtimeHours)}h with it.
            If it&apos;s earning its keep, consider supporting the project.
          </p>
          {!opened ? (
            <div className="flex gap-2">
              <Button size="sm" className="flex-1" onClick={openLink}>
                Support the project
              </Button>
              <Button size="sm" variant="ghost" onClick={snooze}>
                Maybe later
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Thank you. SumUp processes the payment. Aureon does not credit a balance
                until a provider-verified receipt is available.
              </p>
              <div className="flex gap-2">
                <Button size="sm" onClick={thank}>
                  Done
                </Button>
                <Button size="sm" variant="ghost" onClick={snooze}>
                  Skip
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
