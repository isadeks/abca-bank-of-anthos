import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM3] the Send Payment card shows its tooltip', async ({ page }) => {
  await signIn(page);
  const card = page.locator('#send-payment-card');
  await expect(card).toBeVisible();
  await expect(card).toHaveAttribute('title', 'Send money to a contact or another account');
  await card.hover();
  await highlight(page, card, '[DM1] Send Payment card tooltip');
  await shot(page, '[DM1] Send Payment card with its tooltip text', { focus: card });
});
