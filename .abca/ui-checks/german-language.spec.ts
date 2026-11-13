// The UI can be switched to German and back to English (DEM-294).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('the home page can be switched to German', async ({ page }) => {
  await signIn(page);

  const switcher = page.locator('#language-switcher');
  await expect(switcher).toBeVisible();
  await expect(page.locator('.current-balance')).toHaveText('Current Balance');
  await highlight(page, switcher, 'language switcher');
  await shot(page, 'The home page in English, with a language switcher in the header', { focus: switcher });

  await switcher.locator('a[data-language="de"]').click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await expect(page.locator('.current-balance')).toHaveText('Aktueller Kontostand');
  await expect(page.locator('#depositSpan')).toContainText('Geld einzahlen');
  await expect(page.locator('#paymentSpan')).toContainText('Zahlung senden');
  await expect(page.locator('#transaction-table')).toContainText('Datum');
  const balance = page.locator('.current-balance');
  await highlight(page, balance, 'German');
  await shot(page, 'The home page in German after choosing Deutsch', { focus: balance });

  // The choice is remembered when the page is reloaded.
  await page.reload();
  await expect(page.locator('.current-balance')).toHaveText('Aktueller Kontostand');

  await page.locator('#language-switcher a[data-language="en"]').click();
  await expect(page.locator('.current-balance')).toHaveText('Current Balance');
  await shot(page, 'Switching back to English', { focus: page.locator('#language-switcher') });
});
