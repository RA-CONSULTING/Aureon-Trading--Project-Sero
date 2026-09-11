const { chromium } = require("playwright");
const fs = require("fs");
const outDir = "C:\\Users\\user\\Desktop\\HNC_DESIGN_2026-09-10";
fs.mkdirSync(outDir, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto("http://127.0.0.1:5173/trading/live", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 20000 }); } catch {}
  await page.waitForTimeout(12000);
  await page.screenshot({ path: outDir + "\\02_live_bridge_current.png", fullPage: true });
  const text = (await page.locator("body").innerText()).slice(0, 2500);
  fs.writeFileSync(outDir + "\\02_live_bridge_current.txt", text);
  console.log("SHOT", text.slice(0, 800).replace(/\s+/g, " "));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
