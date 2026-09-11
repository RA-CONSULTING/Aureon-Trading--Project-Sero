/** A recent operator configuration receipt; it does not assert provider health. */
import { useEffect, useState } from "react";
import { useOperatorPulse } from "@/hooks/useOperatorPulse";
import { readOperatorConfiguration } from "@/lib/operatorConfiguration";

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums text-foreground">{value}</span>
    </span>
  );
}

export function LiveVitals() {
  const receipt = useOperatorPulse();
  const [, refreshAge] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => refreshAge((value) => value + 1), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  const items = readOperatorConfiguration(receipt);
  if (items.length === 0) return null;

  return (
    <div
      className="hidden items-center gap-3 text-xs lg:flex"
      title={`Operator configuration snapshot · received ${new Date(receipt.lastOkAt!).toISOString()} (GET /api/pulse). Configured providers do not establish provider health.`}
      aria-label="recent operator configuration snapshot"
    >
      {items.map((it, i) => (
        <span key={it.label} className="flex items-center gap-3">
          {i > 0 && <span className="text-border">·</span>}
          <Pill label={it.label} value={it.value} />
        </span>
      ))}
    </div>
  );
}

export default LiveVitals;
