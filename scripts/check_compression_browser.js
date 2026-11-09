// Run with a separate temporary browser, not the user's signed-in profile:
// playwright-cli -s=iml-compression open http://127.0.0.1:8080/compression --browser=chrome
// playwright-cli -s=iml-compression run-code --filename=scripts/check_compression_browser.js
// Requires npm run dev. All successful results come from the real local API.
async (page) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('http://127.0.0.1:8080/compression');
  await page.getByRole('button', { name: 'Hinglish email request', exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Your large-run development evidence' }).waitFor();
  await page.getByLabel('Method', { exact: true }).selectOption('crf');

  async function run() {
    const response = page.waitForResponse((response) => response.url().endsWith('/compression/analyze') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Analyze prompt', exact: true }).click();
    const body = await (await response).json();
    await page.getByRole('button', { name: 'Analyze prompt', exact: true }).waitFor();
    if (body.evidence_kind !== 'local_execution') throw new Error('Result is not a local execution');
    return body;
  }

  const crf = await run();
  if (crf.method !== 'crf' || !crf.compressed.includes('user@example.com')) throw new Error('CRF execution or email protection failed');
  await page.getByText('Protected content and algorithm drop records', { exact: true }).click();
  if (await page.locator('mark').count() === 0) throw new Error('No tracked protection highlight');
  await page.getByText('Literal present', { exact: true }).waitFor();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Studio request', exact: true }).click();
  const download = await downloadPromise;
  if (download.suggestedFilename() !== 'studio-chat-request.json') throw new Error('Wrong contract export filename');

  await page.getByRole('button', { name: 'English filler request', exact: true }).click();
  if (!await page.getByRole('button', { name: 'Copy text', exact: true }).isDisabled()) throw new Error('Stale output can be copied');
  const english = await run();
  if (!english.compressed.trim()) throw new Error('Empty English output');

  const comparisonResponse = page.waitForResponse((response) => response.url().includes('/compression/compare?'));
  await page.getByRole('button', { name: 'Run method comparison', exact: true }).click();
  const comparison = await (await comparisonResponse).json();
  await page.locator('.compression-table').first().locator('tbody tr').nth(5).waitFor();
  if (comparison.rows.length !== 6) throw new Error('Six comparisons expected');

  await page.getByLabel('Historical context target', { exact: true }).selectOption('0.33');
  const historical = await page.locator('.compression-evidence table tbody tr').allTextContents();
  if (historical.length !== 4) throw new Error('Four historical answer models expected');

  await page.getByRole('slider').focus();
  await page.keyboard.press('End');
  const passthrough = await run();
  if (passthrough.method !== 'passthrough' || passthrough.original !== passthrough.compressed) throw new Error('100% target changed the original');

  await page.screenshot({ path: 'test-results/compression/desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({ viewport: innerWidth, width: document.documentElement.scrollWidth }));
  if (mobile.width > mobile.viewport) throw new Error('Whole-page mobile overflow');
  await page.screenshot({ path: 'test-results/compression/mobile.png', fullPage: true });

  // Explicit QA error response, never used as demo metrics or successful evidence.
  await page.route('**/api/v1/compression/analyze', (route) => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Intentional QA service failure.' }),
  }));
  await page.getByRole('button', { name: 'Analyze prompt', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Intentional QA service failure.' }).waitFor();
  await page.unroute('**/api/v1/compression/analyze');
  if (errors.length) throw new Error(errors.join('; '));
  return { crf_method: crf.method, crf_reference_tokens: [crf.original_tokens, crf.compressed_tokens],
    english_actual_method: english.method, comparison_rows: comparison.rows.length,
    historical_models: historical.length, mobile, export: download.suggestedFilename(),
    passthrough: true, stale_output_blocked: true, service_error_visible: true, page_errors: errors };
}
