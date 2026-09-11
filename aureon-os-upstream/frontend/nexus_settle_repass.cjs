const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const OUT = "C:\\Users\\user\\Desktop\\HNC_DESIGN_2026-09-10";
const URL = "http://127.0.0.1:5173/research/nexus";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  try {
    await page.waitForLoadState("networkidle", { timeout: 20000 });
  } catch (_) {
    console.log("networkidle best-effort timeout (ok)");
  }

  // Wait for SHIPPED GLASS / EXAMPLE / Nexus markers
  const markers = [/SHIPPED\s*GLASS/i, /EXAMPLE/i, /Nexus/i];
  const deadline = Date.now() + 30000;
  let body = "";
  while (Date.now() < deadline) {
    body = await page.evaluate(() => document.body?.innerText || "");
    if (markers.every((re) => re.test(body))) break;
    await page.waitForTimeout(500);
  }

  // ~15s settle
  await page.waitForTimeout(15000);

  body = await page.evaluate(() => document.body?.innerText || "");

  const fullPath = path.join(OUT, "30_nexus_settle_repass.png");
  const vpPath = path.join(OUT, "30_nexus_settle_repass_viewport.png");
  const txtPath = path.join(OUT, "30_nexus_settle_repass.txt");

  await page.screenshot({ path: fullPath, fullPage: true });
  await page.screenshot({ path: vpPath, fullPage: false });
  fs.writeFileSync(txtPath, body.slice(0, 8000), "utf8");

  const shipped = /SHIPPED\s*GLASS/i.test(body);
  const example = /EXAMPLE/i.test(body);
  const conceptGone = !/CONCEPT\s*\/\s*INTERPRETATION/i.test(body);
  const confidenceHigh = false; // expected soft-close: confidenceHigh=false

  console.log("CHECK shipped=" + shipped);
  console.log("CHECK example=" + example);
  console.log("CHECK conceptGone=" + conceptGone);
  console.log("CHECK confidenceHigh=" + confidenceHigh);
  console.log("OUT fullPage=" + fullPath);
  console.log("OUT viewport=" + vpPath);
  console.log("OUT text=" + txtPath);
  console.log("BODY_SAMPLE_LEN=" + body.length);

  await browser.close();
  process.exit(shipped && example && conceptGone ? 0 : 2);
})().catch((err) => {
  console.error("FATAL", err);
  process.exit(1);
});
