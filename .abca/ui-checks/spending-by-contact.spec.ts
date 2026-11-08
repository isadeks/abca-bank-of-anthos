// UI check: the home page shows a "Spending this month" panel under the transaction history.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

const dollars = (text: string) => parseFloat(text.replace(/[^0-9.]/g, ''));

test('home shows spending this month by contact', async ({ page }) => {
  await signIn(page);

  // Make sure there is spending this month: send a payment to the first contact.
  await page.locator('#paymentSpan').click();
  const recipient = page.locator('#payment-accounts');
  await expect(recipient).toBeVisible();
  await recipient.selectOption({ index: 0 });
  const contactLabel = ((await recipient.locator('option').first().textContent()) ?? '')
    .split(' - ')[0].trim();
  await page.locator('#payment-amount').fill('1.23');
  await shot(page, 'Sending a payment to a contact');
  await page.locator('#payment-form button[type=submit]').click();
  await expect(page.locator('#alert-message')).toBeVisible();

  const panel = page.locator('#spending-panel');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('Spending this month');

  // The history service may lag behind the ledger by a moment: reload until the row shows.
  const row = panel.locator('.spending-row', { hasText: contactLabel });
  await expect(async () => {
    await page.reload();
    await expect(row).toBeVisible({ timeout: 2000 });
  }).toPass({ timeout: 60_000 });

  await highlight(page, panel, 'spending this month');
  await shot(page, 'Spending this month by contact, under the transaction history', { focus: panel });

  const rows = panel.locator('.spending-row');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
  expect(count).toBeLessThanOrEqual(5);

  // Largest first.
  const amounts = (await panel.locator('.spending-amount').allTextContents()).map(dollars);
  expect(amounts).toEqual([...amounts].sort((a, b) => b - a));
  expect(dollars((await row.locator('.spending-amount').textContent()) ?? '')).toBeGreaterThanOrEqual(1.23);

  // The panel sits below the transaction history.
  const history = await page.locator('#transaction-table').boundingBox();
  const spending = await panel.boundingBox();
  expect(spending!.y).toBeGreaterThan(history!.y);
});
