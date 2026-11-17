// Public landing page before sign-in (DEM-347).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('landing page shows bank sections and links to sign in', async ({ page }) => {
  await page.goto('/');
  const hero = page.locator('#landing-hero');
  await expect(hero).toBeVisible();
  await highlight(page, hero, 'hero banner');
  await shot(page, 'Public landing page with hero banner', { focus: hero });

  const rates = page.locator('#landing-rates');
  await expect(page.locator('#landing-personal')).toBeVisible();
  await expect(page.locator('#landing-business')).toBeVisible();
  await expect(page.locator('#landing-contact')).toBeVisible();
  await highlight(page, rates, 'rates');
  await shot(page, 'Rates and branch information', { focus: rates });

  const signIn = page.locator('#landing-sign-in');
  await highlight(page, signIn, 'sign in');
  await shot(page, 'Sign-in call to action', { focus: signIn });
  await signIn.click();
  await expect(page).toHaveURL(/\/login/);
  await expect(page.locator('#login-form')).toBeVisible();
  await shot(page, 'The sign-in page');
});
