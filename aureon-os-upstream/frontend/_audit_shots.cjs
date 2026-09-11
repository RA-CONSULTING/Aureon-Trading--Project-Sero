const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const outDir = "C:\\Users\\user\\Desktop\\UI_AUDIT_2026-09-10";
fs.mkdirSync(outDir, { recursive: true });

const pages = [
  { name: "01_hft", url: "http://127.0.0.1:5173/trading/hft" },
  { name: "02_war_room", url: "http://127.0.0.1:5173/trading/war-room" },
  { name: "03_live", url: "http://127.0.0.1:5173/trading/live" },
];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const notes = [];

  for (const p of pages) {
    const t0 = Date.now();
    let loadNote = "";
    try {
      await page.goto(p.url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try {
        await page.waitForLoadState("networkidle", { timeout: 25000 });
      } catch (e) {
        loadNote += "networkidle-timeout; ";
      }
      await page.waitForTimeout(10000);
      await page.waitForTimeout(5000);
      const shot = path.join(outDir, p.name + ".png");
      await page.screenshot({ path: shot, fullPage: true });
      const bodyText = (await page.locator("body").innerText()).slice(0, 3000);
      notes.push({
        page: p.name,
        url: p.url,
        ms: Date.now() - t0,
        loadNote,
        textSample: bodyText.replace(/\s+/g, " ").slice(0, 1000),
        shot,
      });
      console.log("SHOT", p.name, Date.now() - t0 + "ms");
    } catch (err) {
      notes.push({ page: p.name, url: p.url, error: String(err) });
      console.log("FAIL", p.name, String(err));
    }
  }

  fs.writeFileSync(path.join(outDir, "notes.json"), JSON.stringify(notes, null, 2));
  await browser.close();
  console.log("DONE", outDir);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
