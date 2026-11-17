// The sign-up page hints "Letters and numbers only." under the username box (DEM-323).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('sign-up shows the username hint', async ({ page }) => {
  await page.goto('/signup');

  const hint = page.locator('#signup-username-hint');
  await expect(hint).toBeVisible();
  await expect(hint).toHaveText('Letters and numbers only.');
  await highlight(page, hint, 'username hint');
  await shot(page, 'The sign-up page hints at the allowed username characters', { focus: hint });
});
