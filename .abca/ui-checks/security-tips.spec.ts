// The public Security tips page at /security-tips shows three tips, no sign-in (DEM-378).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('security tips page is public and shows three tips', async ({ page }) => {
  await page.goto('/security-tips');
  await expect(page).toHaveURL(/\/security-tips$/);

  const title = page.locator('#security-tips-title');
  await expect(title).toHaveText('Security tips');
  await highlight(page, title, 'Security tips');

  const tips = page.locator('#security-tips .security-tip');
  await expect(tips).toHaveCount(3);
  await expect(tips.nth(0)).toContainText('Never share your password');
  await expect(tips.nth(1)).toContainText('Check the URL');
  await expect(tips.nth(2)).toContainText('Sign out on shared computers');
  await highlight(page, page.locator('#security-tips'), 'three tips');
  await shot(page, 'The three security tips, visible without signing in', { focus: page.locator('#security-tips') });

  await expect(page.locator('footer.footer')).toBeVisible();
});
