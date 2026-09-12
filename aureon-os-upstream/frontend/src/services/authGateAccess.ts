import { readIdentity } from '../lib/accountConfigurationEvidence';

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
