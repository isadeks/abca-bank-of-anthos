// The home page labels the balance "Available Balance".
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home labels the balance "Available Balance"', async ({ page }) => {
  await signIn(page);

  const label = page.locator('#balance-label');
  await expect(label).toHaveText('Available Balance');
  await highlight(page, label, 'new label');
  await shot(page, 'The balance is labelled "Available Balance"', { focus: label });

  const amount = page.locator('#current-balance');
  await expect(amount).toContainText('$');
  await highlight(page, amount, 'balance');
  await shot(page, 'The amount is unchanged under the new label', { focus: amount });
});
