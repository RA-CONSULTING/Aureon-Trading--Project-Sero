import { isIP } from "node:net";
import type { IncomingMessage } from "node:http";
import type { Plugin, ProxyOptions, ResolvedConfig } from "vite";
import { AUTH_RESOLUTION_HEADER } from "../src/services/authResolution";

const AUTH_RESOLUTION_HEADER_LOWER = AUTH_RESOLUTION_HEADER.toLowerCase();

export type ProxyRequestDecision =
  | { allowed: true }
  | {
      allowed: false;
      reason:
        | "loopback_client_required"
        | "loopback_host_required"
        | "same_origin_required"
        | "cross_site_request_denied"
        | "caller_authorization_required";
    };

export type ProxyAuthorizationPolicy = "preserve-required" | "preserve-optional";

export interface ProxyAuthorizationConfig {
  policy: ProxyAuthorizationPolicy;
  /** Present only in explicit local-operator mode; already normalized as Bearer. */
  localOperatorBearer?: string;
}

export interface LoopbackProxyRouteOptions {
  rewrite?: (path: string) => string;
  authorization?: ProxyAuthorizationConfig;
}

function unwrapIpv6Brackets(value: string): string {
  return value.startsWith("[") && value.endsWith("]") ? value.slice(1, -1) : value;
}

/** Accept only names and addresses that cannot route off this machine. */
export function isLoopbackHost(value: string | undefined | null): boolean {
  if (!value) return false;
  if (value.trim() !== value) return false;
  const host = unwrapIpv6Brackets(value.toLowerCase());
  if (!host || host.includes("%")) return false;
  if (host === "localhost" || host === "::1" || host === "0:0:0:0:0:0:0:1") return true;
  if (host.startsWith("::ffff:")) return isLoopbackHost(host.slice("::ffff:".length));
  if (isIP(host) !== 4) return false;
  const firstOctet = Number(host.split(".", 1)[0]);
  return firstOctet === 127;
}

