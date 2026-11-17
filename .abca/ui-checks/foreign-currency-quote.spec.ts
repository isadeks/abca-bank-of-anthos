// The "Order foreign currency" page shows a quote with rate, fee, delivery and total (DEM-331).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('request a foreign currency quote from the home page', async ({ page }) => {
  await signIn(page);

  const link = page.locator('#order-foreign-currency');
  await expect(link).toBeVisible();
  await highlight(page, link, 'order foreign currency');
  await shot(page, 'The home page links to Order foreign currency', { focus: link });
  await link.click();

  await expect(page.locator('#fx-title')).toHaveText('Order foreign currency');
  await page.locator('#fx-currency').selectOption('EUR');
  await page.locator('#fx-amount').fill('100');
  const form = page.locator('#fx-form');
  await highlight(page, form, 'currency and amount');
  await shot(page, 'Pick a currency and an amount', { focus: form });
  await page.locator('#fx-submit').click();

  // Live rates come from Frankfurter: either a quote or a clear "unavailable" message.
  const quote = page.locator('#fx-quote');
  const unavailable = page.locator('#fx-error');
  await expect(quote.or(unavailable)).toBeVisible();
  if (await quote.isVisible()) {
    await expect(page.locator('#fx-rate')).toContainText('EUR');
    await expect(page.locator('#fx-fee')).toContainText('$');
    await expect(page.locator('#fx-delivery')).toHaveText('$5.00');
    await expect(page.locator('#fx-total')).toHaveText(/^\$\d[\d,]*\.\d{2}$/);
    await highlight(page, quote, 'quote');
    await shot(page, 'The quote shows the rate, fee, delivery charge and total in dollars', { focus: quote });
  } else {
    await expect(unavailable).toContainText('unavailable');
    await shot(page, 'If rates cannot be reached, a clear message is shown', { focus: unavailable });
  }
});
