import { fetchRepoManifest, type ManifestReceipt } from '../lib/repoManifestEvidence';
import { createReadOnlyPoller } from './readOnlyPoller';

/** Public, recorded navigation artifact. HTTP completion is not its source date. */
export const repoMapStore = createReadOnlyPoller<ManifestReceipt>({
  receiptMaxAgeMs: 120_000,
  read: async ({ signal }) => {
    const receipt = await fetchRepoManifest('/aureon_repo_sitemap.json', signal);
    if (!receipt.report) throw new Error(receipt.reason);
    return receipt;
  },
});
