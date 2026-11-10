// A button in the navigation bar switches between light and dark mode, and the
// choice is remembered across page loads (DEM-281).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the theme toggle switches to dark mode and remembers it', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await signIn(page);

  const html = page.locator('html');
  const toggle = page.locator('#theme-toggle');
  await expect(toggle).toBeVisible();
  await expect(html).toHaveAttribute('data-theme', 'light');
  await highlight(page, toggle, 'theme toggle');
  await shot(page, 'The home page in light mode, with the theme button in the navigation bar', { focus: toggle });

  await toggle.click();
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(18, 18, 18)');
  await highlight(page, toggle, 'now dark');
  await shot(page, 'Dark mode after clicking the button', { focus: toggle });

  await page.reload();
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await shot(page, 'Dark mode is kept after reloading the page', { focus: page.locator('#transaction-table') });

  await page.locator('#theme-toggle').click();
  await expect(html).toHaveAttribute('data-theme', 'light');
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await shot(page, 'Clicking again returns to light mode', { focus: page.locator('#theme-toggle') });
});
