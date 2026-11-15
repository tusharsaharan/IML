/** Optional browser QA using an already installed Playwright and browser. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';

const { chromium } = createRequire(import.meta.url)('playwright');
const base = process.env.IML_BROWSER_BASE_URL || 'http://127.0.0.1:8080';
const out = 'test-results/pipeline';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.IML_BROWSER_CHANNEL || 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const runs = [];

async function run(button = 'Run pipeline') {
  const received = page.waitForResponse(response => response.url().endsWith('/api/v1/chat') && response.request().method() === 'POST');
  await page.getByRole('button', { name: button, exact: true }).click();
  const response = await received;
  assert.equal(response.status(), 200);
  const result = await response.json();
  await page.getByText(`Answer · request #${result.request_id}`, { exact: true }).waitFor();
  runs.push({ language: result.language, source: result.answer_source, cache_hit: result.cache.hit });
  return result;
}

try {
  await page.goto(base);
  await page.evaluate(() => localStorage.setItem('iml.cache.scope.v1', `qa-${crypto.randomUUID()}`));
  await page.reload();
  const cold = await run();
  assert.equal(cold.answer_source, 'authored-demo');
  assert.equal(cold.cache.hit, false);
  assert.equal(cold.compression.method, 'crf');
  assert.equal(cold.routing.scorer.proxy, false);
  await page.screenshot({ path: `${out}/desktop-cold.png`, fullPage: true });
  const warm = await run('Repeat this request');
  assert.equal(warm.cache.hit, true);
  assert.equal(warm.compression, null);
  assert.equal(warm.routing, null);

  // Cache management must open the same configuration, not the standalone lab.
  await page.getByRole('link', { name: 'Manage this pipeline cache' }).click();
  await page.getByText(cold.compression.original, { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Seed demo FAQs', exact: true }).isDisabled(), true);
  await page.getByRole('button', { name: 'Clear cache', exact: true }).click();
  await page.getByText('No cached answers yet.', { exact: false }).waitFor();
  await page.getByRole('link', { name: 'Studio', exact: true }).click();
  assert.equal((await run()).cache.hit, false);

  for (const [label, language] of [['English library', 'en'], ['Hindi assignment', 'hi']]) {
    await page.getByRole('button', { name: label, exact: true }).click();
    const result = await run();
    assert.equal(result.language, language);
    assert.equal(result.answer_source, 'authored-demo');
  }

  await page.getByLabel('Output format', { exact: true }).selectOption('JSON only');
  await page.getByLabel('Maximum output tokens', { exact: true }).fill('40');
  const json = await run();
  JSON.parse(json.answer);
  assert.ok(json.usage.reference_output_tokens <= 40);

  await page.getByRole('link', { name: 'View request history' }).click();
  await page.getByRole('heading', { name: 'Request History & Pipeline Audit' }).waitFor();
  await page.getByText('authored-demo', { exact: true }).first().waitFor();

  await page.getByRole('link', { name: 'Compression', exact: true }).click();
  await page.getByRole('button', { name: 'English filler request', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze prompt', exact: true }).click();
  await page.getByRole('button', { name: 'Send to Request Studio', exact: true }).click();
  assert.equal(await page.getByLabel('Compress prompt', { exact: true }).isChecked(), false);
  const handoff = await run();
  assert.equal(handoff.compression, null);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const mobile = await run();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${out}/mobile-input.png` });
  await page.getByText(`Answer · request #${mobile.request_id}`, { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${out}/mobile-answer.png` });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile horizontal overflow');

  await page.route('**/api/v1/chat', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'QA-only service failure' }) }));
  await page.getByRole('button', { name: 'Run pipeline', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'QA-only service failure' }).waitFor();
  await page.unroute('**/api/v1/chat');
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ status: 'passed', runs, mobile_overflow: false, page_errors: errors, screenshots: out }, null, 2));
} finally {
  await browser.close();
}
