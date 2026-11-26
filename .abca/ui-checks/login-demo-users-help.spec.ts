// The login page shows the demo users line under the form (DEM-383).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('login page lists the demo users', async ({ page }) => {
  await page.goto('/login');
  const help = page.locator('#demo-users-help');
  await expect(help).toHaveText('Demo users: alice, bob, eve (password bankofanthos)');
  await highlight(page, help, 'demo users');
  await shot(page, 'Demo users help text under the sign-in form', { focus: help });
});
