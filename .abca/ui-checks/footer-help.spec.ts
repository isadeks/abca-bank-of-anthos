import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('[DM3][DM5] footer Help link opens the help page', async ({ page }) => {
  await page.goto('/fees');
  const link = page.locator('#footer-help-link');
  await expect(link).toHaveAttribute('href', '/help');
  await highlight(page, link, '[DM2] Help link');
  await shot(page, '[DM2] The footer has a Help link', { focus: link });

  await link.click();
  await expect(page).toHaveURL(/\/help$/);
  await expect(page.locator('#help-phone')).toContainText('1-800-555-0100');
  await expect(page.locator('#help-email')).toContainText('help@bank.example');
  await shot(page, '[DM1][DM3] The help page shows phone and email', { focus: page.locator('#help-phone') });
});
