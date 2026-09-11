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
  const urls = [
    { name: "10_overview_painted", url: "http://127.0.0.1:5173/" },
    { name: "10b_overview_console", url: "http://127.0.0.1:5173/overview" },
    { name: "10c_console_home", url: "http://127.0.0.1:5173/console" },
  ];
  const notes = [];
  for (const p of urls) {
    try {
      await page.goto(p.url, { waitUntil: "domcontentloaded", timeout: 60000 });
      try { await page.waitForLoadState("networkidle", { timeout: 20000 }); } catch (e) { /* settle anyway */ }
      await page.waitForTimeout(8000);
      await page.waitForTimeout(5000);
      const shot = outDir + "\\" + p.name + ".png";
      await page.screenshot({ path: shot, fullPage: true });
      const text = (await page.locator("body").innerText()).slice(0, 3000);
      notes.push({ name: p.name, url: p.url, ok: true, sample: text.replace(/\s+/g, " ").slice(0, 1200) });
      console.log("OK", p.name, text.slice(0, 350).replace(/\s+/g, " "));
    } catch (e) {
      notes.push({ name: p.name, url: p.url, error: String(e) });
      console.log("FAIL", p.name, String(e));
    }
  }
  fs.writeFileSync(outDir + "\\10_overview_painted_notes.json", JSON.stringify(notes, null, 2));
  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error(e); process.exit(1); });
