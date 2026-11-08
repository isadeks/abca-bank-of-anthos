// UI check: the home page transaction history has a "Download CSV" button that downloads the user's transactions.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';
import * as fs from 'fs';

test('transaction history can be downloaded as CSV', async ({ page }) => {
  await signIn(page);

  const history = page.locator('#transaction-table');
  await expect(history.locator('tbody tr').first()).toBeVisible();
  await shot(page, 'Transaction history on the home page', { focus: history });

  const button = page.locator('#download-csv');
  await expect(button).toBeVisible();
  await expect(button).toHaveText('Download CSV');
  await highlight(page, button, 'Download CSV');
  await shot(page, 'The new Download CSV button above the transaction history', { focus: button });

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    button.click(),
  ]);
  expect(download.suggestedFilename()).toBe('transactions.csv');

  const path = await download.path();
  const lines = fs.readFileSync(path, 'utf8').trim().split(/\r?\n/);
  expect(lines[0]).toBe('Date,Description,Amount,Type');
  expect(lines.length).toBeGreaterThan(1);
  expect(lines[1]).toMatch(/^\d{4}-\d{2}-\d{2},.*,-?\d+\.\d{2},(Credit|Debit)$/);

  await shot(page, 'The CSV downloaded after clicking the button', { focus: button });
});
