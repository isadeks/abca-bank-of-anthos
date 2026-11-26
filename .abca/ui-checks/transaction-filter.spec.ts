// Transactions can be filtered by type and text (DEM-343).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the transaction history can be filtered', async ({ page }) => {
  await signIn(page);

  const form = page.locator('#transaction-filter');
  await expect(form).toBeVisible();
  await highlight(page, form, 'filter');
  await shot(page, 'The transaction history with its filter', { focus: form });

  const rows = page.locator('#transaction-list tr');
  const total = await rows.count();
  expect(total).toBeGreaterThan(0);

  await page.selectOption('#filter-type', 'credit');
  await page.click('#filter-apply');
  await expect(page.locator('#transaction-filter')).toBeVisible();
  const credits = page.locator('#transaction-list tr .transaction-type');
  expect(await credits.count()).toBeGreaterThan(0);
  await expect(credits.filter({ hasText: 'Debit' })).toHaveCount(0);
  await highlight(page, page.locator('#transaction-table'), 'credits only');
  await shot(page, 'Only credit transactions are listed', { focus: page.locator('#transaction-table') });

  await page.fill('#filter-query', 'zzz-no-such-account');
  await page.click('#filter-apply');
  await expect(page.locator('#transaction-table')).toContainText('No Matching Transactions');
  await shot(page, 'A search with no results says so', { focus: page.locator('#transaction-table') });
});
