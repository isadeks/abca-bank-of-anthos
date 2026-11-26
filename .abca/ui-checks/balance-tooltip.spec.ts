import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('[DM1][DM3] the balance shows the tooltip "Your current available balance"', async ({ page }) => {
  await signIn(page);
  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  await balance.hover();
  await highlight(page, balance, '[DM1] hover for tooltip');
  await shot(page, '[DM1] Balance on the home page, hovered', { focus: balance });
  await expect(balance).toHaveAttribute('title', 'Your current available balance');
  await shot(page, '[DM3] Balance element carries the tooltip text', { focus: balance });
});
