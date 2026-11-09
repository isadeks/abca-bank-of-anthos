// Every page has a footer with Help, Privacy and Contact links (DEM-259).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the footer links to Help, Privacy and Contact', async ({ page }) => {
  await signIn(page);

  const links = page.locator('#footer-links');
  await expect(links.locator('a')).toHaveText(['Help', 'Privacy', 'Contact']);
  await highlight(page, links, 'support links');
  await shot(page, 'Footer with Help, Privacy and Contact links on the home page', { focus: links });

  await page.locator('#footer-help').click();
  await expect(page).toHaveURL(/\/help$/);
  const title = page.locator('#support-title');
  await expect(title).toHaveText('Help');
  await highlight(page, title, 'help page');
  await shot(page, 'The Help page, still with the footer', { focus: title });

  await expect(page.locator('#footer-links')).toBeVisible();
  await page.locator('#footer-privacy').click();
  await expect(page.locator('#support-title')).toHaveText('Privacy');
  await page.locator('#footer-contact').click();
  await expect(page.locator('#support-title')).toHaveText('Contact');
  await shot(page, 'The Contact page reached from the footer', { focus: page.locator('#footer-links') });
});
