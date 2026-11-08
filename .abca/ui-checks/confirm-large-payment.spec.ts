// UI check: a payment over $1,000 asks for confirmation ("You are about to send $X to Y") before it is submitted.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('large payments need a confirmation step', async ({ page }) => {
  await signIn(page);

  // Make sure the account can afford the payment: deposit from the first external account.
  await page.locator('#depositSpan').click();
  await expect(page.locator('#depositFunds')).toBeVisible();
  await page.locator('#deposit-amount').fill('5000');
  await page.locator('#deposit-form button[type=submit]').click();
  await expect(page.locator('#alert-message')).toContainText('Deposit successful');

  await page.locator('#paymentSpan').click();
  const modal = page.locator('#sendPayment');
  await expect(modal).toBeVisible();

  const amount = page.locator('#payment-amount');
  await amount.fill('1000.5');
  await highlight(page, amount, 'payment over $1,000');
  await shot(page, 'Entering a payment of more than $1,000', { focus: amount });

  await page.locator('#payment-form button[type=submit]').click();

  const confirm = page.locator('#payment-confirm');
  await expect(confirm).toBeVisible();
  await expect(page.locator('#payment-confirm-message')).toContainText('You are about to send $1,000.50 to');
  await expect(page).toHaveURL(/\/home/);
  await highlight(page, confirm, 'confirmation step');
  await shot(page, 'The confirmation step shows the amount and recipient before anything is sent', { focus: confirm });

  // Going back returns to the form without sending anything.
  await page.locator('#payment-confirm-back').click();
  await expect(confirm).toBeHidden();
  await expect(amount).toBeVisible();
  await shot(page, 'Back returns to the payment form', { focus: amount });

  // A payment of $1,000 or less is submitted straight away.
  await amount.fill('1.00');
  await page.locator('#payment-form button[type=submit]').click();
  await expect(page.locator('#alert-message')).toContainText('Payment successful');
  await shot(page, 'A small payment is sent without a confirmation step');
});
