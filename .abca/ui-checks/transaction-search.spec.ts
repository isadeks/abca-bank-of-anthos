// The home page has a search box above the transaction history that filters rows by
// counterparty name or account number as you type (DEM-282).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('searching the transaction history filters rows and reports when nothing matches', async ({ page }) => {
  await signIn(page);

  const search = page.locator('#transaction-search');
  const rows = page.locator('#transaction-list tr');
  await expect(search).toBeVisible();
  await expect(rows.first()).toBeVisible();
  const total = await rows.count();
  await highlight(page, search, 'search box');
  await shot(page, 'The transaction history has a search box above it', { focus: page.locator('#transaction-table') });

  // Filter by the account number of the first row.
  const account = (await rows.first().locator('.transaction-account').innerText()).trim();
  await search.pressSequentially(account);
  const visibleRows = page.locator('#transaction-list tr:not([hidden])');
  await expect(visibleRows.first()).toBeVisible();
  const count = await visibleRows.count();
  expect(count).toBeGreaterThan(0);
  expect(count).toBeLessThanOrEqual(total);
  for (const text of await visibleRows.locator('.transaction-account').allInnerTexts()) {
    expect(text.trim()).toContain(account);
  }
  await highlight(page, search, 'account number');
  await shot(page, 'Typing an account number keeps only its transactions', { focus: page.locator('#transaction-table') });

  // Nothing matches.
  await search.fill('zzz-no-such-counterparty');
  const empty = page.locator('#no-matching-transactions');
  await expect(empty).toBeVisible();
  await expect(empty).toHaveText('No matching transactions');
  await expect(visibleRows).toHaveCount(0);
  await highlight(page, empty, 'no results');
  await shot(page, 'A search with no results shows "No matching transactions"', { focus: empty });

  // Clearing the search brings every row back.
  await search.fill('');
  await expect(empty).toBeHidden();
  await expect(visibleRows).toHaveCount(total);
});
