import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('[DM1][DM3] Transaction History heading has a tooltip', async ({ page }) => {
  await signIn(page);
  const heading = page.locator('#transaction-history-heading');
  await expect(heading).toContainText('Transaction History');
  await expect(heading).toHaveAttribute('title', 'Your most recent transactions');
  await highlight(page, heading, '[DM1] tooltip: Your most recent transactions');
  await shot(page, '[DM3] Transaction History heading carries its tooltip', { focus: heading });
});
