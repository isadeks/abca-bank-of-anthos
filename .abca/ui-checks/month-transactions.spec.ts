// The home page shows how many transactions the account had this month (DEM-297).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the balance shows the number of transactions this month', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toBeVisible();
  const count = page.locator('#month-transaction-count');
  await expect(count).toBeVisible();
  await expect(count).toHaveText(/^\d+ transactions? this month$/);
  await highlight(page, count, 'transactions this month');
  await shot(page, 'A small line under the balance counts this month\'s transactions', { focus: count });
});
