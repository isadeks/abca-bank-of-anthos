// The sign-in page has a muted help line under the Sign in button (DEM-372).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('sign-in page shows a plain-text help line under the button', async ({ page }) => {
  await page.goto('/login');
  const button = page.locator('#login-form button[type=submit]');
  const help = page.locator('#login-help');
  await expect(help).toHaveText('Trouble signing in? Contact Cymbal Bank support.');
  await expect(help.locator('a')).toHaveCount(0);
  await expect(help).toHaveClass(/text-muted/);

  const b = await button.boundingBox();
  const h = await help.boundingBox();
  expect(h!.y).toBeGreaterThan(b!.y + b!.height - 1);

  await highlight(page, button, 'Sign in');
  await highlight(page, help, 'help line');
  await shot(page, 'Help line under the Sign in button', { focus: help });
});
