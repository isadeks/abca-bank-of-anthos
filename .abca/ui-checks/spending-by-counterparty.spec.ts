// The home page shows this month's spending per counterparty, using the contact's label (DEM-278).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('home shows spending by counterparty with the contact label', async ({ page }) => {
  await signIn(page);

  // Send a small payment to a saved contact so this month has spending to show.
  await page.locator('#paymentSpan').click();
  const form = page.locator('#payment-form');
  await expect(form).toBeVisible();
  const option = page.locator('#payment-accounts option:not([disabled])').first();
  const optionText = (await option.textContent()) ?? '';
  const label = optionText.split(' - ')[0].trim();
  expect(label.length).toBeGreaterThan(0);
  await page.locator('#payment-accounts').selectOption({ index: 0 });
  await page.locator('#payment-amount').fill('1.23');
  await highlight(page, page.locator('#payment-amount'), '$1.23 to ' + label);
  await shot(page, `Sending $1.23 to the saved contact ${label}`, { focus: form });
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#alert-message')).toContainText('Payment successful');

  const section = page.locator('#spending-section');
  await expect(section).toContainText('Spending by counterparty');
  await expect(page.locator('#spending-empty')).toHaveCount(0);

  const rows = page.locator('#spending-table .spending-row');
  await expect(rows.first()).toBeVisible();
  const contactRow = rows.filter({ hasText: label }).first();
  await expect(contactRow).toBeVisible();
  await expect(contactRow.locator('.spending-amount')).toHaveText(/^\$\d[\d,]*\.\d{2}$/);
  await highlight(page, section, 'spending by counterparty');
  await shot(page, `Spending by counterparty on the home page, with ${label} by label`, { focus: section });

  await highlight(page, contactRow, label + ' this month');
  await shot(page, `The row for ${label} shows the total sent in dollars`, { focus: contactRow });
});
