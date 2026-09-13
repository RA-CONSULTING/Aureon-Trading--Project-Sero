import { lstatSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

export const REVIEWED_PUBLIC_ASSETS = Object.freeze([
  "aureon-logo.jpg",
  "favicon.svg",
  "ra-consulting-logo.jpg",
  "watch/icon-192.png",
  "watch/icon-512.png",
  "watch/icon-maskable.png",
  "watch/icon.svg",
  "watch/index.html",
  "watch/manifest.webmanifest",
  "watch/sw.js",
  "watch/watch.css",
  "watch/watch.js",
]);

const PUBLIC_ROOT = fileURLToPath(new URL("../public/", import.meta.url));
const MAX_PUBLIC_ASSET_BYTES = 2 * 1024 * 1024;

export function reviewedPublicAssetsPlugin(): Plugin {
  return {
    name: "aureon-reviewed-public-assets",
    apply: "build",
    buildStart() {
      for (const relative of REVIEWED_PUBLIC_ASSETS) {
        const absolute = fileURLToPath(new URL(relative, new URL("../public/", import.meta.url)));
        const stat = lstatSync(absolute);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.size > MAX_PUBLIC_ASSET_BYTES) {
          this.error(`reviewed public asset is unsafe: ${relative}`);
        }
        if (!absolute.startsWith(PUBLIC_ROOT)) {
          this.error(`reviewed public asset escaped root: ${relative}`);
        }
        this.emitFile({ type: "asset", fileName: relative, source: readFileSync(absolute) });
      }
    },
  };
}
