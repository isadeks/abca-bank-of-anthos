// Example UI check: the home page after sign-in shows the balance and the transaction history.
// A UI check of a change drives the UI to that change and asserts it; see AGENTS.md "UI checks".
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from '../ui-annotate'   // in a real check (top level of .abca/ui-checks): './ui-annotate';

test('home shows the balance and the transaction history', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  await highlight(page, balance, 'balance');
  await shot(page, 'Current balance after sign-in', { focus: balance });

  const history = page.locator('#transaction-table');
  await expect(history.locator('tbody tr').first()).toBeVisible();
  await highlight(page, history, 'transaction history');
  await shot(page, 'Recent transactions on the home page', { focus: history });
});
