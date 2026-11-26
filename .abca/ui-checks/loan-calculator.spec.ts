// DEM-396: public loan calculator linked from the footer.
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

test('loan calculator computes the monthly payment', async ({ page }) => {
  await page.goto('/login');
  const link = page.locator('footer a[href="/loan-calculator"]');
  await expect(link).toBeVisible();
  await highlight(page, link, 'loan calculator link');
  await shot(page, 'Footer link to the loan calculator', { focus: page.locator('footer.footer') });
  await link.click();
  await expect(page).toHaveURL(/\/loan-calculator$/);

  await page.fill('#loan-amount', '10000');
  await page.fill('#loan-rate', '12');
  await page.fill('#loan-months', '12');
  await page.click('#loan-submit');
  const result = page.locator('#loan-result');
  await expect(result).toContainText('$888.49');
  await highlight(page, result, 'monthly payment');
  await shot(page, 'Monthly payment for $10,000 at 12% over 12 months', { focus: page.locator('#loan-form') });

  await page.fill('#loan-rate', '0');
  await page.click('#loan-submit');
  await expect(result).toContainText('$833.33');

  await page.fill('#loan-months', '0');
  await page.click('#loan-submit');
  await expect(result).toContainText('Please enter');
  await shot(page, 'Invalid input shows a message', { focus: result });
});
