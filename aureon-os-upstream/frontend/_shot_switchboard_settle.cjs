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
  await page.goto("http://127.0.0.1:5173/platform/switchboard", { waitUntil: "domcontentloaded", timeout: 60000 });
  try { await page.waitForLoadState("networkidle", { timeout: 25000 }); } catch {}
  try { await page.waitForSelector("text=Switchboard, text=SHIPPED GLASS, text=OFF", { timeout: 20000 }); } catch {}
  await page.waitForTimeout(10000);
  await page.waitForTimeout(5000);
  await page.screenshot({ path: outDir + "\\22_switchboard_settle.png", fullPage: true });
  await page.screenshot({ path: outDir + "\\22_switchboard_settle_viewport.png", fullPage: false });
  const text = (await page.locator("body").innerText()).slice(0, 4500);
  fs.writeFileSync(outDir + "\\22_switchboard_settle.txt", text);
  console.log("TEXT", text.slice(0, 2000).replace(/\s+/g, " "));
  const onCount = (text.match(/\bON\b/g) || []).length;
  const offCount = (text.match(/\bOFF\b/g) || []).length;
  console.log("CHECK shipped=", /SHIPPED GLASS/i.test(text), "off=", offCount, "on=", onCount, "greenBaseline=", /LOW-RISK BASELINE|paint-green/i.test(text), "allOff=", /ALL OFF|NO GREEN/i.test(text));
  console.log("DONE");
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
