// The transaction history has a "Download CSV" link (DEM-397).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('Download CSV link downloads the visible transactions', async ({ page }) => {
  await signIn(page);

  const link = page.locator('#download-csv');
  await link.scrollIntoViewIfNeeded();
  await expect(link).toBeVisible();
  await expect(link).toHaveText('Download CSV');
  await highlight(page, link, 'download csv');
  await shot(page, 'The Download CSV link under Transaction History', { focus: link });

  const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
  expect(download.suggestedFilename()).toBe('transactions.csv');
  const stream = await download.createReadStream();
  let body = '';
  for await (const chunk of stream) body += chunk.toString();
  const lines = body.trim().split(/\r?\n/);
  expect(lines[0]).toBe('Date,Description,Amount');
  expect(lines.length).toBeGreaterThan(1);
  expect(lines[1]).toMatch(/^\d{4}-\d{2}-\d{2},/);
  await shot(page, 'The CSV file was downloaded');
});
