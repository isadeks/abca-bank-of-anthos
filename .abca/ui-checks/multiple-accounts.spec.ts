// A user can open a second account, switch between accounts from the header and
// transfer between their own accounts (DEM-296).
import { test, expect } from '@playwright/test';
import { highlight, shot } from './ui-annotate';

function parseDollars(text: string): number {
  return parseFloat(text.replace(/[^0-9.\-]/g, ''));
}

test('a user opens a Savings account, switches to it and transfers between accounts', async ({ page }) => {
  // A new user, so the check does not depend on (or fill up) the demo user's accounts.
  const suffix = Date.now().toString(36).slice(-6);
  await page.goto('/signup');
  await page.locator('#signup-username').fill(`multi_${suffix}`);
  await page.locator('#signup-password').fill('bells');
  await page.locator('#signup-password-repeat').fill('bells');
  await page.locator('#signup-firstname').fill('Tom');
  await page.locator('#signup-lastname').fill('Nook');
  await page.locator('#signup-birthday').fill('1981-01-01');
  await page.locator('#signup-form button[type=submit]').click();
  await expect(page.locator('#current-balance')).toContainText('$0.00');

  const title = page.locator('#account-title');
  const accountNumber = page.locator('.account-number');
  await expect(title).toHaveText('Checking Account');
  const checkingNumber = (await accountNumber.innerText()).trim();
  await highlight(page, page.locator('#account-switcher'), 'account switcher');
  await shot(page, 'A new user starts with a Checking account and an account switcher in the header', { focus: page.locator('#account-switcher') });

  // Fund the Checking account.
  await page.locator('#depositSpan').click();
  const deposit = page.locator('#deposit-form');
  await expect(deposit).toBeVisible();
  await page.locator('#accounts').selectOption('add');
  await page.locator('#external_account_num').fill('1234567890');
  await page.locator('#external_routing_num').fill('123456789');
  await page.locator('#deposit-amount').fill('100');
  await deposit.locator('button[type=submit]').click();
  const balance = page.locator('#current-balance');
  await expect(async () => {
    await page.goto('/home');
    expect(parseDollars((await balance.innerText()).replace(/,/g, ''))).toBeCloseTo(100, 2);
  }).toPass({ timeout: 60_000 });

  // Open a second account from the header.
  await page.locator('#accountSwitcherDropdown').click();
  await page.locator('#open-account-link').click();
  const openForm = page.locator('#open-account-form');
  await expect(openForm).toBeVisible();
  await page.locator('#new-account-label').fill('Savings');
  await highlight(page, page.locator('#new-account-label'), 'new account name');
  await shot(page, 'Opening a second account called Savings', { focus: openForm });
  await openForm.locator('button[type=submit]').click();

  await expect(page.locator('#alert-message')).toContainText('Opened account Savings');
  await expect(title).toHaveText('Savings Account');
  await expect(page.locator('#active-account-label')).toHaveText('Savings');
  const savingsNumber = (await accountNumber.innerText()).trim();
  expect(savingsNumber).not.toBe(checkingNumber);
  await expect(balance).toContainText('$0.00');
  await highlight(page, title, 'Savings account');
  await shot(page, 'The new Savings account has its own number and a $0.00 balance', { focus: page.locator('.top-row') });

  // Switch back to Checking from the header: its own balance is shown.
  await page.locator('#accountSwitcherDropdown').click();
  await page.locator('.account-switch-option', { hasText: 'Checking' }).click();
  await expect(title).toHaveText('Checking Account');
  await expect(accountNumber).toHaveText(checkingNumber);
  await expect(balance).toContainText('$100.00');
  await highlight(page, balance, 'Checking balance');
  await shot(page, 'Switching back to Checking shows its own balance', { focus: page.locator('.top-row') });

  // Transfer $30 from Checking to Savings.
  await page.locator('#transferSpan').click();
  const transfer = page.locator('#transfer-form');
  await expect(transfer).toBeVisible();
  await page.locator('#transfer-to').selectOption({ label: `Savings - ${savingsNumber}` });
  await page.locator('#transfer-amount').fill('30');
  await highlight(page, page.locator('#transfer-amount'), 'transfer $30');
  await shot(page, 'Transferring $30 from Checking to Savings', { focus: transfer });
  await transfer.locator('button[type=submit]').click();
  await expect(page.locator('#alert-message')).toContainText('Transfer successful');
  await expect(async () => {
    await page.goto('/home');
    expect(parseDollars((await balance.innerText()).replace(/,/g, ''))).toBeCloseTo(70, 2);
  }).toPass({ timeout: 60_000 });
  await expect(page.locator('#transaction-list tr').first()).toContainText('Savings');
  await highlight(page, page.locator('#transaction-table'), 'labelled with Savings');
  await shot(page, 'Checking is down to $70.00 and the history names the Savings account', { focus: page.locator('#transaction-table') });

  // Savings received the money.
  await page.locator('#accountSwitcherDropdown').click();
  await page.locator('.account-switch-option', { hasText: 'Savings' }).click();
  await expect(title).toHaveText('Savings Account');
  await expect(async () => {
    await page.goto('/home');
    expect(parseDollars((await balance.innerText()).replace(/,/g, ''))).toBeCloseTo(30, 2);
  }).toPass({ timeout: 60_000 });
  await highlight(page, balance, 'Savings balance');
  await shot(page, 'Savings now holds the $30.00 that was transferred', { focus: page.locator('.top-row') });
});
