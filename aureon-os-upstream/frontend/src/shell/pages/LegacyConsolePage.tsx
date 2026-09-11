/**
 * The original nine-tab operational console, preserved intact inside the
 * unified shell. Its hash-tab navigation (#trading, #inventory, …) keeps
 * working within this route.
 */

import { LegacyConsole } from "@/App";
import { PanelsTopLeft } from "lucide-react";
import { GlassPageHeader } from "@/shell/GlassPage";

export default function LegacyConsolePage() {
  return <div className="space-y-6">
    <GlassPageHeader icon={PanelsTopLeft} eyebrow="Operational workspace" title="Legacy Console"
      description="The original operating tabs, with their existing data sources and controls." />
    <LegacyConsole />
  </div>;
}
