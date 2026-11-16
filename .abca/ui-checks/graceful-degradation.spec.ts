// When balancereader or transactionhistory is down the home page must still render
// (DEM-308). The backends are healthy in the preview, so this checks the healthy
// page shows no "temporarily unavailable" notice, and that the page structure that
// hosts the fallback notices (balance and history) is present.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home page shows balance and history without fallback notices', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toBeVisible();
  await expect(balance).not.toContainText('temporarily unavailable');
  await expect(balance).toContainText('$');
  await highlight(page, balance, 'balance');
  await shot(page, 'The balance is shown while balancereader is healthy', { focus: balance });

  const table = page.locator('#transaction-table');
  await expect(table).toBeVisible();
  await expect(table).not.toContainText('temporarily unavailable');
  await highlight(page, table, 'history');
  await shot(page, 'The history table is shown while transactionhistory is healthy', { focus: table });
});
