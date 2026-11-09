// The payment and deposit forms offer the 3 most recent payees / external accounts as
// quick-pick chips that fill in the form when clicked (DEM-244).
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('recent payees and accounts are quick picks on the payment and deposit forms', async ({ page }) => {
  await signIn(page);

  // Send Payment
  await page.locator('#paymentSpan').click();
  const paymentForm = page.locator('#payment-form');
  await expect(paymentForm).toBeVisible();
  const payeeChips = page.locator('#recent-payees .recent-chip');
  await expect(payeeChips.first()).toBeVisible();
  expect(await payeeChips.count()).toBeLessThanOrEqual(3);
  await highlight(page, page.locator('#recent-payees'), 'recent payees');
  await shot(page, 'The payment form lists the most recent payees as chips', { focus: paymentForm });

  const payeeNum = await payeeChips.first().getAttribute('data-account-num');
  await payeeChips.first().click();
  const recipient = page.locator('#payment-accounts');
  const selected = await recipient.inputValue();
  if (selected === 'add') {
    await expect(page.locator('#contact_account_num')).toHaveValue(payeeNum!);
  } else {
    expect(selected).toBe(payeeNum);
  }
  await highlight(page, recipient, 'recipient filled in');
  await shot(page, 'Clicking a chip fills in the recipient', { focus: paymentForm });
  await page.locator('.payment-cancel').first().click();
  await expect(paymentForm).toBeHidden();

  // Deposit
  await page.locator('#depositSpan').click();
  const depositForm = page.locator('#deposit-form');
  await expect(depositForm).toBeVisible();
  const accountChips = page.locator('#recent-depositors .recent-chip');
  await expect(accountChips.first()).toBeVisible();
  expect(await accountChips.count()).toBeLessThanOrEqual(3);
  await highlight(page, page.locator('#recent-depositors'), 'recent accounts');
  await shot(page, 'The deposit form lists the most recent accounts as chips', { focus: depositForm });

  const accountNum = await accountChips.first().getAttribute('data-account-num');
  await accountChips.first().click();
  const selectedAccount = await page.locator('#accounts').inputValue();
  if (selectedAccount === 'add') {
    await expect(page.locator('#external_account_num')).toHaveValue(accountNum!);
  } else {
    expect(JSON.parse(selectedAccount).account_num).toBe(accountNum);
  }
  await highlight(page, page.locator('#accounts'), 'account filled in');
  await shot(page, 'Clicking a chip fills in the external account', { focus: depositForm });
});
