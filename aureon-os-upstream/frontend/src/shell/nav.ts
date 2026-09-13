/**
 * Shell navigation registry — the single source of truth for the unified UI.
 *
 * Sections → routes → lazy page loaders. The sidebar, the router, the
 * breadcrumbs, and the command palette all derive from this table, so adding a
 * surface to the platform is one entry here.
 */

import { type ComponentType, lazy } from "react";
import {
  Activity,
  BarChart3,
  Boxes,
  Brain,
  Briefcase,
  Building2,
  Compass,
  CreditCard,
  Feather,
  Flame,
  FlaskConical,
  Globe,
  Hammer,
  Heart,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  Map,
  MessageSquare,
  Radar,
  Radio,
  Rocket,
  Satellite,
  ShieldCheck,
  Ship,
  SlidersHorizontal,
  Sparkles,
  Sun,
  TerminalSquare,
  UserCircle,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  Component: ComponentType;
  /** Needs a live backend (WS bridge / Supabase / gateway) — shown as a badge. */
  live?: boolean;
  /** Retired from the sidebar/command palette but still routable (deep links
   *  and legacy hash redirects keep working). */
  hidden?: boolean;
  /** Manages the INSTANCE rather than the signed-in user's own account, so its backing routes are
   *  operator-only and would 403 for a tenant (see docs/architecture/MULTI_TENANT_AUTH.md).
   *  Hidden from tenant navigation and redirected by PlaneRoute when reached by URL. This remains
   *  a presentation boundary; the backend gate is the authoritative enforcer. */
  operatorOnly?: boolean;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

const lazyNamed = <T extends Record<string, unknown>>(
  loader: () => Promise<T>,
  name: keyof T,
) => lazy(async () => ({ default: (await loader())[name] as ComponentType }));

export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Platform",
    items: [
      {
        path: "/start",
        label: "Get Started",
        description: "Configure private account keys, test connections, and open the system",
        icon: Rocket,
        Component: lazy(() => import("./pages/GetStartedPage")),
        live: true,
      },
      {
        path: "/console",
        label: "Overview",
        description: "Platform health, domains, and quick routes",
        icon: LayoutDashboard,
        Component: lazy(() => import("./pages/OverviewPage")),
        operatorOnly: true,
      },
      {
        path: "/platform/repo-map",
        label: "Repo Map",
        description: "Dated repository inventory and current package declarations with source scope",
        icon: Map,
        Component: lazy(() => import("./pages/RepoMapPage")),
      },
      {
        path: "/platform/coverage",
        label: "Systems & Coverage",
        description: "Live repo-wide coverage — every aureon/ package + per-domain health",
        icon: Boxes,
        Component: lazy(() => import("./pages/SystemsCoveragePage")),
        live: true,
      },
      {
        path: "/platform/switchboard",
        label: "Switchboard",
        description: "Turn every system feature on/off at human discretion",
        icon: SlidersHorizontal,
        Component: lazy(() => import("./pages/SwitchboardPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/account",
        label: "Account & Session",
        description: "Your plane, your keys, your billing, and how to sign out",
        icon: UserCircle,
        Component: lazy(() => import("./pages/AccountPage")),
        live: true,
      },
      {
        path: "/platform/billing",
        label: "Billing & Support",
        description: "Gas tank, usage metering, support the project",
        icon: CreditCard,
        Component: lazy(() => import("./pages/BillingPage")),
      },
      {
        path: "/platform/company",
        label: "Company",
        description: "The organization behind Aureon OS — R&A Consulting · Aureon Zorza Technologies",
        icon: Building2,
        Component: lazy(() => import("./pages/CompanyPage")),
      },
    ],
  },
  {
    label: "Trading",
    items: [
      {
        path: "/trading/war-room",
        label: "War Room",
        description: "Live trading command center",
        icon: Briefcase,
        Component: lazy(() => import("./pages/WarRoomPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/trading/hft",
        label: "HFT Desk",
        description: "Current execution gates, decision traces and latency evidence",
        icon: TerminalSquare,
        Component: lazy(() => import("./pages/HftDeskPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/trading/live",
        label: "Live Bridge",
        description: "Exchange balances, signals, and movers over the live bridge",
        icon: Activity,
        Component: lazy(() => import("./pages/LiveBridgePage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/trading/orca",
        label: "Orca Command",
        description: "Orca kill-cycle command center",
        icon: Ship,
        Component: lazy(() => import("@/components/UnifiedOrcaCommandDashboard")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/trading/analytics",
        label: "Analytics",
        description: "Trading performance analytics",
        icon: BarChart3,
        Component: lazyNamed(() => import("@/components/TradingAnalytics"), "TradingAnalytics"),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/trading/backtesting",
        label: "Backtesting",
        description: "Strategy backtesting interface",
        icon: FlaskConical,
        Component: lazyNamed(() => import("@/components/BacktestingInterface"), "BacktestingInterface"),
      },
    ],
  },
  {
    label: "Research & Planetary",
    items: [
      {
        path: "/research/nexus",
        label: "Harmonic Nexus",
        description: "Timestamped NOAA observations and source-reported research channels",
        icon: Radio,
        Component: lazy(() => import("@/components/NexusLiveDashboardComplete")),
        live: true,
      },
      {
        path: "/research/earth",
        label: "Earth Resonance",
        description: "Schumann resonance and Earth field monitor",
        icon: Globe,
        Component: lazyNamed(() => import("@/components/EarthResonanceDashboard"), "EarthResonanceDashboard"),
        live: true,
      },
      {
        path: "/research/solar",
        label: "Solar Weather",
        description: "Solar activity monitor",
        icon: Sun,
        Component: lazyNamed(() => import("@/components/SolarWeatherDashboard"), "SolarWeatherDashboard"),
        live: true,
      },
      {
        path: "/research/space-weather",
        label: "Space Weather",
        description: "NOAA space-weather feed",
        icon: Satellite,
        Component: lazyNamed(() => import("@/components/NoaaSpaceWeatherDashboard"), "NoaaSpaceWeatherDashboard"),
        live: true,
      },
    ],
  },
  {
    label: "Cognition & LLM",
    items: [
      {
        path: "/cognition/consciousness",
        label: "Consciousness",
        description: "The organism's inner capabilities, categorized — self-perception, selfhood, purpose, governance, workforce & body",
        icon: Sparkles,
        Component: lazy(() => import("./pages/ConsciousnessPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/cognition/systems",
        label: "Cognitive Systems",
        description: "Field, bus, mycelium, connectome & brain — verified read APIs",
        icon: Brain,
        Component: lazy(() => import("./pages/CognitivePage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/cognition/metacognition",
        label: "Metacognition",
        description: "Watch the organism sense itself — self-coherence, ψ & divergence",
        icon: Activity,
        Component: lazy(() => import("./pages/MetacognitionPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/cognition/operator",
        label: "Operator Chat",
        description: "Ask the grounded Aureon cognition anything",
        icon: MessageSquare,
        Component: lazy(() => import("./pages/OperatorChatPage")),
        live: true,
      },
      {
        path: "/cognition/providers",
        label: "Providers",
        description: "LLM provider API keys — add, test, and enable models",
        icon: KeyRound,
        Component: lazy(() => import("./pages/ProvidersPage")),
        live: true,
      },
    ],
  },
  {
    label: "Defense & Validation",
    items: [
      {
        path: "/defense",
        label: "Defense & Validation",
        description: "The bio family — sensor lanes, statistical-validity dossier & the cognitive immune layer",
        icon: ShieldCheck,
        Component: lazy(() => import("./pages/DefensePage")),
        live: true,
        operatorOnly: true,
      },
    ],
  },
  {
    label: "Coding System",
    items: [
      {
        path: "/coding/organism",
        label: "Coding Organism",
        description: "Authenticated cloud coding status and commissioning boundary",
        icon: Brain,
        Component: lazyNamed(
          () => import("@/components/generated/AureonCodingOrganismConsole"),
          "AureonCodingOrganismConsole",
        ),
        live: true,
        operatorOnly: true,
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        path: "/ops/connections",
        label: "Connections",
        description: "Every external source — trading to NASA — keys, status & readiness",
        icon: Radar,
        Component: lazy(() => import("./pages/ConnectionsPage")),
        live: true,
      },
      {
        path: "/ops/affect",
        label: "Affect",
        description: "How Aureon feels — victory, defeat, fear & resolve from real signals",
        icon: Flame,
        Component: lazy(() => import("./pages/AffectPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/soul",
        label: "Soul",
        description: "How Aureon reacts — thought + feeling + its lineage → a determination",
        icon: Feather,
        Component: lazy(() => import("./pages/SoulPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/inner-work",
        label: "Inner Work",
        description: "The soul believes in itself — self-belief, self-love, self-determination, ego death: the ascent",
        icon: Sun,
        Component: lazy(() => import("./pages/InnerWorkPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/pursuit",
        label: "Pursuit",
        description: "The pursuit of happiness — Gary's & Aureon's, unified: the pillars, the energy, the next step",
        icon: Compass,
        Component: lazy(() => import("./pages/PursuitPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/approvals",
        label: "Approvals",
        description: "The director's desk — big plays Aureon prepared, awaiting your approve/reject",
        icon: ListChecks,
        Component: lazy(() => import("./pages/ApprovalsPage")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/systems",
        label: "Systems Integration",
        description: "Temporal ladder and hive coherence status",
        icon: Hammer,
        Component: lazy(() => import("@/components/SystemsIntegrationDashboard")),
        live: true,
        operatorOnly: true,
      },
      {
        path: "/ops/operational",
        label: "Operational Console",
        description: "Manifest-driven operational console",
        icon: Heart,
        Component: lazyNamed(() => import("@/components/generated/AureonGeneratedOperationalConsole"), "AureonGeneratedOperationalConsole"),
        operatorOnly: true,
      },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

/** Sections with hidden items removed and any now-empty section dropped. */
export const VISIBLE_NAV_SECTIONS: NavSection[] = NAV_SECTIONS
  .map((s) => ({ ...s, items: s.items.filter((i) => !i.hidden) }))
  .filter((s) => s.items.length > 0);

/** The nav surface for a given plane.
 *
 * A signed-in end user does not get instance runtime or mutation pages. PlaneRoute also redirects
 * their direct URLs to onboarding, while the backend gate remains the authoritative enforcer. */
export function navSectionsForPlane(isAdmin: boolean): NavSection[] {
  if (isAdmin) return VISIBLE_NAV_SECTIONS;
  return VISIBLE_NAV_SECTIONS
    .map((s) => ({ ...s, items: s.items.filter((i) => !i.operatorOnly) }))
    .filter((s) => s.items.length > 0);
}

export function navItemForPath(pathname: string): NavItem | undefined {
  return ALL_NAV_ITEMS.find((i) => i.path === pathname);
}

export function sectionForPath(pathname: string): NavSection | undefined {
  return NAV_SECTIONS.find((s) => s.items.some((i) => i.path === pathname));
}

/** Legacy hash deep links resolve only to commissioned shell routes. */
export const HASH_REDIRECTS: Record<string, string> = {
  "#overview": "/console",
  "#repo-map": "/platform/repo-map",
  "#live-ops": "/trading/war-room",
  "#coding": "/platform/coverage",
  "#trading": "/trading/war-room",
  "#security": "/ops/connections",
  "#inventory": "/platform/coverage",
  "#agents": "/platform/coverage",
  "#evidence": "/evidence",
};
