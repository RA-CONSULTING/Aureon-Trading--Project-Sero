import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { runtimeCount, runtimeSourceFresh, type RuntimeSourceObservation } from "@/lib/runtimeSourceStatus";

/** Software producers retain their own observation clock, including between HTTP reads. */
export function RuntimeSourcesPanel({ sources, error }: {
  sources?: Record<string, RuntimeSourceObservation>; error?: string | null;
}) {
  const rows = Object.entries(sources ?? {});
  const now = Date.now();
  return <Card>
    <CardHeader>
      <CardTitle className="text-base">Published runtime observations</CardTitle>
      <CardDescription>Queen and HNC publish these software measurements independently of this page. Each source expires on its own clock.</CardDescription>
    </CardHeader>
    <CardContent className="space-y-3">
      {!rows.length && <p className="text-sm text-muted-foreground">{error || "No current producer observations received."}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map(([name, source]) => {
          const fresh = runtimeSourceFresh(source, now);
          const stamp = source.source_timestamp;
          const time = typeof stamp === "number" && Number.isFinite(stamp) && stamp > 0
            ? new Date(stamp * 1000).toISOString() : null;
          return <div key={name} className="space-y-2 rounded-md border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{name.replaceAll("_", " ")}</span>
              <Badge variant="outline">{fresh ? "Current observation" : "No current observation"}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">{time ? `Source time: ${time}` : "Producer timestamp unavailable"}</p>
            {fresh ? <div className="flex flex-wrap gap-4 text-sm">
              {source.cycle != null && <span>Cycle <b>{runtimeCount(source.cycle)}</b></span>}
              {source.step != null && <span>Step <b>{runtimeCount(source.step)}</b></span>}
              {source.input_count != null && <span>Inputs <b>{runtimeCount(source.input_count)}</b></span>}
            </div> : <p className="text-xs text-muted-foreground">{source.reason || "The source is missing, expired, or could not be verified."}</p>}
            <p className="text-[11px] text-muted-foreground">Software runtime evidence; functional results are verified in each system's view.</p>
          </div>;
        })}
      </div>
    </CardContent>
  </Card>;
}
