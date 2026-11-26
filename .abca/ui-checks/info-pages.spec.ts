// DEM-394: Fees and Opening hours pages linked from the footer.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM3] footer links lead to the fees and opening hours pages', async ({ page }) => {
  await page.goto('/login');
  const feesLink = page.locator('footer a[href="/fees"]');
  await expect(feesLink).toBeVisible();
  await highlight(page, feesLink, 'fees link');
  await shot(page, '[DM3] Footer links on the login page', { focus: page.locator('footer.footer') });

  await feesLink.click();
  await expect(page).toHaveURL(/\/fees$/);
  const fees = page.locator('#fees-table');
  await expect(fees).toContainText('Monthly account fee');
  await expect(fees).toContainText('$2 per month');
  await highlight(page, fees, 'fees');
  await shot(page, '[DM1] The fees page', { focus: fees });

  await page.locator('footer a[href="/hours"]').click();
  await expect(page).toHaveURL(/\/hours$/);
  const hours = page.locator('#hours-table');
  await expect(hours).toContainText('9:00–17:00');
  await expect(hours).toContainText('Closed');
  await highlight(page, hours, 'hours');
  await shot(page, '[DM2] The opening hours page', { focus: hours });

  await signIn(page);
  await expect(page.locator('footer a[href="/fees"]')).toBeVisible();
  await expect(page.locator('footer a[href="/hours"]')).toBeVisible();
});
