// The app is renamed "Larkspur Bank" and restyled with a navy/teal banking theme (DEM-328).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the app shows the Larkspur Bank brand and banking theme', async ({ page }) => {
  await page.goto('/login');
  await expect(page).toHaveTitle('Larkspur Bank');
  const brand = page.locator('.navbar-brand');
  await expect(brand).toContainText('Larkspur Bank');
  await highlight(page, brand, 'new name');
  await shot(page, 'The sign-in page under the new Larkspur Bank name', { focus: brand });

  await signIn(page);
  const nav = page.locator('.navbar-top');
  await expect(nav).toBeVisible();
  await expect(nav).toHaveCSS('background-image', /linear-gradient/);
  await highlight(page, nav, 'navy header');
  await shot(page, 'Home page with the navy header and card layout', { focus: nav });
  await expect(page.locator('#current-balance')).toBeVisible();
});
