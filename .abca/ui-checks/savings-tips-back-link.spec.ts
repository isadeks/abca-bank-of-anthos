// DEM-398: savings tips page links back to the home page.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM4] savings tips page has a Back to home link at the bottom', async ({ page }) => {
  await page.goto('/savings-tips');
  const link = page.locator('#back-to-home');
  await expect(link).toBeVisible();
  await expect(link).toHaveText('Back to home');
  await expect(link).toHaveAttribute('href', '/home');
  await highlight(page, link, '[DM4] back to home');
  await shot(page, '[DM1][DM2] Back to home link below the tips, no sign-in needed', { focus: link });
});
