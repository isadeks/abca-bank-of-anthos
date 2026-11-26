// The Deposit Funds card shows a tooltip; Send Payment does not (DEM-375).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('deposit funds card has a tooltip', async ({ page }) => {
  await signIn(page);
  const card = page.locator('#deposit-card');
  await expect(card).toHaveAttribute('title', 'Add money to your checking account');
  await highlight(page, card, 'tooltip');
  await shot(page, 'The Deposit Funds card with its tooltip', { focus: card });

  const send = page.locator('.card-button[data-target="#sendPayment"]');
  await expect(send).not.toHaveAttribute('title', /.+/);
});