function singleHeader(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function requestOriginFromHost(hostHeader: string | undefined, encrypted: boolean): string | null {
  if (!hostHeader || hostHeader.length > 255 || hostHeader.trim() !== hostHeader) return null;
  if (/[\\/@?#,\s]/.test(hostHeader)) return null;
  try {
    const parsed = new URL(`${encrypted ? "https" : "http"}://${hostHeader}`);
    if (
      !isLoopbackHost(parsed.hostname) ||
      parsed.username ||
      parsed.password ||
      parsed.pathname !== "/" ||
      parsed.search ||
      parsed.hash
    ) {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

function suppliedOrigin(value: string | undefined): string | null {
  if (!value || value.length > 512 || value.trim() !== value) return null;
  try {
    const parsed = new URL(value);
    if (
      (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
      !isLoopbackHost(parsed.hostname) ||
      parsed.username ||
      parsed.password ||
      parsed.pathname !== "/" ||
      parsed.search ||
      parsed.hash
    ) {
      return null;
    }
    return parsed.origin;
  } catch {
    return null;
  }
}

function hasHeader(headers: IncomingMessage["headers"], name: string): boolean {
  return Object.hasOwn(headers, name.toLowerCase());
}

function hasValidatedSameOriginEvidence(req: Pick<IncomingMessage, "headers" | "socket">): boolean {
  const encrypted = Boolean((req.socket as IncomingMessage["socket"] & { encrypted?: boolean }).encrypted);
  const expectedOrigin = requestOriginFromHost(singleHeader(req.headers.host), encrypted);
  if (!expectedOrigin) return false;
  const originHeader = singleHeader(req.headers.origin);
  if (originHeader !== undefined) return suppliedOrigin(originHeader) === expectedOrigin;
  return singleHeader(req.headers["sec-fetch-site"]) === "same-origin";
}

/**
 * Decide whether a request may use the local Vite-to-operator bridge.
 *
 * Authorization is never parsed or rewritten here. Tenant mode checks only whether
 * the header is present; the exact value, including an invalid or empty bearer,
 * passes to the operator for identity resolution.
 */
export function inspectProxyRequest(
  req: Pick<IncomingMessage, "headers" | "socket">,
  authorization: ProxyAuthorizationPolicy = "preserve-optional",
): ProxyRequestDecision {
  if (!isLoopbackHost(req.socket.remoteAddress)) {
    return { allowed: false, reason: "loopback_client_required" };
  }

  const encrypted = Boolean((req.socket as IncomingMessage["socket"] & { encrypted?: boolean }).encrypted);
  const expectedOrigin = requestOriginFromHost(singleHeader(req.headers.host), encrypted);
  if (!expectedOrigin) {
    return { allowed: false, reason: "loopback_host_required" };
  }

  const fetchSite = singleHeader(req.headers["sec-fetch-site"]);
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
    return { allowed: false, reason: "cross_site_request_denied" };
  }

  const originHeader = singleHeader(req.headers.origin);
  if (originHeader !== undefined) {
    const origin = suppliedOrigin(originHeader);
    if (!origin || origin !== expectedOrigin) {
      return { allowed: false, reason: "same_origin_required" };
    }
  }

  if (authorization === "preserve-required") {
    if (!hasHeader(req.headers, "authorization")) {
      return { allowed: false, reason: "caller_authorization_required" };
    }
  }

  return { allowed: true };
}

export function createProxyRequestGuard(
  authorization: ProxyAuthorizationPolicy = "preserve-optional",
): NonNullable<ProxyOptions["bypass"]> {
  return (req, res) => {
    const decision = inspectProxyRequest(req, authorization);
    if (decision.allowed) return undefined;
    // Vite converts `false` to a local 404 without contacting the target. Keep the
    // response uncacheable and do not reflect attacker-controlled header values.
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    return false;
  };
}

function normalizeLocalOperatorBearer(value: string | undefined): string {
  const raw = (value ?? "").trim();
  if (!raw) throw new Error("aureon_local_operator_proxy_bearer_required");
  if (raw.length > 8_192 || /[\r\n]/.test(raw)) {
    throw new Error("aureon_local_operator_proxy_bearer_invalid");
  }
  const token = raw.toLowerCase().startsWith("bearer ") ? raw.slice(7).trim() : raw;
  if (!token || /\s/.test(token)) {
    throw new Error("aureon_local_operator_proxy_bearer_invalid");
  }
  return `Bearer ${token}`;
}

/** Validate a proxy target without ever including its value in an error or log. */
export function assertLoopbackProxyTarget(label: string, value: string): string {
  if (!value || value.trim() !== value) {
    throw new Error(`aureon_${label}_proxy_target_invalid`);
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`aureon_${label}_proxy_target_invalid`);
  }
  if (
    (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
    !isLoopbackHost(parsed.hostname) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(`aureon_${label}_proxy_target_must_be_loopback`);
  }
  return value;
}

/**
 * Construct the only supported proxy shape. It has no static `headers`, `auth`, or
 * `forward`; the sole server bearer path is the guarded, explicit local-operator
 * hook below, and target validation prevents it from reaching a remote host.
 */
export function createLoopbackProxyRoute(
  label: string,
  target: string,
  options: LoopbackProxyRouteOptions = {},
): ProxyOptions {
  const route: ProxyOptions = {
    target: assertLoopbackProxyTarget(label, target),
    changeOrigin: true,
    bypass: createProxyRequestGuard(options.authorization?.policy),
  };
  if (options.rewrite) route.rewrite = options.rewrite;
  const localOperatorBearer = options.authorization?.localOperatorBearer;
  route.configure = (proxy) => {
    proxy.on("proxyReq", (proxyReq, req) => {
      const authResolutionFailed = hasHeader(req.headers, AUTH_RESOLUTION_HEADER_LOWER);
      // This browser-only signal is consumed at ingress and never enters the operator.
      proxyReq.removeHeader(AUTH_RESOLUTION_HEADER);
      if (
        !localOperatorBearer ||
        hasHeader(req.headers, "authorization") ||
        authResolutionFailed ||
        !hasValidatedSameOriginEvidence(req)
      ) {
        return;
      }
      // The bypass guard already approved this request. Re-evaluate at the last
      // mile so a future proxy refactor cannot inject the bearer without proof.
      if (!inspectProxyRequest(req).allowed) return;
      proxyReq.setHeader("Authorization", localOperatorBearer);
    });
  };
  return route;
}

/**
 * Transparent is the compatibility default: caller Authorization is preserved
 * when present and absence remains absence. Tenant enforcement and local operator
 * fallback are explicit, mutually exclusive startup modes.
 */
export function operatorAuthorizationConfig(
  value: string | undefined,
  dedicatedProxyBearer: string | undefined,
): ProxyAuthorizationConfig {
  const mode = (value ?? "transparent").trim().toLowerCase();
  if (mode === "transparent") return { policy: "preserve-optional" };
  if (mode === "tenant") return { policy: "preserve-required" };
  if (mode === "local-operator") {
    return {
      policy: "preserve-optional",
      localOperatorBearer: normalizeLocalOperatorBearer(dedicatedProxyBearer),
    };
  }
  throw new Error("aureon_ui_auth_mode_invalid");
}

export function assertResolvedLoopbackBindHost(host: string | boolean | undefined, surface: string): void {
  if (typeof host !== "string" || !isLoopbackHost(host)) {
    // Do not interpolate configuration values: CLI input and environment data
    // must not be reflected into logs by a failed startup.
    throw new Error(`aureon_${surface}_must_bind_loopback`);
  }
}

/** configResolved runs after CLI flags, so `vite --host 0.0.0.0` cannot override the policy. */
export function createLoopbackIngressPlugin(isPreview = false): Plugin {
  return {
    name: "aureon-loopback-ingress-boundary",
    enforce: "pre",
    configResolved(config: ResolvedConfig) {
      if (config.command !== "serve") return;
      const host = isPreview ? config.preview.host : config.server.host;
      assertResolvedLoopbackBindHost(host, isPreview ? "preview" : "server");
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith("/api")) return next();
        const decision = inspectProxyRequest(req);
        if (decision.allowed) return next();
        res.statusCode = 403;
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.setHeader("X-Content-Type-Options", "nosniff");
        res.end(JSON.stringify({ error: { code: 403, message: "local proxy boundary rejected request" } }));
      });
    },
  };
}
