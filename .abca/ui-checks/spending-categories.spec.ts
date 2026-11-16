// Payments carry a category; history shows and filters by it; home shows
// this month's spending per category (DEM-311).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('pay with a category, see it in history, filter and spending bars', async ({ page }) => {
  await signIn(page);

  await page.locator('#paymentSpan').click();
  const form = page.locator('#payment-form');
  await expect(form).toBeVisible();
  await expect(page.locator('#payment-category')).toHaveValue('Other');
  await page.locator('#payment-category').selectOption('Groceries');
  await page.locator('#payment-amount').fill('1.23');
  await highlight(page, page.locator('#payment-category'), 'category');
  await shot(page, 'Choosing the Groceries category for a payment', { focus: form });
  await form.locator('button[type=submit]').click();

  await expect(page.locator('#alert-message')).toContainText('Payment successful');

  const spending = page.locator('#spending-breakdown');
  await expect(spending.locator('[data-category="Groceries"]')).toBeVisible();
  await highlight(page, spending, 'spending this month');
  await shot(page, 'This month\'s spending per category on the home page', { focus: spending });

  const table = page.locator('#transaction-table');
  await expect(table.locator('.transaction-category', { hasText: 'Groceries' }).first()).toBeVisible();

  await page.locator('#category-filter').selectOption('Groceries');
  await page.waitForURL(/category=Groceries/);
  const cats = page.locator('#transaction-list .transaction-category');
  await expect(cats.first()).toHaveText('Groceries');
  for (const c of await cats.allTextContents()) expect(c.trim()).toBe('Groceries');
  await highlight(page, page.locator('#category-filter'), 'filtered');
  await shot(page, 'History filtered to the Groceries category', { focus: table });
});
