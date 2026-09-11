const { chromium } = require("playwright");
const fs = require("fs");
const outDir = "C:\\Users\\user\\Desktop\\HNC_DESIGN_2026-09-10";
fs.mkdirSync(outDir, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  await page.goto("http://127.0.0.1:5173/console", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 25000 }); } catch {}
  // wait for operator overview markers
  try {
    await page.waitForSelector('[data-overview="operator"], text=Portfolio GBP, text=EXECUTION, text=HOLD', { timeout: 20000 });
  } catch {}
  await page.waitForTimeout(10000);
  await page.waitForTimeout(5000);
  const shot = outDir + "\\11_console_overview_settle.png";
  await page.screenshot({ path: shot, fullPage: true });
  const text = (await page.locator("body").innerText()).slice(0, 4000);
  fs.writeFileSync(outDir + "\\11_console_overview_settle.txt", text);
  console.log("SHOT", shot);
  console.log("TEXT", text.slice(0, 1500).replace(/\s+/g, " "));
  // also viewport-only above fold
  await page.screenshot({ path: outDir + "\\11_console_overview_viewport.png", fullPage: false });
  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error(e); process.exit(1); });
