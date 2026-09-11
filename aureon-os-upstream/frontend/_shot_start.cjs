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
  await page.goto("http://127.0.0.1:5173/start", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 20000 }); } catch {}
  await page.waitForTimeout(10000);
  await page.screenshot({ path: outDir + "\\00_start_current.png", fullPage: true });
  const text = (await page.locator("body").innerText()).slice(0, 2500);
  fs.writeFileSync(outDir + "\\00_start_current.txt", text);
  console.log("SHOT", text.slice(0, 600).replace(/\s+/g, " "));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
