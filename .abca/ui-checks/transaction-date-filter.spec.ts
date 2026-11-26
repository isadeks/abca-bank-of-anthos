// Transactions can be filtered by date (DEM-343).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the transaction history can be filtered by date', async ({ page }) => {
  await signIn(page);

  const form = page.locator('#transaction-filter');
  await expect(page.locator('#filter-from')).toBeVisible();
  await expect(page.locator('#filter-to')).toBeVisible();
  await highlight(page, form, 'date filter');
  await shot(page, 'The filter has from and to dates', { focus: form });

  await page.fill('#filter-from', '2999-01-01');
  await page.click('#filter-apply');
  await expect(page.locator('#transaction-table')).toContainText('No Matching Transactions');
  await expect(page.locator('#filter-from')).toHaveValue('2999-01-01');
  await shot(page, 'A future start date finds nothing', { focus: page.locator('#transaction-table') });

  await page.fill('#filter-from', '2000-01-01');
  await page.fill('#filter-to', '2999-01-01');
  await page.click('#filter-apply');
  await expect(page.locator('#transaction-list tr').first()).toBeVisible();
  await shot(page, 'A wide date range lists the transactions', { focus: page.locator('#transaction-table') });
});
