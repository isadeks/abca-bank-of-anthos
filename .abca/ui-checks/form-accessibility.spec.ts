// Accessibility of the login, payment and deposit forms (DEM-229): labelled inputs,
// a dialog that traps keyboard focus, and errors that are announced to screen readers.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

test('login failure is announced, deposit and payment dialogs are accessible', async ({ page, browser }) => {
  // 1. Login: inputs are labelled and a failed login lands in a role=alert region
  const ctx = await browser.newContext({ baseURL: process.env.PREVIEW_URL });
  const loginPage = await ctx.newPage();
  await loginPage.goto('/login?msg=Login+Failed');
  const username = loginPage.getByLabel('Username');
  const password = loginPage.getByLabel('Password');
  await expect(username).toBeVisible();
  await expect(password).toBeVisible();
  const alertRegion = loginPage.getByRole('alert').filter({ hasText: 'Login failed.' });
  await expect(alertRegion).toBeVisible();
  await highlight(loginPage, alertRegion, 'announced to screen readers');
  await shot(loginPage, 'Labelled login fields; the failure message is a live alert', { focus: alertRegion });
  await ctx.close();

  // 2. Home: the deposit opener is reachable by keyboard and opens a labelled dialog
  await signIn(page);
  const opener = page.getByRole('button', { name: /Deposit Funds/ });
  await opener.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Make a Deposit' });
  await expect(dialog).toBeVisible();
  await expect(page.locator('#accounts')).toBeFocused();
  await highlight(page, dialog, 'deposit dialog');
  await shot(page, 'Deposit dialog opened from the keyboard, named by its heading', { focus: dialog });

  // 3. Focus stays inside the dialog while tabbing
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(() => !!document.activeElement?.closest('#depositFunds'));
    expect(inside).toBe(true);
  }

  // 4. Invalid amount: field is marked invalid, linked to its message, and focused
  const amount = page.locator('#deposit-amount');
  await amount.fill('0');
  await dialog.locator('button[type=submit]').click();
  await expect(amount).toHaveAttribute('aria-invalid', 'true');
  await expect(amount).toBeFocused();
  const describedBy = await amount.getAttribute('aria-describedby');
  await expect(page.locator(`#${describedBy}`)).toContainText('valid amount');
  await highlight(page, amount, 'invalid, with message');
  await shot(page, 'Invalid amount: focus returns to the field and its error is linked', { focus: amount });

  // 5. Escape closes the dialog and focus returns to the opener
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();

  // 6. The payment dialog has labelled inputs too
  await page.getByRole('button', { name: /Send Payment/ }).click();
  const payment = page.getByRole('dialog', { name: 'Send a Payment' });
  await expect(payment).toBeVisible();
  await expect(page.getByLabel('Transaction Amount')).toBeVisible();
  await shot(page, 'Payment dialog with labelled recipient and amount', { focus: payment });
});
