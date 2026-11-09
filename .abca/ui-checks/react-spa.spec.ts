// The frontend is a React single-page app (DEM-250): a deposit updates the balance and the
// history in place, without loading another page, and signing out returns to the login form.
import { test, expect } from '@playwright/test';
import { signIn, highlight, shot } from './ui-annotate';

const cents = (text: string) => Math.round(parseFloat(text.replace(/[^0-9.-]/g, '')) * 100);

test('a deposit updates the home page of the single-page app in place', async ({ page }) => {
  await signIn(page);

  const balance = page.locator('#current-balance');
  await expect(balance).toContainText('$');
  await expect(page.locator('#transaction-table')).toBeVisible();
  // a value on window is lost if the browser loads another page
  await page.evaluate(() => { (window as any).__spa = true; });
  const before = cents(await balance.innerText());
  await highlight(page, balance, 'balance');
  await shot(page, 'The home page of the React app after sign-in', { focus: balance });

  await page.locator('#depositSpan').click();
  const form = page.locator('#deposit-form');
  await expect(form).toBeVisible();
  await page.locator('#deposit-amount').fill('1.37');
  await highlight(page, page.locator('#deposit-amount'), 'amount');
  await shot(page, 'The deposit form opens as a dialog over the page', { focus: form });
  await form.getByRole('button', { name: 'Deposit' }).click();

  const message = page.locator('#alert-message');
  await expect(message).toContainText('Deposit successful');
  await expect(form).toBeHidden();
  await expect(balance).toHaveText(new RegExp(`^\\s*\\$${((before + 137) / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}\\s*$`));
  await highlight(page, message, 'confirmation');
  await highlight(page, balance, 'new balance');
  await shot(page, 'The balance has grown by the deposit and a confirmation is shown', { focus: balance });
  expect(await page.evaluate(() => (window as any).__spa)).toBe(true);

  await page.locator('#accountDropdown').click();
  const signOut = page.getByRole('button', { name: 'Sign out' });
  await highlight(page, signOut, 'sign out');
  await shot(page, 'The account menu offers to sign out', { focus: signOut });
  await signOut.click();
  await expect(page.locator('#login-form')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
  await shot(page, 'Signing out returns to the sign-in form', { focus: page.locator('#login-form') });
});
