import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); }
catch {
  if (!process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES) throw new Error('Install Playwright and Chromium before running: npm install --no-save playwright && npx playwright install chromium');
  playwright = require(require.resolve('playwright', { paths: [process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES] }));
}
const base = process.env.BASE_URL || 'http://127.0.0.1:5187';
const server = process.env.BASE_URL ? null : spawn(process.execPath,
  ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5187', '--strictPort'],
  { cwd: new URL('../', import.meta.url), stdio: 'ignore' });
let ready = false;
for (let attempt = 0; attempt < 60; attempt++) {
  try { if ((await fetch(base)).ok) { ready = true; break; } } catch { /* starting */ }
  await delay(250);
}
if (!ready) { server?.kill(); throw new Error('Test server did not become ready'); }
let browser;
try {
  browser = await playwright.chromium.launch({ headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
    ...(process.env.PLAYWRIGHT_CHROMIUM_ARGS ? { args: JSON.parse(process.env.PLAYWRIGHT_CHROMIUM_ARGS) } : {}),
  });
} catch (error) { server?.kill(); throw error; }
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
const page = await context.newPage();
const errors = [];
const requests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => requests.push(request.url()));
const artifacts = new URL('../../.tmp/openstock-verification/', import.meta.url);
await mkdir(artifacts, { recursive: true });
try {
  await page.goto(`${base}/openstock`);
  await page.locator('.os-summary h3').waitFor();
  assert.equal(await page.locator('.os-summary h3').innerText(), '台積電');
  assert.equal(requests.some(url => url.includes('s3.tradingview.com')), false, 'external scripts load only after activation');
  assert.equal(await page.locator('.os-warning').count(), 1, 'old snapshot is clearly labelled');
  console.log('PASS real Taiwan lookup, stale data notice, and deferred external widgets');

  // Save an explicitly empty watchlist, then verify that the async defaults do not overwrite it.
  await page.evaluate(() => localStorage.setItem('tw_stock_watchlist', '[]'));
  await Promise.all([page.waitForResponse(r => r.url().endsWith('/data/watchlist_latest.json')), page.reload()]);
  await page.locator('.os-summary h3').waitFor();
  await page.getByRole('button', { name: '我的自選 0', exact: true }).waitFor();
  await page.getByRole('button', { name: '☆ 加入自選', exact: true }).click();
  await page.getByRole('button', { name: '我的自選 1', exact: true }).waitFor();
  await page.getByRole('button', { name: '自選監控 觀察清單與條件監控', exact: true }).click();
  await page.getByText('2330 台積電', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'OpenStock 研究室 台股搜尋、圖表與公司研究', exact: true }).click();
  await page.getByRole('button', { name: '★ 移出自選', exact: true }).click();
  await page.reload();
  await page.locator('.os-summary h3').waitFor();
  await page.getByRole('button', { name: '我的自選 0', exact: true }).waitFor();
  console.log('PASS add/remove, shared watchlist, and empty persistence after reload');

  await page.keyboard.press('Control+k');
  assert.equal(await page.locator('#os-search').evaluate(el => el === document.activeElement), true);
  await page.locator('#os-search').fill('00878');
  await page.locator('.os-result').first().click();
  assert.match(await page.locator('.os-summary .os-eyebrow').innerText(), /TWSE \/ 00878/);
  await page.locator('#os-search').fill('nothing-found');
  await page.getByText('找不到符合的股票或 ETF，試試代號或部分名稱。', { exact: true }).waitFor();
  await page.locator('#os-search').fill('00400A');
  await page.locator('.os-result').first().click();
  await page.getByText('此標的尚無可用的歷史走勢檔，可前往個股雷達查看其他已備資料。', { exact: true }).waitFor();
  console.log('PASS keyboard search, ETF leading zeros, unknown query, missing trend fallback');

  await page.locator('#os-search').fill('2330');
  await page.locator('.os-result').first().click();
  await page.locator('.os-local-chart').waitFor();
  // Only external script transport is fault-injected; all quote data is real repository JSON.
  await page.route('https://s3.tradingview.com/**', route => route.abort());
  await page.getByRole('button', { name: '載入 TradingView 圖表', exact: true }).click();
  await page.getByRole('button', { name: '重新載入圖表', exact: true }).waitFor();
  assert.equal(await page.locator('.os-widget-frame script').count(), 1);
  for (const tab of ['技術摘要', '財務資料', '公司簡介', '進階 K 線']) {
    await page.getByRole('button', { name: tab, exact: true }).click();
    await page.getByRole('button', { name: '重新載入圖表', exact: true }).waitFor();
    assert.equal(await page.locator('.os-widget-frame script').count(), 1, 'one widget instance after switching tabs');
  }
  await page.getByRole('button', { name: '重新載入圖表', exact: true }).click();
  await page.getByRole('button', { name: '重新載入圖表', exact: true }).waitFor();
  await page.getByRole('button', { name: '關閉外部圖表', exact: true }).click();
  assert.equal(await page.locator('.os-widget-frame script').count(), 0);
  console.log('PASS external outage, retry, tabs and unmount cleanup');

  for (const width of [390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: `${artifacts.pathname}${width}.png`, fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `no horizontal overflow at ${width}`);
    console.log(`PASS responsive layout at ${width}px`);
  }
  await page.getByRole('button', { name: '查看台股 Alpha 與籌碼 →', exact: true }).click();
  await page.getByRole('heading', { name: '個股雷達', exact: true, level: 2 }).waitFor();
  assert.equal(await page.locator('vite-error-overlay').count(), 0);
  assert.deepEqual(errors, []);
  console.log('PASS navigation back to original stock page; no uncaught browser errors');
} finally { await context.close(); await browser.close(); server?.kill(); }
