// UI check: set a monthly budget on the home page, see its usage bar, and get a warning
// (with confirm / cancel) before a payment that would push this month's spending over it.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('set a monthly budget, see usage, and get warned before an over-limit payment', async ({ page }) => {
  await signIn(page);

  // 1. Set a small monthly limit so that any payment of $2.00 is over it.
  const section = page.locator('#budget-section');
  await expect(section).toBeVisible();
  await page.locator('#budget-limit-input').fill('1.00');
  await highlight(page, page.locator('#budget-form'), 'monthly limit: $1.00');
  await shot(page, 'Setting a monthly spending limit of $1.00 on the home page', { focus: section });
  await page.locator('#budget-save').click();

  // 2. The usage bar shows spent, remaining and percent against the limit.
  await expect(page.locator('#budget-progress')).toBeVisible();
  await expect(page.locator('#budget-limit')).toHaveText('$1.00');
  await expect(page.locator('#budget-spent')).toContainText('$');
  await expect(page.locator('#budget-remaining')).toContainText('$');
  await expect(page.locator('#budget-percent')).toContainText('%');
  await highlight(page, page.locator('#budget-usage'), 'spent, remaining, percent');
  await shot(page, 'This month\'s budget usage: spent, remaining and percent used', { focus: section });

  // 3. A payment over the limit shows the warning before it is sent.
  await page.locator('#paymentSpan').click();
  const amount = page.locator('#payment-amount');
  await expect(amount).toBeVisible();
  await page.locator('#payment-accounts').selectOption({ index: 0 });
  await amount.fill('2.00');
  await page.locator('#payment-submit').click();
  const warning = page.locator('#budget-warning');
  await expect(warning).toBeVisible();
  await expect(page.locator('#budget-warning-text')).toContainText('over your monthly budget of $1.00');
  await highlight(page, warning, 'over budget warning');
  await shot(page, 'Warning before a payment that would exceed the monthly budget', { focus: warning });

  // 4. Cancel keeps the user on the payment form; nothing was sent.
  await page.locator('#budget-warning-cancel').click();
  await expect(warning).toBeHidden();
  await expect(page.locator('#payment-submit')).toBeVisible();

  // 5. Confirming still sends the payment.
  await page.locator('#payment-submit').click();
  await expect(warning).toBeVisible();
  await page.locator('#budget-warning-confirm').click();
  const message = page.locator('#alert-message');
  await expect(message).toContainText('Payment successful');
  await highlight(page, message, 'payment sent after confirming');
  await shot(page, 'The payment goes through after the user confirms', { focus: message });

  // 6. Clear the budget again so the demo account is left as found.
  await page.locator('#budget-clear').click();
  await expect(page.locator('#budget-empty')).toBeVisible();
});
