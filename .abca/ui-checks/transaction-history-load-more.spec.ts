// The home page shows the 10 most recent transactions with a Load more button (DEM-262);
// Load more appends the next transactions instead of loading the whole history up front.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('transaction history shows 10 rows and loads more on demand', async ({ page }) => {
  await signIn(page);

  const rows = page.locator('#transaction-list tr');
  const loadMore = page.locator('#load-more-transactions');
  await expect(rows).toHaveCount(10);
  await expect(loadMore).toBeVisible();
  await highlight(page, loadMore, 'Load more');
  await shot(page, 'The 10 most recent transactions and a Load more button', {
    focus: page.locator('#transaction-table'),
  });

  await loadMore.click();
  await expect(rows).toHaveCount(20);
  await highlight(page, rows.nth(10), 'next transactions');
  await shot(page, 'Load more appends the next 10 transactions', {
    focus: page.locator('#transaction-table'),
  });
});
