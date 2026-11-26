// DEM-398: savings tips page lists a sixth tip.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM3] savings tips page lists six tips, the sixth about subscriptions', async ({ page }) => {
  await page.goto('/savings-tips');
  const items = page.locator('#savings-tips-list li');
  await expect(items).toHaveCount(7);
  await expect(items.nth(0)).toHaveText('Pay yourself first: move money to savings on payday.');
  const sixth = items.nth(5);
  await expect(sixth).toHaveText("Review your subscriptions every month and cancel the ones you don't use.");
  await highlight(page, sixth, '[DM1] sixth tip');
  await shot(page, '[DM1][DM2][DM3] Six savings tips, the sixth about subscriptions', { focus: sixth });
});
