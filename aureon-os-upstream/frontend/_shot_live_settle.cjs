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
  await page.goto("http://127.0.0.1:5173/trading/live", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 25000 }); } catch {}
  try {
    await page.waitForSelector("text=LIVE BRIDGE, text=HOLD, text=KRAKEN, text=EXAMPLE", { timeout: 20000 });
  } catch {}
  await page.waitForTimeout(10000);
  await page.waitForTimeout(5000);
  await page.screenshot({ path: outDir + "\\14_live_bridge_settle.png", fullPage: true });
  await page.screenshot({ path: outDir + "\\14_live_bridge_settle_viewport.png", fullPage: false });
  const text = (await page.locator("body").innerText()).slice(0, 4500);
  fs.writeFileSync(outDir + "\\14_live_bridge_settle.txt", text);
  console.log("TEXT", text.slice(0, 2200).replace(/\s+/g, " "));
  console.log("CHECK hold=", /HOLD|EXECUTION HOLD/i.test(text), "krakenNR=", /KRAKEN[\\s\\S]{0,80}NOT READY|NOT READY[\\s\\S]{0,40}KRAKEN|Invalid nonce/i.test(text), "falseReady=", /KRAKEN[\\s\\S]{0,40}READY(?!.*NOT)/i.test(text) && !/KRAKEN[\\s\\S]{0,80}NOT READY/i.test(text), "example=", /EXAMPLE/i.test(text), "gbp=", /£?217|GBP/i.test(text), "shipped=", /SHIPPED GLASS/i.test(text), "notShipped=", /NOT SHIPPED/i.test(text));
  console.log("DONE");
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
