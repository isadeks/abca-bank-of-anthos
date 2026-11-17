// The whole site gets a traditional community-bank look (DEM-346).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('login and home pages show the community-bank header and footer', async ({ page }) => {
  await page.goto('/login');
  const utility = page.locator('.utility-bar');
  await expect(utility).toBeVisible();
  const nav = page.locator('.navbar-top');
  await expect(nav).toBeVisible();
  await expect(nav).toHaveCSS('border-bottom-width', '4px');
  await highlight(page, nav, 'bank-style header');
  await shot(page, 'Sign-in page with the new bank header', { focus: nav });
  const signInBtn = page.locator('.btn-sign-in');
  await expect(signInBtn).toBeVisible();
  await highlight(page, signInBtn, 'green button');
  await shot(page, 'Sign-in button in the bank palette', { focus: signInBtn });

  await signIn(page);
  await expect(page.locator('#current-balance')).toBeVisible();
  await highlight(page, nav, 'header');
  await shot(page, 'Signed-in home page with the new header', { focus: nav });
  const footer = page.locator('footer.footer .footer-links');
  await expect(footer).toContainText('Locations');
  await highlight(page, footer, 'footer links');
  await shot(page, 'Bank-style footer', { focus: footer });
});
