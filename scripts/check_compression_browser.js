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

  const phrases = page.getByLabel('Always keep these phrases (optional)', { exact: true });
  await phrases.focus();
  await page.keyboard.insertText('user@example.com');
  if (!await page.getByRole('button', { name: 'Export Studio request', exact: true }).isDisabled()) throw new Error('Phrase edit did not block export');
  const surviving = await run();
  if (surviving.protection_fallback || surviving.compressed !== crf.compressed) throw new Error('Surviving phrase changed compression');
  await phrases.fill('yaar\nuser@example.com');
  for (const name of ['Copy text', 'Download audit', 'Export Studio request']) {
    if (!await page.getByRole('button', { name, exact: true }).isDisabled()) throw new Error('Phrase edit left stale action enabled: ' + name);
  }
  const guarded = await run();
  if (!guarded.protection_fallback || guarded.method !== 'protection_fallback' || guarded.compressed !== crf.original || guarded.saved_tokens !== 0) throw new Error('Original-text protection fallback failed: ' + JSON.stringify(guarded));
  if (guarded.compression_candidate.compressed !== crf.compressed || guarded.compression_candidate.method !== crf.method) throw new Error('Unchanged research candidate not retained');
  await page.getByRole('heading', { name: 'Final output: original retained', exact: true }).waitFor();
  await page.getByText('Inspect unchanged compressor candidate (excluded from Studio request)', { exact: true }).click();
  await page.getByText('Lost in compressor output; original retained', { exact: true }).waitFor();
  const guardDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Studio request', exact: true }).click();
  const guardDownload = await guardDownloadPromise;
  await guardDownload.saveAs('test-results/compression/protected-studio-request.json');
  const auditDownloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download audit', exact: true }).click();
  await (await auditDownloadPromise).saveAs('test-results/compression/protected-audit.json');
  await page.screenshot({ path: 'test-results/compression/phrase-fallback-desktop.png', fullPage: true });
  await phrases.fill('Yaar');
  await page.getByRole('alert').filter({ hasText: 'Phrase not found exactly' }).waitFor();
  if (!await page.getByRole('button', { name: 'Analyze prompt', exact: true }).isDisabled()) throw new Error('Invalid phrase can be submitted');
  await phrases.fill('');

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

  await page.getByRole('button', { name: 'Hindi and English', exact: true }).click();
  await phrases.fill('मेरा\nनहीं\nwifi काम');
  const unicode = await run();
  if (unicode.phrase_checks.length !== 3 || !unicode.phrase_checks.every((check) => check.preserved_in_output)) throw new Error('Hindi phrase check failed');
  if (!await page.locator('mark').filter({ hasText: 'नहीं' }).count()) throw new Error('Hindi selection highlight missing');
  await page.screenshot({ path: 'test-results/compression/desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({ viewport: innerWidth, width: document.documentElement.scrollWidth }));
  if (mobile.width > mobile.viewport) throw new Error('Whole-page mobile overflow');
  await page.screenshot({ path: 'test-results/compression/mobile.png', fullPage: true });
  await phrases.fill('');
  await page.getByRole('button', { name: 'Hinglish email request', exact: true }).click();
  await page.getByRole('slider').focus();
  await page.keyboard.press('Home');
  await phrases.fill('yaar');
  const mobileGuard = await run();
  if (!mobileGuard.protection_fallback) throw new Error('Mobile protection fallback failed');
  const fallbackMobile = await page.evaluate(() => ({ viewport: innerWidth, width: document.documentElement.scrollWidth }));
  if (fallbackMobile.width > fallbackMobile.viewport) throw new Error('Protection fallback causes mobile overflow');
  await page.screenshot({ path: 'test-results/compression/phrase-fallback-mobile.png', fullPage: true });

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
    protection_fallback: guarded.method, candidate_unchanged: true, phrase_edit_blocks_exports: true,
    invalid_phrase_blocked: true, unicode_checks: unicode.phrase_checks.length, fallbackMobile,
    passthrough: true, stale_output_blocked: true, service_error_visible: true, page_errors: errors };
}
