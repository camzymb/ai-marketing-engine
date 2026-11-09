// Records the dashboard while the run happens. Usage: node record.js <outName> [port]
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const out = process.argv[2] || 'run';
  const port = process.argv[3] || '8787';
  const dir = path.join(__dirname, 'video-tmp');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, recordVideo: { dir, size: { width: 1080, height: 1920 } } });
  const page = await ctx.newPage();
  await page.goto(`http://localhost:${port}/`);
  // wait until the summary overlay shows, then hold it on screen for a few seconds
  await page.waitForSelector('#final.show', { timeout: 15 * 60 * 1000 });
  await page.waitForTimeout(6000);
  await page.screenshot({ path: path.join(__dirname, `${out}-final.png`) });
  const video = page.video();
  await ctx.close();
  const p = await video.path();
  fs.renameSync(p, path.join(__dirname, `${out}.webm`));
  await browser.close();
  console.log('saved', `${out}.webm`);
})();
