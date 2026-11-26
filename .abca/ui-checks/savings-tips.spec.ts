// DEM-399: public Savings tips page linked from the footer.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('footer link opens the public savings tips page', async ({ page }) => {
  await page.goto('/login');
  const link = page.locator('footer a[href="/savings-tips"]');
  await expect(link).toBeVisible();
  await highlight(page, link, 'savings tips link');
  await shot(page, 'Savings tips link in the footer', { focus: page.locator('footer.footer') });

  await link.click();
  await expect(page).toHaveURL(/\/savings-tips$/);
  const list = page.locator('#savings-tips-list');
  await expect(list.locator('li')).toHaveCount(5);
  await highlight(page, list, 'five tips');
  await shot(page, 'The Savings tips page without signing in', { focus: list });
});
