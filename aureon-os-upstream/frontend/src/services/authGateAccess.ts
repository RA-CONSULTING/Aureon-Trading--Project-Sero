import { readIdentity } from '../lib/accountConfigurationEvidence';

/**
 * The public Cloud Run console always requires a tenant session. Keeping this
 * decision in the bundle as well as the build configuration prevents a missed
 * VITE_REQUIRE_AUTH argument from exposing a disconnected anonymous shell.
 * Local development remains opt-in.
 */
export function requiresConsoleAuth(configured: string | undefined, hostname: string): boolean {
  return configured === '1' || hostname.toLowerCase().endsWith('.run.app');
}

/**
 * A protected owner hostname may already have a verified Google IAP identity.
 * Trust only the backend's current `/api/me` admin receipt; public and tenant
 * responses cannot manufacture owner access in the browser.
 */
export async function hasCurrentOwnerIngress(read: () => Promise<unknown>): Promise<boolean> {
  try {
    return readIdentity(await read())?.isAdmin === true;
  } catch {
    return false;
  }
}
