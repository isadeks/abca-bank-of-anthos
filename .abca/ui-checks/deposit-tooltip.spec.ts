import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('deposit card shows a tooltip', async ({ page }) => {
  await signIn(page);
  const card = page.locator('#deposit-card');
  await expect(card).toHaveAttribute('title', 'Add money to your checking account');
  await highlight(page, card, 'deposit card tooltip');
  await shot(page, 'Deposit card with its tooltip', { focus: card });
});
