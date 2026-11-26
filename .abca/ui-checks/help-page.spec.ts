// A public Help page at /help with three FAQ entries (DEM-377).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('the Help page shows three FAQ entries without signing in', async ({ page }) => {
  await page.goto('/help');
  await expect(page.locator('#help-title')).toHaveText('Help');
  await expect(page.locator('header')).toBeVisible();
  await expect(page.locator('footer.footer')).toBeVisible();

  const entries = page.locator('#help-faq .faq-entry');
  await expect(entries).toHaveCount(3);
  await expect(page.locator('#faq-deposit')).toContainText('deposit');
  await expect(page.locator('#faq-send-money')).toContainText('send money');
  await expect(page.locator('#faq-sign-out')).toContainText('sign out');

  await highlight(page, page.locator('#faq-deposit'), 'how to deposit');
  await shot(page, 'The public Help page with its first FAQ entry', { focus: page.locator('#faq-deposit') });
  await highlight(page, page.locator('#faq-sign-out'), 'how to sign out');
  await shot(page, 'All three FAQ entries, no sign-in needed', { focus: page.locator('#help-faq') });
});
