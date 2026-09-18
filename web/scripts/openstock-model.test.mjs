import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { normalizeStocks, priceAgeDays, searchStocks, tradingViewSymbol, toggleWatchLabel, readWatchlist, validDate, WIDGET_SCRIPTS, widgetConfig } from '../src/integrations/openstock/model.ts';

const payload = JSON.parse(readFileSync(new URL('../../public/data/stock_lookup_latest.json', import.meta.url), 'utf8'));
const stocks = normalizeStocks(payload);

test('Given the existing lookup, common stocks and ETFs remain searchable without invented records', () => {
  assert.equal(stocks.length, payload.records.length);
  assert.equal(searchStocks(stocks, '2330')[0].code, '2330');
  assert.equal(searchStocks(stocks, '台積電')[0].code, '2330');
  assert.equal(searchStocks(stocks, '00878')[0].code, '00878');
  assert.ok(stocks.some(s => s.code === '00400A'));
  assert.deepEqual(searchStocks(stocks, 'NOT_A_STOCK'), []);
});
test('Given Taiwan stocks, TradingView gets the actual exchange and preserves ETF leading zeros', () => {
  for (const code of ['2330', '00878', '00400A']) {
    assert.equal(tradingViewSymbol(stocks.find(s => s.code === code)), `TWSE:${code}`);
  }
  const otc = stocks.find(s => s.market === 'TPEX');
  assert.ok(otc);
  assert.equal(tradingViewSymbol(otc), `TPEX:${otc.code}`);
  assert.equal(tradingViewSymbol({ ...otc, market: 'UNKNOWN' }), null);
  assert.equal(tradingViewSymbol({ ...otc, code: '../2330' }), null);
});
test('Given null quote values, the adapter preserves missing values instead of zero', () => {
  const [s] = normalizeStocks({ records: [{ stock_code: '2330', stock_name: '台積電', close: null, change_pct: 0 }], as_of_date: '2026-09-18' });
  assert.equal(s.close, null);
  assert.equal(s.changePct, 0);
  assert.equal(s.priceDate, null);
});
test('Malformed and duplicate records cannot create invalid widget symbols', () => {
  assert.equal(normalizeStocks({records: [null, {}, {stock_code: '../x', stock_name: 'x'}]}).length, 0);
  assert.equal(normalizeStocks({records: [payload.records[0], payload.records[0]]}).length, 1);
});
test('Freshness uses the individual price date and the Taiwan calendar date', () => {
  assert.equal(priceAgeDays('2026-09-18', new Date('2026-09-17T17:00:00Z')), 0);
  assert.equal(priceAgeDays('2026-07-01', new Date('2026-09-18T08:00:00Z')), 79);
  assert.equal(priceAgeDays('2026-09-19', new Date('2026-09-18T08:00:00Z')), -1);
  assert.equal(priceAgeDays(null), null);
  assert.equal(validDate('2026-02-30'), null);
});
test('Given a renamed stock, toggle removes by exact code and never matches a prefix', () => {
  assert.deepEqual(toggleWatchLabel(['2330 舊名', '23300 其他'], '2330 台積電'), ['23300 其他']);
  assert.deepEqual(toggleWatchLabel([], '00878 國泰永續高股息'), ['00878 國泰永續高股息']);
});
test('Given a deliberately empty saved watchlist, reload must not reseed it', () => {
  assert.deepEqual(readWatchlist({ getItem: () => '[]' }), []);
  assert.equal(readWatchlist({ getItem: () => null }), null);
});
test('Corrupt, duplicate, unavailable browser storage is handled without a crash', () => {
  assert.equal(readWatchlist({ getItem: () => '{' }), null);
  assert.equal(readWatchlist({ getItem: () => '{"x": 1}' }), null);
  assert.equal(readWatchlist({ getItem: () => { throw new Error('blocked'); } }), null);
  assert.deepEqual(readWatchlist({ getItem: () => '["2330 台積電","2330 舊名",1,"<script>"]' }), ['2330 台積電']);
});
test('Widget configuration stays on selected symbol and uses separate provider parameters', () => {
  const chart = widgetConfig('TWSE:2330', 'chart');
  assert.equal(chart.symbol, 'TWSE:2330');
  assert.equal(chart.allow_symbol_change, false);
  assert.equal(chart.timezone, 'Asia/Taipei');
  assert.equal(chart.theme, 'light');
  assert.equal(widgetConfig('TPEX:6488', 'financials').colorTheme, 'light');
  for (const url of Object.values(WIDGET_SCRIPTS)) assert.equal(new URL(url).origin, 'https://s3.tradingview.com');
});
