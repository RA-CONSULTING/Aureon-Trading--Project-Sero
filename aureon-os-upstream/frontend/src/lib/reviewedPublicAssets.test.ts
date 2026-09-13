import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import { REVIEWED_PUBLIC_ASSETS } from "../../config/reviewedPublicAssets";

test("production public assets are an exact non-operational allowlist", () => {
  assert.deepEqual(REVIEWED_PUBLIC_ASSETS, [
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
  assert.equal(REVIEWED_PUBLIC_ASSETS.some((path) => path.endsWith(".json")), false);
  assert.equal(
    REVIEWED_PUBLIC_ASSETS.some((path) => /trade|execution|result|signal|runtime/i.test(path)),
    false,
  );
});

test("Vite disables implicit public directory copying", () => {
  const source = readFileSync(resolve(process.cwd(), "vite.config.ts"), "utf8");
  assert.match(source, /publicDir:\s*false/);
  assert.match(source, /reviewedPublicAssetsPlugin\(\)/);
});
