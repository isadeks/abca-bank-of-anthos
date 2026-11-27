// DEM-403: Help page linked from the footer.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('[DM1][DM2][DM3][DM4] footer Help link leads to the public help page', async ({ page }) => {
  await page.goto('/login');
  const link = page.locator('footer a[href="/help"]');
  await expect(link).toBeVisible();
  await highlight(page, link, 'help link');
  await shot(page, '[DM2] Help link in the footer of the login page', { focus: page.locator('footer.footer') });

  await link.click();
  await expect(page).toHaveURL(/\/help$/);
  const phone = page.locator('a[href="tel:+18005550100"]');
  await expect(phone).toHaveText('1-800-555-0100');
  await expect(page.getByText('help@bank.example')).toBeVisible();
  await highlight(page, phone, 'phone');
  await shot(page, '[DM1][DM3] The help page with phone and email', { focus: phone });
});
