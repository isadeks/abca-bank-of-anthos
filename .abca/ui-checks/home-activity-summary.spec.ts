// UI check: the home page balance and transaction history, with an activity summary
// and clearer credit/debit styling.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home shows an activity summary and clear credit/debit styling', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  await highlight(page, balance, 'balance');
  await shot(page, 'Current balance in its highlighted card', { focus: balance });

  const summary = page.locator('#activity-summary');
  await expect(summary).toBeVisible();
  await expect(page.locator('#summary-money-in')).toContainText('$');
  await expect(page.locator('#summary-money-out')).toContainText('$');
  await highlight(page, summary, 'money in and out');
  await shot(page, 'Summary of money in and money out', { focus: summary });

  const history = page.locator('#transaction-table');
  await expect(history.locator('tbody tr').first()).toBeVisible();
  const credit = history.locator('.type-badge-credit').first();
  const debit = history.locator('.type-badge-debit').first();
  await expect(credit).toBeVisible();
  await expect(debit).toBeVisible();
  await expect(history.locator('.transaction-amount-credit').first()).toContainText('+$');
  await expect(history.locator('.transaction-amount-debit').first()).toContainText('-$');
  await highlight(page, history, 'credits in green, debits in red');
  await shot(page, 'Transaction history with credit and debit badges', { focus: history });
});
