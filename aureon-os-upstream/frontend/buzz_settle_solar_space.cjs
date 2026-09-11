const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const OUT = "C:\\Users\\user\\Desktop\\HNC_DESIGN_2026-09-10";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const PAGES = [
  {
    url: "http://127.0.0.1:5173/research/solar",
    full: "31_solar_settle.png",
    vp: "31_solar_settle_viewport.png",
    txt: "31_solar_settle.txt",
    label: "solar",
  },
  {
    url: "http://127.0.0.1:5173/research/space-weather",
    full: "32_space_weather_settle.png",
    vp: "32_space_weather_settle_viewport.png",
    txt: "32_space_weather_settle.txt",
    label: "space-weather",
  },
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1200 },
  });

  for (const p of PAGES) {
    console.log("\n==== " + p.label + " ====");
    const page = await context.newPage();
    await page.goto(p.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    try {
      await page.waitForLoadState("networkidle", { timeout: 25000 });
    } catch (_) {
      console.log("networkidle best-effort timeout (ok)");
    }

    const markers = [/SHIPPED\s*GLASS/i, /EXAMPLE/i];
    const deadline = Date.now() + 30000;
    let body = "";
    while (Date.now() < deadline) {
      body = await page.evaluate(() => document.body?.innerText || "");
      if (markers.every((re) => re.test(body))) break;
      await page.waitForTimeout(500);
    }

    await page.waitForTimeout(15000);

    body = await page.evaluate(() => document.body?.innerText || "");

    const fullPath = path.join(OUT, p.full);
    const vpPath = path.join(OUT, p.vp);
    const txtPath = path.join(OUT, p.txt);

    await page.screenshot({ path: fullPath, fullPage: true });
    await page.screenshot({ path: vpPath, fullPage: false });
    fs.writeFileSync(txtPath, body.slice(0, 4500), "utf8");

    const shipped = /SHIPPED GLASS/i.test(body);
    const example = /EXAMPLE/i.test(body);
    const conceptLeftover = /CONCEPT\s*\/?\s*INTERPRETATION/i.test(body);
    const confidenceHigh = /92%|89%|HIGH confidence/i.test(body);
    const mysticTrading = /solfeggio|lighthouse as market|financial advice/i.test(body);

    console.log("CHECK shipped=" + shipped);
    console.log("CHECK example=" + example);
    console.log("CHECK conceptLeftover=" + conceptLeftover);
    console.log("CHECK confidenceHigh=" + confidenceHigh);
    console.log("CHECK mysticTrading=" + mysticTrading);
    console.log("OUT fullPage=" + fullPath);
    console.log("OUT viewport=" + vpPath);
    console.log("OUT text=" + txtPath);
    console.log("BODY_SAMPLE_LEN=" + body.length);
    const collapsed = body.replace(/\s+/g, " ").trim().slice(0, 2000);
    console.log("BODY_COLLAPSED_2000=" + collapsed);

    await page.close();
  }

  await browser.close();
})().catch((err) => {
  console.error("FATAL", err);
  process.exit(1);
});
