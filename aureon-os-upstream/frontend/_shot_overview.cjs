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
    { name: "00_overview", url: "http://127.0.0.1:5173/" },
    { name: "00b_overview_dashboard", url: "http://127.0.0.1:5173/overview" },
  ];
  const notes = [];
  for (const p of urls) {
    try {
      await page.goto(p.url, { waitUntil: "domcontentloaded", timeout: 45000 });
      try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch {}
      await page.waitForTimeout(6000);
      const shot = outDir + "\\" + p.name + "_current.png";
      await page.screenshot({ path: shot, fullPage: true });
      const text = (await page.locator("body").innerText()).slice(0, 1500);
      notes.push({ name: p.name, url: p.url, ok: true, sample: text.replace(/\s+/g, " ").slice(0, 500) });
      console.log("OK", p.name, text.slice(0, 200).replace(/\s+/g, " "));
    } catch (e) {
      notes.push({ name: p.name, url: p.url, error: String(e) });
      console.log("FAIL", p.name, String(e));
    }
  }
  fs.writeFileSync(outDir + "\\overview_notes.json", JSON.stringify(notes, null, 2));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
