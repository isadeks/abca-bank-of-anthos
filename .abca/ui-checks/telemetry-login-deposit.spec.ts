// With telemetry enabled on EKS, the user journey that produces the connected trace
// (login -> userservice, deposit -> ledgerwriter -> balancereader / transactionhistory)
// must keep working: sign in, deposit, and see the balance and history update.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

function parseDollars(text: string): number {
  return parseFloat(text.replace(/[^0-9.\-]/g, ''));
}

test('login and deposit still work with OpenTelemetry enabled', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  const before = parseDollars((await balance.innerText()).replace(/,/g, ''));
  await highlight(page, balance, 'balance before');
  await shot(page, 'Signed in: login went through the traced userservice', { focus: balance });

  await page.locator('#depositSpan').click();
  const form = page.locator('#deposit-form');
  await expect(form).toBeVisible();
  await page.locator('#deposit-amount').fill('7');
  await highlight(page, page.locator('#deposit-amount'), 'deposit $7');
  await shot(page, 'Depositing $7 through the traced ledgerwriter', { focus: form });
  await form.locator('button[type=submit]').click();

  await expect(async () => {
    await page.goto('/home');
    const after = parseDollars((await balance.innerText()).replace(/,/g, ''));
    expect(after).toBeCloseTo(before + 7, 2);
  }).toPass({ timeout: 60_000 });

  await highlight(page, balance, 'balance after');
  await shot(page, 'Balance read back through balancereader shows the deposit', { focus: balance });

  const history = page.locator('#transaction-table');
  await expect(history.locator('tbody tr').first()).toBeVisible();
  await highlight(page, history, 'transaction history');
  await shot(page, 'Transaction history read back through transactionhistory', { focus: history });
});
