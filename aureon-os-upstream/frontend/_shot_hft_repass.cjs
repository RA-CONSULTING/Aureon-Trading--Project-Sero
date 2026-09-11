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
  await page.goto("http://127.0.0.1:5173/trading/hft", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 25000 }); } catch {}
  try { await page.waitForSelector("text=VENUES", { timeout: 20000 }); } catch {}
  await page.waitForTimeout(10000);
  await page.waitForTimeout(5000);
  await page.screenshot({ path: outDir + "\\16_hft_desk_repass.png", fullPage: true });
  await page.screenshot({ path: outDir + "\\16_hft_desk_repass_viewport.png", fullPage: false });
  const text = (await page.locator("body").innerText()).slice(0, 4500);
  fs.writeFileSync(outDir + "\\16_hft_desk_repass.txt", text);
  console.log("TEXT", text.slice(0, 2000).replace(/\s+/g, " "));
  const has44 = /4\s*\/\s*4/.test(text);
  const has34 = /3\s*\/\s*4/.test(text);
  const hasUnconf = /unconfirmed|—\s*\/\s*4|-\s*\/\s*4/.test(text);
  const hasKrakenNR = /Kraken NOT READY/i.test(text);
  console.log("CHECK 4/4=", has44, "3/4=", has34, "unconfirmed=", hasUnconf, "krakenNR=", hasKrakenNR, "shipped=", text.includes("SHIPPED GLASS"), "concept=", /concept layout/i.test(text));
  console.log("DONE");
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
