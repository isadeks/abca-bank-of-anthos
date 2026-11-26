// DEM-398: savings tips page lists a seventh tip.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM4] savings tips page lists seven tips, the last about rounding up', async ({ page }) => {
  await page.goto('/savings-tips');
  const items = page.locator('#savings-tips-list li');
  await expect(items).toHaveCount(7);
  const seventh = items.nth(6);
  await expect(seventh).toBeVisible();
  await expect(seventh).toHaveText('Round up your card purchases into savings.');
  await expect(page.locator('#back-to-home')).toBeVisible();
  await highlight(page, seventh, '[DM1] seventh tip');
  await shot(page, '[DM1][DM4] Seven savings tips, the last about rounding up', { focus: seventh });
});
